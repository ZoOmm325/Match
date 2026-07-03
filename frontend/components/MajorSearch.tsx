"use client";

const CATEGORIES = [
  "全部",
  "工学",
  "理学",
  "管理学",
  "经济学",
  "医学",
  "文学",
  "法学",
  "教育学",
  "艺术学",
  "农学",
] as const;

interface MajorSearchProps {
  query: string;
  category: string;
  loading?: boolean;
  onQueryChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
}

export default function MajorSearch({
  query,
  category,
  loading = false,
  onQueryChange,
  onCategoryChange,
  onSubmit,
  onClear,
}: MajorSearchProps) {
  return (
    <div className="space-y-5">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <label htmlFor="major-keyword" className="sr-only">
          搜索专业
        </label>
        <input
          id="major-keyword"
          type="search"
          value={query}
          maxLength={100}
          disabled={loading}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="输入专业名称、代码或关键词"
          className="min-h-11 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
        />
        <div className="flex gap-2">
          {query ? (
            <button
              type="button"
              onClick={onClear}
              disabled={loading}
              className="min-h-11 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              清除
            </button>
          ) : null}
          <button
            type="submit"
            disabled={loading}
            className="min-h-11 flex-1 rounded-md bg-sky-700 px-5 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:flex-none"
          >
            搜索
          </button>
        </div>
      </form>

      <div role="tablist" aria-label="按学科门类筛选" className="flex gap-2 overflow-x-auto pb-1">
        {CATEGORIES.map((item) => {
          const selected = item === category;
          return (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={selected}
              disabled={loading}
              onClick={() => onCategoryChange(item)}
              className={`min-h-9 shrink-0 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${
                selected
                  ? "bg-sky-700 text-white"
                  : "border border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {item}
            </button>
          );
        })}
      </div>
    </div>
  );
}
