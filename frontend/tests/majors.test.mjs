import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("majors page loads filtered paginated data", async () => {
  const source = await read("app/majors/page.tsx");

  assert.match(source, /const PAGE_SIZE = 12/);
  assert.match(source, /await getMajors\(\{/);
  assert.match(source, /category: category === "全部" \? undefined : category/);
  assert.match(source, /keyword: keyword \|\| undefined/);
  assert.match(source, /setKeyword\(query\.trim\(\)\)/);
  assert.match(source, /value - PAGE_SIZE/);
  assert.match(source, /value \+ PAGE_SIZE/);
});

test("major search provides category tabs and keyword controls", async () => {
  const source = await read("components/MajorSearch.tsx");

  assert.match(source, /const CATEGORIES = \[/);
  assert.match(source, /"工学"/);
  assert.match(source, /"管理学"/);
  assert.match(source, /role="tablist"/);
  assert.match(source, /role="tab"/);
  assert.match(source, /aria-selected=\{selected\}/);
  assert.match(source, /placeholder="输入专业名称、代码或关键词"/);
});

test("major list cards show required fields and detail link", async () => {
  const source = await read("components/MajorList.tsx");

  assert.match(source, /major\.name/);
  assert.match(source, /major\.code/);
  assert.match(source, /major\.category/);
  assert.match(source, /major\.description/);
  assert.match(source, /href=\{`\/majors\/\$\{major\.id\}`\}/);
  assert.match(source, /查看专业详情/);
  assert.match(source, /没有找到相关专业/);
});

test("major detail loads curriculum and training information", async () => {
  const source = await read("app/majors/[id]/page.tsx");

  assert.match(source, /getMajor\(majorId\)/);
  assert.match(source, /培养目标与专业简介/);
  assert.match(source, /课程体系/);
  assert.match(source, /core: "核心课程"/);
  assert.match(source, /practice: "实践教学"/);
  assert.match(source, /normalizeCurriculum/);
  assert.match(source, /href="\/majors"/);
});

test("global navigation exposes major browsing", async () => {
  const layout = await read("app/layout.tsx");

  assert.match(layout, /href: "\/majors", label: "专业浏览"/);
});
