import base64

import pytest

from backend.schemas.jd import JdFetchResponse
from backend.services import job_fetcher
from backend.services.job_fetcher import PublicJobTrendFetcher, _is_public_result_url, _normalize_search_url


def test_normalize_search_url_decodes_bing_redirect_target():
    target = "https://jobs.example.com/detail/123"
    encoded = "a1" + base64.urlsafe_b64encode(target.encode("utf-8")).decode("ascii").rstrip("=")
    url = f"https://www.bing.com/ck/a?u={encoded}&ntb=1"

    assert _normalize_search_url(url) == target


def test_public_result_url_filters_search_engine_internal_links():
    assert _is_public_result_url("https://jobs.example.com/detail/123") is True
    assert _is_public_result_url("https://www.bing.com/search?q=job") is False
    assert _is_public_result_url("https://duckduckgo.com/l/?uddg=https://example.com") is False


@pytest.mark.asyncio
async def test_job_market_trend_counts_valid_public_source_url(monkeypatch):
    class FakePublicJobFetcher:
        def __init__(self, **_kwargs):
            pass

        async def fetch(self, payload):
            return JdFetchResponse(
                keyword=payload.keyword,
                source_url=payload.source_url,
                source_domain="jobs.example.com",
                jd_text="Need Python and machine learning for algorithm engineering roles.",
                inspected_urls=[payload.source_url],
            )

    async def fake_count(self, _client, _keyword, year):
        return (2 if year == 2026 else 0), True

    monkeypatch.setattr(job_fetcher, "datetime_now_year", lambda: 2026)
    monkeypatch.setattr(job_fetcher, "PublicJobFetcher", FakePublicJobFetcher)
    monkeypatch.setattr(PublicJobTrendFetcher, "_count_public_results", fake_count)

    result = await PublicJobTrendFetcher().fetch(
        keyword="算法工程师",
        years=2,
        source_url="https://jobs.example.com/detail/123",
    )

    assert result.source_url == "https://jobs.example.com/detail/123"
    assert [point.model_dump() for point in result.points] == [
        {"year": 2025, "count": 0},
        {"year": 2026, "count": 3},
    ]
