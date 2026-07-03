import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("loading and empty state expose accessible reusable states", async () => {
  const loading = await read("components/ui/Loading.tsx");
  const emptyState = await read("components/ui/EmptyState.tsx");

  assert.match(loading, /role="status"/);
  assert.match(loading, /aria-label=\{label\}/);
  assert.match(loading, /animate-spin/);
  assert.match(emptyState, /title: string/);
  assert.match(emptyState, /description: string/);
  assert.match(emptyState, /action\?: ReactNode/);
});

test("error boundary logs failures and offers recovery", async () => {
  const source = await read("components/ui/ErrorBoundary.tsx");

  assert.match(source, /getDerivedStateFromError/);
  assert.match(source, /componentDidCatch/);
  assert.match(source, /usePathname\(\)/);
  assert.match(source, /<ErrorBoundary key=\{pathname\}>/);
  assert.match(source, /console\.error\("Unhandled frontend error"/);
  assert.match(source, /role="alert"/);
  assert.match(source, /window\.location\.reload\(\)/);
});

test("toast provider supports variants, dismissal, and live announcements", async () => {
  const source = await read("components/ui/Toast.tsx");

  assert.match(source, /export function ToastProvider/);
  assert.match(source, /export function useToast/);
  assert.match(source, /type ToastVariant = "success" \| "error" \| "info"/);
  assert.match(source, /window\.setTimeout/);
  assert.match(source, /aria-label="消息通知"/);
  assert.match(source, /aria-label="关闭通知"/);
});

test("pagination exposes navigation semantics and disabled states", async () => {
  const source = await read("components/ui/Pagination.tsx");

  assert.match(source, /aria-label=\{ariaLabel\}/);
  assert.match(source, /disabled=\{!hasPrevious\}/);
  assert.match(source, /disabled=\{!hasNext\}/);
  assert.match(source, /onClick=\{onPrevious\}/);
  assert.match(source, /onClick=\{onNext\}/);
  assert.match(source, /aria-live="polite"/);
});

test("global layout mounts shared feedback and responsive shell", async () => {
  const layout = await read("app/layout.tsx");
  const styles = await read("app/globals.css");

  assert.match(layout, /<ToastProvider>/);
  assert.match(layout, /<ErrorBoundary>/);
  assert.match(layout, /<footer/);
  assert.match(layout, /grid grid-cols-4/);
  assert.match(styles, /min-width: 320px/);
  assert.match(styles, /prefers-reduced-motion: reduce/);
  assert.match(styles, /--page-header-height/);
});

test("list and result pages consume the shared UI components", async () => {
  const history = await read("app/history/page.tsx");
  const majors = await read("app/majors/page.tsx");
  const results = await read("components/MatchResult.tsx");

  assert.match(history, /import Pagination from "@\/components\/ui\/Pagination"/);
  assert.match(history, /<Pagination/);
  assert.match(majors, /import Pagination from "@\/components\/ui\/Pagination"/);
  assert.match(majors, /<Pagination/);
  assert.match(results, /<Loading label="正在生成匹配结果"/);
  assert.match(results, /<EmptyState/);
});
