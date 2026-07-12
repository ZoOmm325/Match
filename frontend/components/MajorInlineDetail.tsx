"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Loading from "@/components/ui/Loading";
import { ApiError, getMajor, type Major } from "@/lib/api";

const CURRICULUM_LABELS: Record<string, string> = {
  core: "核心课程",
  practice: "实践教学",
  elective: "专业选修",
  foundation: "基础课程",
};

interface MajorInlineDetailProps {
  majorId: number | null;
}

export default function MajorInlineDetail({ majorId }: MajorInlineDetailProps) {
  const [major, setMajor] = useState<Major | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (majorId === null) {
      setMajor(null);
      setLoading(false);
      setError("");
      return;
    }

    let active = true;
    const resolvedMajorId = majorId;

    async function loadMajor() {
      setLoading(true);
      setError("");
      try {
        const data = await getMajor(resolvedMajorId);
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
          setMajor(null);
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

  if (majorId === null) {
    return <p className="mt-3 text-sm text-slate-500">该推荐暂未关联到可查看的专业详情。</p>;
  }

  if (loading) {
    return <Loading label="正在加载专业详情" className="mt-3" />;
  }

  if (error) {
    return (
      <div
        role="alert"
        className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
      >
        {error}
      </div>
    );
  }

  if (!major) {
    return null;
  }

  return (
    <div className="mt-4 space-y-4">
      <section>
        <div className="flex flex-wrap items-center gap-2">
          <h5 className="text-sm font-semibold text-slate-900">专业简介</h5>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
            {major.category || "未分类"}
          </span>
        </div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">
          {major.description || "暂无专业培养目标和简介。"}
        </p>
      </section>

      <section>
        <h5 className="text-sm font-semibold text-slate-900">课程体系</h5>
        <Curriculum curriculum={major.curriculum} />
      </section>

      <Link
        href={`/majors/${major.id}`}
        className="inline-flex min-h-9 items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
      >
        打开完整详情
      </Link>
    </div>
  );
}

function Curriculum({ curriculum }: { curriculum: Major["curriculum"] }) {
  const sections = normalizeCurriculum(curriculum);
  if (!sections.length) {
    return <p className="mt-2 text-sm text-slate-500">暂无课程设置信息。</p>;
  }

  return (
    <div className="mt-2 space-y-3">
      {sections.map((section) => (
        <div key={section.key}>
          <p className="text-xs font-semibold text-slate-700">{section.title}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {section.items.map((item) => (
              <span
                key={`${section.key}-${item}`}
                className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-700"
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
