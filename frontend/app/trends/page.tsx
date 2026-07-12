"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import JobMarketTrendChart from "@/components/JobMarketTrendChart";
import { ApiError, getJobMarketTrend, type JobMarketTrendData } from "@/lib/api";

export default function TrendsPage() {
  const [keyword, setKeyword] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const [submittedSourceUrl, setSubmittedSourceUrl] = useState("");
  const [trend, setTrend] = useState<JobMarketTrendData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadTrend = useCallback(async () => {
    const normalized = submittedKeyword.trim();
    const publicUrl = submittedSourceUrl.trim();
    if (normalized.length < 2) {
      setTrend(null);
      setError("请输入至少 2 个字符的岗位名称。");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");
    try {
      setTrend(await getJobMarketTrend(normalized, 5, publicUrl || undefined));
    } catch (requestError) {
      setTrend(null);
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "岗位趋势数据联网获取失败，请稍后重试。"
      );
    } finally {
      setLoading(false);
    }
  }, [submittedKeyword, submittedSourceUrl]);

  useEffect(() => {
    if (submittedKeyword.trim()) {
      void loadTrend();
    }
  }, [loadTrend, submittedKeyword]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmittedKeyword(keyword);
    setSubmittedSourceUrl(sourceUrl);
  };

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
      <header className="mb-7 max-w-3xl">
        <p className="text-sm font-semibold text-sky-700">岗位市场趋势</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950">
          查看某一岗位近几年的岗位数量变化
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          输入岗位名称后点击查看趋势。也可以粘贴公开岗位详情页 URL，补充一个可验证的公开样本。
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.2fr)_auto] lg:items-end"
      >
        <div className="min-w-0">
          <label htmlFor="job-trend-keyword" className="text-sm font-semibold text-slate-950">
            岗位名称
          </label>
          <input
            id="job-trend-keyword"
            type="search"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="例如：算法工程师、后端工程师"
            className="mt-2 h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
        </div>
        <div className="min-w-0">
          <label htmlFor="job-trend-source-url" className="text-sm font-semibold text-slate-950">
            公开岗位详情页 URL
          </label>
          <input
            id="job-trend-source-url"
            type="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder="可选：粘贴公开招聘详情页 URL"
            className="mt-2 h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
        </div>
        <button
          type="submit"
          disabled={loading || keyword.trim().length < 2}
          className="inline-flex h-10 items-center justify-center rounded-md bg-sky-700 px-4 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          查看趋势
        </button>
      </form>

      <JobMarketTrendChart data={trend} loading={loading} error={error} />
    </section>
  );
}
