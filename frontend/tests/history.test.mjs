import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("history page loads paginated JDs and match counts", async () => {
  const page = await read("app/history/page.tsx");

  assert.match(page, /const PAGE_SIZE = 10/);
  assert.match(page, /await getJds\(\{ limit: PAGE_SIZE, offset \}\)/);
  assert.match(page, /await Promise\.all\(/);
  assert.match(page, /await getMatchResult\(item\.id\)/);
  assert.match(page, /matchedMajorCount: match\.recommendations\.length/);
  assert.match(page, /setOffset\(\(value\) => Math\.max\(0, value - PAGE_SIZE\)\)/);
  assert.match(page, /setOffset\(\(value\) => value \+ PAGE_SIZE\)/);
});

test("history list exposes loading and empty states", async () => {
  const source = await read("components/HistoryList.tsx");

  assert.match(source, /<Loading label="正在加载历史记录"/);
  assert.match(source, /<EmptyState/);
  assert.match(source, /暂无历史记录/);
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
  assert.match(source, /查看详情/);
});

test("history detail loads JD and full match results", async () => {
  const source = await read("app/history/[id]/page.tsx");

  assert.match(source, /useParams<\{ id: string \}>/);
  assert.match(source, /getJd\(jdId\)/);
  assert.match(source, /getMatchResult\(jdId\)/);
  assert.match(source, /<MatchResult loading=\{loading\} result=\{result\}/);
  assert.match(source, /href="\/history"/);
});
