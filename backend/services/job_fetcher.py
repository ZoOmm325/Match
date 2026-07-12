from __future__ import annotations

import asyncio
import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from backend.schemas.jd import (
    JdFetchRequest,
    JdFetchResponse,
    JobMarketTrendPointResponse,
    JobMarketTrendResponse,
)

USER_AGENT = "JD-Major-Match/0.1 (+https://localhost; public JD fetcher)"
SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
TREND_SEARCH_URLS = (
    "https://html.duckduckgo.com/html/?q={query}",
    "https://www.bing.com/search?q={query}",
)
MAX_PAGE_BYTES = 800_000
MIN_JD_LENGTH = 120
MAX_JD_LENGTH = 8000
LOGIN_HINTS = ("登录", "登陆", "验证码", "安全验证", "扫码", "sign in", "captcha")
JD_HINTS = ("岗位职责", "职位描述", "工作职责", "任职要求", "职位要求", "job description")


@dataclass(frozen=True)
class CandidatePage:
    url: str
    title: str | None = None


class PublicJdFetchError(RuntimeError):
    """Raised when no compliant public JD can be fetched."""


class PublicJobTrendFetcher:
    def __init__(self, *, timeout: float = 8.0, max_results_per_year: int = 50) -> None:
        self.timeout = timeout
        self.max_results_per_year = max_results_per_year

    async def fetch(
        self,
        *,
        keyword: str,
        years: int,
        source_url: str | None = None,
    ) -> JobMarketTrendResponse:
        normalized_keyword = keyword.strip()
        if len(normalized_keyword) < 2:
            raise ValueError("keyword must contain at least 2 characters")
        normalized_source_url = source_url.strip() if source_url else None
        if normalized_source_url and not _is_http_url(normalized_source_url):
            raise ValueError("source_url must start with http or https")

        current_year = datetime_now_year()
        start_year = current_year - years + 1
        points: list[JobMarketTrendPointResponse] = []
        successful_years = 0
        source_url_counted = False

        if normalized_source_url:
            await PublicJobFetcher(timeout=self.timeout).fetch(
                JdFetchRequest(
                    keyword=normalized_keyword,
                    source_url=normalized_source_url,
                    max_results=1,
                )
            )
            source_url_counted = True

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        ) as client:
            for year in range(start_year, current_year + 1):
                count, ok = await self._count_public_results(client, normalized_keyword, year)
                if source_url_counted and year == current_year:
                    count += 1
                if ok:
                    successful_years += 1
                points.append(JobMarketTrendPointResponse(year=year, count=count))

        if successful_years == 0 and not source_url_counted:
            raise PublicJdFetchError("public job trend search is temporarily unavailable")

        return JobMarketTrendResponse(
            keyword=normalized_keyword,
            years=years,
            total=sum(point.count for point in points),
            source_url=normalized_source_url,
            points=points,
        )

    async def _count_public_results(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        year: int,
    ) -> tuple[int, bool]:
        query = f"{keyword} 招聘 JD 岗位职责 任职要求 {year}"
        for search_template in TREND_SEARCH_URLS:
            search_url = search_template.format(query=quote_plus(query))
            try:
                response = await client.get(search_url)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            if response.status_code == 202:
                continue

            parser = _TextExtractor()
            parser.feed(response.text[:MAX_PAGE_BYTES])
            candidates = _dedupe_candidates(
                CandidatePage(url=_normalize_search_url(link.url), title=link.title)
                for link in parser.links
            )
            candidates = [
                candidate for candidate in candidates if _is_public_result_url(candidate.url)
            ]
            return min(len(candidates), self.max_results_per_year), True
        return 0, False


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[CandidatePage] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag_name == "title":
            self._in_title = True
        if tag_name == "a":
            href = dict(attrs).get("href")
            if href:
                self._current_href = href
                self._current_link_text = []
        if tag_name in {"p", "div", "li", "br", "section", "article", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag_name == "title":
            self._in_title = False
        if tag_name == "a" and self._current_href:
            text = _squash_whitespace("".join(self._current_link_text))
            self.links.append(CandidatePage(url=self._current_href, title=text or None))
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data)
        if self._current_href:
            self._current_link_text.append(data)

    @property
    def title(self) -> str | None:
        title = _squash_whitespace(" ".join(self.title_parts))
        return title or None

    @property
    def text(self) -> str:
        return _clean_text("\n".join(self.text_parts))


