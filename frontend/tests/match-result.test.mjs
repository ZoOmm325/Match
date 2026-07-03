import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("match result renders at most five recommendation cards", async () => {
  const source = await read("components/MatchResult.tsx");

  assert.match(source, /recommendations\.slice\(0, 5\)\.map/);
  assert.match(source, /<MajorCard/);
  assert.match(source, /defaultExpanded=\{index === 0\}/);
  assert.match(source, /aria-live="polite"/);
});

test("major card shows score reason skills and expandable details", async () => {
  const source = await read("components/MajorCard.tsx");

  assert.match(source, /recommendation\.major_name/);
  assert.match(source, /recommendation\.recommendation_reason/);
  assert.match(source, /label="综合匹配得分"/);
  assert.match(source, /label="技能相似度"/);
  assert.match(source, /label="技能覆盖率"/);
  assert.match(source, /label="就业方向匹配"/);
  assert.match(source, /aria-expanded=\{expanded\}/);
  assert.match(source, /expanded \? "收起详情" : "查看详情"/);
});

test("skill tags distinguish matched and missing skills", async () => {
  const card = await read("components/MajorCard.tsx");
  const tag = await read("components/SkillTag.tsx");

  assert.match(card, /label="匹配技能"/);
  assert.match(card, /status="matched"/);
  assert.match(card, /label="待补充技能"/);
  assert.match(card, /status="missing"/);
  assert.match(tag, /bg-emerald-50 text-emerald-700/);
  assert.match(tag, /bg-slate-100 text-slate-600/);
});

test("score bar clamps values and exposes progress semantics", async () => {
  const source = await read("components/ScoreBar.tsx");

  assert.match(source, /Math\.max\(0, Math\.min\(1, value\)\)/);
  assert.match(source, /role="progressbar"/);
  assert.match(source, /aria-valuemin=\{0\}/);
  assert.match(source, /aria-valuemax=\{100\}/);
  assert.match(source, /aria-valuenow=\{percentage\}/);
});
