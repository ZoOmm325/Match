import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("api client exposes typed backend operations", async () => {
  const source = await read("lib/api.ts");

  for (const operation of [
    "submitJD",
    "matchBySkills",
    "getMatchResult",
    "getJds",
    "getJd",
    "deleteJd",
    "getMajors",
    "getMajor",
    "searchMajors",
    "getSkills",
    "getSkill",
    "getSkillCategories",
  ]) {
    assert.match(source, new RegExp(`export async function ${operation}\\(`));
  }
});

test("api endpoint mappings match backend routes", async () => {
  const source = await read("lib/api.ts");

  assert.match(source, /apiRequest<MatchResponseData>\(\s*"\/match"/);
  assert.match(source, /apiRequest<MatchResponseData>\(\s*"\/match\/by-skills"/);
  assert.match(source, /`\/match\/\$\{encodeURIComponent\(jdId\)\}`/);
  assert.match(source, /withQuery\("\/majors\/search"/);
  assert.match(source, /withQuery\("\/skills"/);
  assert.match(source, /apiRequest<SkillCategoriesData>\(\s*"\/skills\/categories"/);
});

test("api client uses configured base URL and centralized errors", async () => {
  const source = await read("lib/api.ts");

  assert.match(source, /process\.env\.NEXT_PUBLIC_API_BASE_URL/);
  assert.match(source, /export class ApiError extends Error/);
  assert.match(source, /if \(!response\.ok \|\| payload\.code !== 0\)/);
  assert.match(source, /Server returned an invalid JSON response/);
  assert.match(source, /does not match the API contract/);
  assert.match(source, /value\.recommendations\.every\(isMatchRecommendation\)/);
  for (const field of [
    "major_id",
    "major_code",
    "skill_similarity_score",
    "skill_coverage_score",
    "employment_alignment_score",
    "score_details",
  ]) {
    assert.match(source, new RegExp(`value\\.${field}`));
  }
  assert.doesNotMatch(source, /payload\.data as T/);
  assert.match(source, /Network request failed/);
});

test("api client serializes JSON and URL query parameters safely", async () => {
  const source = await read("lib/api.ts");

  assert.match(source, /headers\.set\("Accept", "application\/json"\)/);
  assert.match(source, /headers\.set\("Content-Type", "application\/json"\)/);
  assert.match(source, /new URLSearchParams\(\)/);
  assert.match(source, /search\.set\(key, String\(queryValue\)\)/);
  assert.match(source, /encodeURIComponent\(majorId\)/);
  assert.match(source, /encodeURIComponent\(skillId\)/);
});
