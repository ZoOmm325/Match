import Link from "next/link";
import type { JdListItem } from "@/lib/api";

export interface HistoryRecord extends JdListItem {
  matchedMajorCount: number;
}

interface HistoryItemProps {
  record: HistoryRecord;
}

const dateFormatter = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export default function HistoryItem({ record }: HistoryItemProps) {
  const title = record.title?.trim() || "未命名岗位";
  const company = record.company?.trim();
  const submittedAt = dateFormatter.format(new Date(record.created_at));

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-base font-semibold text-slate-950">{title}</h2>
            {company ? (
              <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                {company}
              </span>
            ) : null}
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{record.raw_text}</p>
          <p className="mt-2 text-xs text-slate-500">提交于 {submittedAt}</p>
        </div>

        <div className="flex shrink-0 items-center justify-between gap-5 border-t border-slate-100 pt-4 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0">
          <div className="text-center">
            <p className="text-xl font-semibold text-slate-950">{record.matchedMajorCount}</p>
            <p className="mt-1 text-xs text-slate-500">匹配专业</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-semibold text-slate-950">{record.skill_count}</p>
            <p className="mt-1 text-xs text-slate-500">提取技能</p>
          </div>
          <Link
            href={`/history/${record.id}`}
            className="inline-flex min-h-10 items-center rounded-md bg-sky-700 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
          >
            查看详情
          </Link>
        </div>
      </div>
    </article>
  );
}
