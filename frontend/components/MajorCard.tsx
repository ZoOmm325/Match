"use client";

import { useState } from "react";
import type { MatchRecommendation } from "@/lib/api";
import MajorInlineDetail from "@/components/MajorInlineDetail";
import ScoreBar from "@/components/ScoreBar";
import SkillTag from "@/components/SkillTag";

interface MajorCardProps {
  recommendation: MatchRecommendation;
  defaultExpanded?: boolean;
}

export default function MajorCard({ recommendation, defaultExpanded = false }: MajorCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const detailId = `major-details-${recommendation.rank}-${recommendation.major_id ?? "fallback"}`;

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-sky-50 text-sm font-semibold text-sky-700">
          {recommendation.rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-slate-950">
                {recommendation.major_name}
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                {recommendation.major_code ?? "暂无专业代码"}
              </p>
            </div>
            <span className="rounded-md bg-sky-700 px-2.5 py-1 text-sm font-semibold text-white">
              {Math.round(recommendation.final_score * 100)}%
            </span>
          </div>

          <div className="mt-4">
            <ScoreBar label="综合匹配得分" value={recommendation.final_score} />
          </div>

          <p className="mt-4 text-sm leading-6 text-slate-600">
            {recommendation.recommendation_reason}
          </p>

          <SkillGroup
            label="匹配技能"
            skills={recommendation.matched_skills}
            status="matched"
            emptyText="暂无明确匹配技能"
          />
          <SkillGroup
            label="待补充技能"
            skills={recommendation.missing_skills}
            status="missing"
            emptyText="暂无明显技能缺口"
          />

          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={detailId}
            onClick={() => setExpanded((current) => !current)}
            className="mt-4 inline-flex min-h-9 items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
          >
            {expanded ? "收起详情" : "查看详情"}
          </button>

          {expanded ? (
            <div id={detailId} className="mt-4 border-t border-slate-200 pt-4">
              <h4 className="text-sm font-semibold text-slate-900">评分明细</h4>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <ScoreBar
                  compact
                  label="技能相似度"
                  value={recommendation.skill_similarity_score}
                />
                <ScoreBar compact label="技能覆盖率" value={recommendation.skill_coverage_score} />
                <ScoreBar
                  compact
                  label="就业方向匹配"
                  value={recommendation.employment_alignment_score}
                />
              </div>
              <div className="mt-5 border-t border-slate-100 pt-4">
                <h4 className="text-sm font-semibold text-slate-900">专业详情</h4>
                <MajorInlineDetail majorId={recommendation.major_id} />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function SkillGroup({
  label,
  skills,
  status,
  emptyText,
}: {
  label: string;
  skills: string[];
  status: "matched" | "missing";
  emptyText: string;
}) {
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-semibold text-slate-700">{label}</p>
      {skills.length ? (
        <div className="flex flex-wrap gap-2">
          {skills.map((skill) => (
            <SkillTag key={`${status}-${skill}`} name={skill} status={status} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">{emptyText}</p>
      )}
    </div>
  );
}
