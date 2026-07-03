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

test("homepage supports example input and result states", async () => {
  const page = await read("app/page.tsx");

  assert.match(page, /const EXAMPLE_JD =/);
  assert.match(page, /setJdText\(EXAMPLE_JD\)/);
  assert.match(page, /import MatchResult from "@\/components\/MatchResult"/);
  assert.match(page, /<MatchResult loading=\{loading\} result=\{result\}/);
  assert.match(page, /匹配请求失败，请稍后重试/);
});

test("input and button expose accessible loading and error states", async () => {
  const input = await read("components/JdInput.tsx");
  const button = await read("components/MatchButton.tsx");

  assert.match(input, /aria-invalid=\{Boolean\(error\)\}/);
  assert.match(input, /role="alert"/);
  assert.match(input, /maxLength=\{maxLength\}/);
  assert.match(input, /填入示例 JD/);
  assert.match(button, /aria-busy=\{loading\}/);
  assert.match(button, /disabled=\{disabled \|\| loading\}/);
  assert.match(button, /正在分析并匹配/);
});