class PublicJobFetcher:
    def __init__(self, *, timeout: float = 8.0) -> None:
        self.timeout = timeout

    async def fetch(self, payload: JdFetchRequest) -> JdFetchResponse:
        if payload.source_url and not _is_http_url(payload.source_url):
            raise ValueError("source_url 必须是 http 或 https 开头的公开页面地址")
        candidates = [CandidatePage(payload.source_url)] if payload.source_url else []
        if not candidates:
            try:
                candidates = await self._search(payload)
            except httpx.HTTPError as exc:
                raise PublicJdFetchError("公开搜索服务暂时不可用，请稍后重试") from exc

        inspected_urls: list[str] = []
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            for candidate in candidates[: payload.max_results]:
                if not _is_http_url(candidate.url):
                    continue
                inspected_urls.append(candidate.url)
                if not await self._robots_allows(client, candidate.url):
                    continue
                try:
                    response = await client.get(candidate.url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    continue
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    continue
                html = response.text[:MAX_PAGE_BYTES]
                extracted = self._extract_from_html(
                    html,
                    keyword=payload.keyword,
                    source_url=str(response.url),
                    inspected_urls=inspected_urls,
                    fallback_title=candidate.title,
                )
                if extracted:
                    return extracted

        raise PublicJdFetchError("未找到可公开访问且允许抓取的岗位 JD")

    async def _search(self, payload: JdFetchRequest) -> list[CandidatePage]:
        query_parts = [payload.keyword, payload.city or "", "招聘 JD 岗位职责 任职要求"]
        search_url = SEARCH_URL.format(query=quote_plus(" ".join(part for part in query_parts if part)))
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        ) as client:
            response = await client.get(search_url)
            response.raise_for_status()
        parser = _TextExtractor()
        parser.feed(response.text[:MAX_PAGE_BYTES])
        return _dedupe_candidates(
            CandidatePage(url=_normalize_search_url(link.url), title=link.title)
            for link in parser.links
        )

    async def _robots_allows(self, client: httpx.AsyncClient, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = await client.get(robots_url)
        except httpx.HTTPError:
            return False
        if response.status_code >= 400:
            return True
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        return await asyncio.to_thread(parser.can_fetch, USER_AGENT, url)

    def _extract_from_html(
        self,
        html: str,
        *,
        keyword: str,
        source_url: str,
        inspected_urls: list[str],
        fallback_title: str | None,
    ) -> JdFetchResponse | None:
        parser = _TextExtractor()
        parser.feed(html)
        text = parser.text
        if len(text) < MIN_JD_LENGTH or _looks_blocked(text):
            return None
        jd_text = _extract_jd_window(text)
        if len(jd_text) < MIN_JD_LENGTH:
            return None
        title = _guess_title(parser.title or fallback_title, keyword)
        return JdFetchResponse(
            keyword=keyword,
            title=title,
            company=None,
            source_url=source_url,
            source_domain=urlparse(source_url).netloc,
            jd_text=jd_text[:MAX_JD_LENGTH],
            inspected_urls=inspected_urls,
        )


def _extract_jd_window(text: str) -> str:
    lower = text.lower()
    positions = [lower.find(hint.lower()) for hint in JD_HINTS if lower.find(hint.lower()) >= 0]
    if not positions:
        return text[:MAX_JD_LENGTH]
    start = max(0, min(positions) - 120)
    return text[start : start + MAX_JD_LENGTH].strip()


def _looks_blocked(text: str) -> bool:
    sample = text[:1000].lower()
    return any(hint.lower() in sample for hint in LOGIN_HINTS)


def _guess_title(title: str | None, keyword: str) -> str | None:
    if not title:
        return keyword
    title = re.split(r"[-_|—]", title, maxsplit=1)[0].strip()
    return title[:120] or keyword


def _clean_text(text: str) -> str:
    lines = [_squash_whitespace(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _squash_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_http_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_search_url(url: str) -> str:
    if url.startswith("//"):
        url = f"https:{url}"
    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [url])[0]
        return target
    if parsed.netloc.endswith("bing.com") and parsed.path.startswith("/ck/"):
        target = _decode_bing_target(parsed.query)
        if target:
            return target
    return url


def _decode_bing_target(query: str) -> str | None:
    encoded = parse_qs(query).get("u", [None])[0]
    if not encoded:
        return None
    if encoded.startswith("a1"):
        encoded = encoded[2:]
    padding = "=" * (-len(encoded) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return decoded if _is_http_url(decoded) else None


def _is_public_result_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host:
        return False
    blocked_hosts = ("bing.com", "microsoft.com", "duckduckgo.com")
    return not any(host == blocked or host.endswith(f".{blocked}") for blocked in blocked_hosts)


def _dedupe_candidates(candidates: object) -> list[CandidatePage]:
    seen: set[str] = set()
    deduped: list[CandidatePage] = []
    for candidate in candidates:
        if not isinstance(candidate, CandidatePage):
            continue
        if not _is_http_url(candidate.url) or candidate.url in seen:
            continue
        seen.add(candidate.url)
        deduped.append(candidate)
    return deduped


def datetime_now_year() -> int:
    return datetime.now(UTC).year
