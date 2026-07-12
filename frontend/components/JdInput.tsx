"use client";

import { useState } from "react";

interface ExampleJob {
  id: string;
  title: string;
  summary: string;
  jd: string;
}

interface JdInputProps {
  value: string;
  maxLength: number;
  examples: ExampleJob[];
  selectedExampleId?: string | null;
  error?: string;
  disabled?: boolean;
  fetchingJd?: boolean;
  onChange: (value: string) => void;
  onUseExample: (exampleId: string) => void;
  onFetchPublicJd: (keyword: string, sourceUrl?: string) => Promise<unknown>;
}

function searchExamples(examples: ExampleJob[], query: string) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) {
    return examples;
  }

  return examples.filter((example) => {
    const searchableText = `${example.title} ${example.summary} ${example.jd}`.toLocaleLowerCase();
    return searchableText.includes(normalizedQuery);
  });
}

export default function JdInput({
  value,
  maxLength,
  examples,
  selectedExampleId = null,
  error,
  disabled = false,
  fetchingJd = false,
  onChange,
  onUseExample,
  onFetchPublicJd,
}: JdInputProps) {
  const [examplesOpen, setExamplesOpen] = useState(false);
  const [jobSearch, setJobSearch] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [fetchError, setFetchError] = useState("");
  const selectedExample = examples.find((example) => example.id === selectedExampleId);
  const visibleExamples = searchExamples(examples, jobSearch);

  const handleSelectExample = (exampleId: string) => {
    onUseExample(exampleId);
    setExamplesOpen(false);
  };

  const handleSearchChange = (nextSearch: string) => {
    setJobSearch(nextSearch);
    setFetchError("");
    const [firstMatch] = searchExamples(examples, nextSearch);
    if (nextSearch.trim() && firstMatch && firstMatch.id !== selectedExampleId) {
      onUseExample(firstMatch.id);
    }
  };

  const handleFetchPublicJd = async () => {
    const keyword = jobSearch.trim();
    const publicUrl = sourceUrl.trim();
    if (!keyword) {
      setFetchError("请先输入岗位关键词。");
      return;
    }
    setFetchError("");
    try {
      await onFetchPublicJd(keyword, publicUrl || undefined);
    } catch (error) {
      setFetchError(error instanceof Error ? error.message : "联网搜索 JD 失败，请稍后重试。");
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <label htmlFor="jd-text" className="text-sm font-semibold text-slate-950">
            岗位描述
          </label>
          <p className="mt-1 text-sm text-slate-500">
            粘贴完整招聘 JD，系统将抽取技能并推荐相关大学专业。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExamplesOpen((open) => !open)}
          disabled={disabled}
          aria-expanded={examplesOpen}
          aria-controls="example-jd-panel"
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          示例 JD
        </button>
      </div>

      {examplesOpen ? (
        <div
          id="example-jd-panel"
          className="rounded-lg border border-sky-100 bg-sky-50/60 p-3 shadow-sm"
        >
          <label htmlFor="example-job-search" className="text-xs font-semibold text-sky-800">
            搜索岗位，自动填入对应 JD
          </label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              id="example-job-search"
              type="search"
              value={jobSearch}
              disabled={disabled || fetchingJd}
              onChange={(event) => handleSearchChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleFetchPublicJd();
                }
              }}
              placeholder="例如：财务、机械、教师、运营、人力"
              className="h-10 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:bg-slate-100"
            />
            <button
              type="button"
              onClick={() => void handleFetchPublicJd()}
              disabled={disabled || fetchingJd || !jobSearch.trim()}
              className="inline-flex h-10 items-center justify-center rounded-md bg-sky-700 px-3 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {fetchingJd ? "正在联网搜索" : "联网搜索 JD"}
            </button>
          </div>
          <input
            type="url"
            value={sourceUrl}
            disabled={disabled || fetchingJd}
            onChange={(event) => {
              setSourceUrl(event.target.value);
              setFetchError("");
            }}
            placeholder="可选：粘贴公开岗位详情页 URL，可提高抓取成功率"
            className="mt-2 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:cursor-not-allowed disabled:bg-slate-100"
          />
          <p className="mt-2 text-xs leading-5 text-slate-500">
            只抓取公开页面；需要登录、验证码或 robots 禁止访问的页面会被跳过。
          </p>
          {fetchError ? (
            <p role="alert" className="mt-2 text-xs font-medium text-red-600">
              {fetchError}
            </p>
          ) : null}

          <p className="mb-2 mt-3 text-xs font-semibold text-sky-800">选择一个常见岗位</p>
          {visibleExamples.length ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {visibleExamples.map((example) => {
                const isSelected = example.id === selectedExampleId;

                return (
                  <button
                    key={example.id}
                    type="button"
                    onClick={() => handleSelectExample(example.id)}
                    disabled={disabled}
                    className={`rounded-md border p-3 text-left transition hover:-translate-y-0.5 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-50 ${
                      isSelected
                        ? "border-sky-500 bg-white text-sky-950 shadow-sm"
                        : "border-slate-200 bg-white text-slate-800 hover:border-sky-300"
                    }`}
                  >
                    <span className="block text-sm font-semibold">{example.title}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">{example.summary}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="rounded-md border border-dashed border-slate-300 bg-white px-3 py-2 text-sm text-slate-500">
              暂未命中内置示例，可换一个岗位关键词，或直接粘贴真实 JD。
            </p>
          )}
        </div>
      ) : null}

      {selectedExample ? (
        <div
          key={selectedExample.id}
          aria-live="polite"
          className="example-jd-rise rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
        >
          已填入「{selectedExample.title}」对应 JD，内容已向上加载到输入框。
        </div>
      ) : null}

      <textarea
        id="jd-text"
        value={value}
        maxLength={maxLength}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "jd-error jd-count" : "jd-count"}
        onChange={(event) => onChange(event.target.value)}
        placeholder="例如：负责后端服务开发，要求熟悉 Python、FastAPI、PostgreSQL、Docker，具备机器学习项目经验……"
        className={`min-h-72 w-full resize-y rounded-md border bg-white p-4 text-sm leading-6 text-slate-800 outline-none transition focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-100 ${
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-100"
            : "border-slate-300 focus:border-sky-500 focus:ring-sky-100"
        }`}
      />

      <div className="flex min-h-5 items-start justify-between gap-4 text-xs">
        <p id="jd-error" role="alert" className="font-medium text-red-600">
          {error ?? ""}
        </p>
        <p
          id="jd-count"
          className={`shrink-0 ${value.length >= maxLength ? "text-red-600" : "text-slate-500"}`}
        >
          {value.length.toLocaleString()} / {maxLength.toLocaleString()}
        </p>
      </div>
    </div>
  );
}
