import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("package scripts expose Next.js development commands", async () => {
  const pkg = JSON.parse(await read("package.json"));

  assert.equal(pkg.scripts.dev, "next dev");
  assert.equal(pkg.scripts.build, "next build");
  assert.equal(pkg.scripts.typecheck, "tsc --noEmit");
  assert.equal(pkg.dependencies.next.startsWith("^15."), true);
  assert.equal(pkg.devDependencies.tailwindcss.startsWith("^3."), true);
});

test("app router pages keep one match entry point", async () => {
  const layout = await read("app/layout.tsx");
  const home = await read("app/page.tsx");
  const match = await read("app/match/page.tsx");
  const history = await read("app/history/page.tsx");

  assert.match(layout, /href: "\/", label: "开始匹配"/);
  assert.doesNotMatch(layout, /href: "\/match"/);
  assert.match(layout, /href: "\/history"/);
  assert.match(home, /开始匹配/);
  assert.match(match, /redirect\("\/"\)/);
  assert.match(history, /历史匹配记录/);
});

test("tailwind is wired into the app", async () => {
  const config = await read("tailwind.config.ts");
  const globals = await read("app/globals.css");

  assert.match(config, /\.\/app\/\*\*\/\*\.\{js,ts,jsx,tsx,mdx\}/);
  assert.match(globals, /@tailwind base;/);
  assert.match(globals, /@tailwind components;/);
  assert.match(globals, /@tailwind utilities;/);
});

test("next build is configured for Docker standalone output", async () => {
  const config = await read("next.config.mjs");

  assert.match(config, /output:\s*"standalone"/);
});
