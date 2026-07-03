"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Loading from "@/components/ui/Loading";
import { ApiError, getMajor, type Major } from "@/lib/api";

const CURRICULUM_LABELS: Record<string, string> = {
  core: "核心课程",
  practice: "实践教学",
  elective: "专业选修",
  foundation: "基础课程",
};

export default function MajorDetailPage() {
  const params = useParams<{ id: string }>();
  const majorId = Number(params.id);
  const [major, setMajor] = useState<Major | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadMajor() {
      if (!Number.isInteger(majorId) || majorId < 1) {
        setError("无效的专业编号。");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");
      try {
        const data = await getMajor(majorId);
        if (active) {
          setMajor(data);
        }
      } catch (requestError) {
        if (active) {
          setError(
            requestError instanceof ApiError
              ? requestError.message
              : "专业详情加载失败，请稍后重试。"
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadMajor();
    return () => {
      active = false;
    };
  }, [majorId]);

  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
      <Link
        href="/majors"
        className="inline-flex min-h-10 items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        返回专业列表
      </Link>

      {error ? (
        <div
          role="alert"
          className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      ) : loading || !major ? (
        <Loading label="正在加载专业详情" className="mt-6" />
      ) : (
        <>
          <header className="mt-6 border-b border-slate-200 pb-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-sky-700">专业详情</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950 sm:text-4xl">
                  {major.name}
                </h1>
                <p className="mt-2 text-sm text-slate-500">专业代码：{major.code || "暂无"}</p>
              </div>
              <span className="rounded-md bg-sky-50 px-3 py-1.5 text-sm font-semibold text-sky-700">
                {major.category || "未分类"}
              </span>
            </div>
          </header>

          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(360px,1.2fr)]">
            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-base font-semibold text-slate-950">培养目标与专业简介</h2>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">
                {major.description || "暂无专业培养目标和简介。"}
              </p>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-base font-semibold text-slate-950">课程体系</h2>
              <Curriculum curriculum={major.curriculum} />
            </section>
          </div>
        </>
      )}
    </section>
  );
}

function Curriculum({ curriculum }: { curriculum: Major["curriculum"] }) {
  const sections = normalizeCurriculum(curriculum);
  if (!sections.length) {
    return <p className="mt-3 text-sm text-slate-500">暂无课程设置信息。</p>;
  }

  return (
    <div className="mt-4 space-y-5">
      {sections.map((section) => (
        <div key={section.key}>
          <h3 className="text-sm font-semibold text-slate-800">{section.title}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {section.items.map((item) => (
              <span
                key={`${section.key}-${item}`}
                className="rounded-md bg-slate-100 px-2.5 py-1.5 text-sm text-slate-700"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function normalizeCurriculum(
  curriculum: Major["curriculum"]
): Array<{ key: string; title: string; items: string[] }> {
  if (Array.isArray(curriculum)) {
    const items = curriculum.map(String).filter(Boolean);
    return items.length ? [{ key: "courses", title: "专业课程", items }] : [];
  }
  if (!curriculum || typeof curriculum !== "object") {
    return [];
  }

  return Object.entries(curriculum)
    .map(([key, value]) => {
      const items = Array.isArray(value)
        ? value.map(String).filter(Boolean)
        : value === null || value === undefined
          ? []
          : [String(value)];
      return {
        key,
        title: CURRICULUM_LABELS[key] || key,
        items,
      };
    })
    .filter((section) => section.items.length > 0);
}
