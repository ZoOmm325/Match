"use client";

import { useCallback, useEffect, useState } from "react";
import HistoryList from "@/components/HistoryList";
import type { HistoryRecord } from "@/components/HistoryItem";
import Pagination from "@/components/ui/Pagination";
import { ApiError, getJds, getMatchResult } from "@/lib/api";

const PAGE_SIZE = 10;

export default function HistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
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

  useEffect(() => {
    void loadHistory();
  }, [loadHistory, reloadToken]);

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
