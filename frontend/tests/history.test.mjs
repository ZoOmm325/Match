import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("history page loads paginated JDs and match counts only", async () => {
  const page = await read("app/history/page.tsx");

  assert.match(page, /const PAGE_SIZE = 10/);
  assert.match(page, /await getJds\(\{ limit: PAGE_SIZE, offset \}\)/);
  assert.match(page, /await Promise\.all\(/);
  assert.match(page, /await getMatchResult\(item\.id\)/);
  assert.match(page, /matchedMajorCount: match\.recommendations\.length/);
  assert.doesNotMatch(page, /getJobMarketTrend/);
  assert.doesNotMatch(page, /JobMarketTrendChart/);
  assert.match(page, /setOffset\(\(value\) => Math\.max\(0, value - PAGE_SIZE\)\)/);
  assert.match(page, /setOffset\(\(value\) => value \+ PAGE_SIZE\)/);
});

test("trends page waits for user input and accepts a public detail URL", async () => {
  const page = await read("app/trends/page.tsx");

  assert.match(page, /const \[keyword, setKeyword\] = useState\(""\)/);
  assert.match(page, /const \[loading, setLoading\] = useState\(false\)/);
  assert.match(page, /if \(submittedKeyword\.trim\(\)\)/);
  assert.match(page, /getJobMarketTrend\(normalized, 5, publicUrl \|\| undefined\)/);
  assert.match(page, /<JobMarketTrendChart data=\{trend\} loading=\{loading\} error=\{error\}/);
  assert.match(page, /id="job-trend-keyword"/);
  assert.match(page, /id="job-trend-source-url"/);
  assert.match(page, /公开岗位详情页 URL/);
  assert.match(page, /岗位市场趋势/);
});

test("job market trend chart renders an accessible line chart", async () => {
  const source = await read("components/JobMarketTrendChart.tsx");

  assert.match(source, /aria-label=/);
  assert.match(source, /<polyline/);
  assert.match(source, /points\.map/);
  assert.match(source, /point\.year/);
});

test("history list exposes loading and empty states", async () => {
  const source = await read("components/HistoryList.tsx");

  assert.match(source, /<Loading label=/);
  assert.match(source, /<EmptyState/);
  assert.match(source, /records\.map/);
  assert.match(source, /<HistoryItem/);
});

test("history item shows required fields and links to detail", async () => {
  const source = await read("components/HistoryItem.tsx");

  assert.match(source, /record\.title/);
  assert.match(source, /record\.created_at/);
  assert.match(source, /record\.matchedMajorCount/);
  assert.match(source, /record\.skill_count/);
  assert.match(source, /href=\{`\/history\/\$\{record\.id\}`\}/);
});

test("history detail loads JD and full match results", async () => {
  const source = await read("app/history/[id]/page.tsx");

  assert.match(source, /useParams<\{ id: string \}>/);
  assert.match(source, /getJd\(jdId\)/);
  assert.match(source, /getMatchResult\(jdId\)/);
  assert.match(source, /<MatchResult loading=\{loading\} result=\{result\}/);
  assert.match(source, /href="\/history"/);
});
