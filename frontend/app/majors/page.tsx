"use client";

import { useCallback, useEffect, useState } from "react";
import MajorList from "@/components/MajorList";
import MajorSearch from "@/components/MajorSearch";
import Pagination from "@/components/ui/Pagination";
import { ApiError, getMajors, type Major } from "@/lib/api";

const PAGE_SIZE = 12;

export default function MajorsPage() {
  const [majors, setMajors] = useState<Major[]>([]);
  const [query, setQuery] = useState("");
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("全部");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const loadMajors = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getMajors({
        category: category === "全部" ? undefined : category,
        keyword: keyword || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setMajors(data.items);
      setTotal(data.total);
    } catch (requestError) {
      setMajors([]);
      setError(
        requestError instanceof ApiError ? requestError.message : "专业列表加载失败，请稍后重试。"
      );
    } finally {
      setLoading(false);
    }
  }, [category, keyword, offset]);

  useEffect(() => {
    void loadMajors();
  }, [loadMajors, reloadToken]);

  const handleCategoryChange = (value: string) => {
    setCategory(value);
    setOffset(0);
  };

  const handleSearch = () => {
    setKeyword(query.trim());
    setOffset(0);
  };

  const handleClear = () => {
    setQuery("");
    setKeyword("");
    setOffset(0);
  };

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasPrevious = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
      <header className="mb-7">
        <p className="text-sm font-semibold text-sky-700">专业知识库</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950">浏览大学专业</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          按学科门类筛选，或搜索专业名称、代码和培养方向。
        </p>
      </header>

      <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <MajorSearch
          query={query}
          category={category}
          loading={loading}
          onQueryChange={setQuery}
          onCategoryChange={handleCategoryChange}
          onSubmit={handleSearch}
          onClear={handleClear}
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          共找到 <span className="font-semibold text-slate-950">{total}</span> 个专业
          {keyword ? (
            <span>
              ，关键词“<span className="font-medium text-slate-900">{keyword}</span>”
            </span>
          ) : null}
        </p>
        {category !== "全部" ? (
          <span className="rounded-md bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
            {category}
          </span>
        ) : null}
      </div>

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

      <MajorList majors={majors} loading={loading} />

      {!loading && !error && total > 0 ? (
        <Pagination
          ariaLabel="专业列表分页"
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
