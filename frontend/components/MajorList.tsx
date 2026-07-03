import Link from "next/link";
import EmptyState from "@/components/ui/EmptyState";
import Loading from "@/components/ui/Loading";
import type { Major } from "@/lib/api";

interface MajorListProps {
  majors: Major[];
  loading: boolean;
}

export default function MajorList({ majors, loading }: MajorListProps) {
  if (loading) {
    return <Loading label="正在加载专业列表" />;
  }

  if (!majors.length) {
    return <EmptyState title="没有找到相关专业" description="尝试更换关键词或选择其他学科门类。" />;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {majors.map((major) => (
        <article
          key={major.id}
          className="flex min-h-60 flex-col rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-slate-950">{major.name}</h2>
              <p className="mt-1 text-xs text-slate-500">{major.code || "暂无专业代码"}</p>
            </div>
            <span className="shrink-0 rounded-md bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
              {major.category || "未分类"}
            </span>
          </div>

          <p className="mt-4 line-clamp-4 text-sm leading-6 text-slate-600">
            {major.description || "暂无专业简介。"}
          </p>

          <div className="mt-auto border-t border-slate-100 pt-4">
            <Link
              href={`/majors/${major.id}`}
              className="inline-flex min-h-10 items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
            >
              查看专业详情
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
