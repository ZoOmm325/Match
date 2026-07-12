import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("homepage composes the JD input and match button components", async () => {
  const page = await read("app/page.tsx");

  assert.match(page, /import JdInput from "@\/components\/JdInput"/);
  assert.match(page, /import MatchButton from "@\/components\/MatchButton"/);
  assert.match(page, /<JdInput/);
  assert.match(page, /<MatchButton/);
});

test("homepage validates JD text and calls the match API", async () => {
  const page = await read("app/page.tsx");

  assert.match(page, /const MIN_JD_LENGTH = 20/);
  assert.match(page, /const MAX_JD_LENGTH = 20_000/);
  assert.match(page, /if \(!normalized\)/);
  assert.match(page, /normalized\.length < MIN_JD_LENGTH/);
  assert.match(page, /await submitJD\(normalized/);
  assert.match(page, /setLoading\(true\)/);
  assert.match(page, /finally \{\s*setLoading\(false\)/);
});

test("homepage supports diverse example job selection and result states", async () => {
  const page = await read("app/page.tsx");

  assert.match(page, /const EXAMPLE_JOBS =/);
  assert.match(page, /算法工程师/);
  assert.match(page, /财务分析师/);
  assert.match(page, /机械设计工程师/);
  assert.match(page, /临床研究专员/);
  assert.match(page, /英语教师/);
  assert.match(page, /新媒体运营/);
  assert.match(page, /人力资源专员/);
  assert.match(page, /setJdText\(example\.jd\)/);
  assert.match(page, /fetchPublicJd/);
  assert.match(page, /source_url: sourceUrl\?\.trim\(\) \|\| undefined/);
  assert.match(page, /setJdText\(fetched\.jd_text\)/);
  assert.match(page, /selectedExampleId=\{selectedExampleId\}/);
  assert.match(page, /import MatchResult from "@\/components\/MatchResult"/);
  assert.match(page, /<MatchResult loading=\{loading\} result=\{result\}/);
  assert.match(page, /匹配请求失败，请稍后重试/);
});

test("input searches example jobs and auto-fills matching JD text", async () => {
  const input = await read("components/JdInput.tsx");

  assert.match(input, /function searchExamples/);
  assert.match(input, /搜索岗位，自动填入对应 JD/);
  assert.match(input, /联网搜索 JD/);
  assert.match(input, /正在联网搜索/);
  assert.match(input, /onFetchPublicJd\(keyword, publicUrl \|\| undefined\)/);
  assert.match(input, /type="search"/);
  assert.match(input, /type="url"/);
  assert.match(input, /公开岗位详情页 URL/);
  assert.match(input, /robots 禁止访问/);
  assert.match(input, /handleSearchChange/);
  assert.match(input, /onUseExample\(firstMatch\.id\)/);
  assert.match(input, /visibleExamples\.map/);
  assert.match(input, /暂未命中内置示例/);
});

test("input and button expose accessible loading and error states", async () => {
  const input = await read("components/JdInput.tsx");
  const button = await read("components/MatchButton.tsx");

  assert.match(input, /aria-invalid=\{Boolean\(error\)\}/);
  assert.match(input, /aria-expanded=\{examplesOpen\}/);
  assert.match(input, /aria-live="polite"/);
  assert.match(input, /role="alert"/);
  assert.match(input, /maxLength=\{maxLength\}/);
  assert.match(input, /示例 JD/);
  assert.match(input, /选择一个常见岗位/);
  assert.match(input, /example-jd-rise/);
  assert.match(button, /aria-busy=\{loading\}/);
  assert.match(button, /disabled=\{disabled \|\| loading\}/);
  assert.match(button, /正在分析并匹配/);
});
