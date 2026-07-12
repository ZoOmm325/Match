"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import HistoryList from "@/components/HistoryList";
import type { HistoryRecord } from "@/components/HistoryItem";
import JobMarketTrendChart from "@/components/JobMarketTrendChart";
import Pagination from "@/components/ui/Pagination";
import {
  ApiError,
  getJds,
  getJobMarketTrend,
  getMatchResult,
  type JobMarketTrendData,
} from "@/lib/api";

const PAGE_SIZE = 10;

export default function HistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [trendKeyword, setTrendKeyword] = useState("Backend Engineer");
  const [submittedTrendKeyword, setSubmittedTrendKeyword] = useState("Backend Engineer");
  const [trend, setTrend] = useState<JobMarketTrendData | null>(null);
  const [trendLoading, setTrendLoading] = useState(true);
  const [trendError, setTrendError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getJds({ limit: PAGE_SIZE, offset });
      const recordsWithMatchCount = await Promise.all(
        data.items.map(async (item) => {
          try {
            const match = await getMatchResult(item.id);
            return {
              ...item,
              matchedMajorCount: match.recommendations.length,
            };
          } catch {
            return { ...item, matchedMajorCount: 0 };
          }
        })
      );
      setRecords(recordsWithMatchCount);
      setTotal(data.total);
    } catch (requestError) {
      setRecords([]);
      setError(
        requestError instanceof ApiError ? requestError.message : "历史记录加载失败，请稍后重试。"
      );
    } finally {
      setLoading(false);
    }
  }, [offset]);

  const loadTrend = useCallback(async () => {
    const keyword = submittedTrendKeyword.trim();
    if (keyword.length < 2) {
      setTrend(null);
      setTrendError("请输入至少 2 个字符的岗位名称。");
      setTrendLoading(false);
      return;
    }
    setTrendLoading(true);
    setTrendError("");
    try {
      setTrend(await getJobMarketTrend(keyword, 5));
    } catch (requestError) {
      setTrend(null);
      setTrendError(
        requestError instanceof ApiError ? requestError.message : "岗位年度趋势数据加载失败，请稍后重试。"
      );
    } finally {
      setTrendLoading(false);
    }
  }, [submittedTrendKeyword]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory, reloadToken]);

  useEffect(() => {
    void loadTrend();
  }, [loadTrend, reloadToken]);

  const handleTrendSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmittedTrendKeyword(trendKeyword);
  };

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasPrevious = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-sky-700">历史匹配</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950">
            历史匹配记录
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            查看已经提交的岗位描述及对应专业推荐结果。
          </p>
        </div>
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
          共 <span className="font-semibold text-slate-950">{total}</span> 条记录
        </div>
      </header>

      {error ? (
        <div
          role="alert"
          className="mb-5 flex flex-col gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setReloadToken((value) => value + 1)}
            className="self-start rounded-md border border-red-300 bg-white px-3 py-1.5 font-semibold text-red-700 hover:bg-red-100 sm:self-auto"
          >
            重新加载
          </button>
        </div>
      ) : null}

      <form
        onSubmit={handleTrendSubmit}
        className="mb-4 flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-end"
      >
        <div className="min-w-0 flex-1">
          <label htmlFor="job-trend-keyword" className="text-sm font-semibold text-slate-950">
            岗位名称
          </label>
          <input
            id="job-trend-keyword"
            type="search"
            value={trendKeyword}
            onChange={(event) => setTrendKeyword(event.target.value)}
            placeholder="例如：算法工程师、后端工程师、机械设计工程师"
            className="mt-2 h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
        </div>
        <button
          type="submit"
          disabled={trendLoading || trendKeyword.trim().length < 2}
          className="inline-flex h-10 items-center justify-center rounded-md bg-sky-700 px-4 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          查看趋势
        </button>
      </form>

      <JobMarketTrendChart data={trend} loading={trendLoading} error={trendError} />

      <HistoryList records={records} loading={loading} />

      {!loading && !error && total > 0 ? (
        <Pagination
          ariaLabel="历史记录分页"
          currentPage={currentPage}
          totalPages={totalPages}
          hasPrevious={hasPrevious}
          hasNext={hasNext}
          onPrevious={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
          onNext={() => setOffset((value) => value + PAGE_SIZE)}
        />
      ) : null}
    </section>
  );
}
