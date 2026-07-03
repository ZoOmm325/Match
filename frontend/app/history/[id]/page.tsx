"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import MatchResult from "@/components/MatchResult";
import Loading from "@/components/ui/Loading";
import { ApiError, getJd, getMatchResult, type JdDetail, type MatchResponseData } from "@/lib/api";

export default function HistoryDetailPage() {
  const params = useParams<{ id: string }>();
  const jdId = Number(params.id);
  const [jd, setJd] = useState<JdDetail | null>(null);
  const [result, setResult] = useState<MatchResponseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadDetail() {
      if (!Number.isInteger(jdId) || jdId < 1) {
        setError("无效的历史记录编号。");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");
      try {
        const [jdData, matchData] = await Promise.all([getJd(jdId), getMatchResult(jdId)]);
        if (!active) {
          return;
        }
        setJd(jdData);
        setResult({
          jd_id: jdId,
          extracted_skill_count: jdData.skills.length,
          persisted_count: matchData.recommendations.length,
          already_processed: true,
          recommendations: matchData.recommendations,
        });
      } catch (requestError) {
        if (!active) {
          return;
        }
        setError(
          requestError instanceof ApiError ? requestError.message : "历史详情加载失败，请稍后重试。"
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadDetail();
    return () => {
      active = false;
    };
  }, [jdId]);

  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
      <Link
        href="/history"
        className="inline-flex min-h-10 items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        返回历史记录
      </Link>

      {error ? (
        <div
          role="alert"
          className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      ) : (
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(420px,1.2fr)]">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:sticky lg:top-6">
            {loading || !jd ? (
              <Loading label="正在加载岗位详情" />
            ) : (
              <>
                <p className="text-xs font-semibold text-sky-700">岗位描述</p>
                <h1 className="mt-2 text-2xl font-semibold text-slate-950">
                  {jd.title || "未命名岗位"}
                </h1>
                <p className="mt-2 text-sm text-slate-500">
                  {jd.company || "未填写公司"} · {formatDate(jd.created_at)}
                </p>
                <div className="mt-5 max-h-[55vh] overflow-y-auto whitespace-pre-wrap rounded-md bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                  {jd.raw_text}
                </div>
              </>
            )}
          </div>

          <MatchResult loading={loading} result={result} />
        </div>
      )}
    </section>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
