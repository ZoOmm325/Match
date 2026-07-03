import type { MatchResponseData } from "@/lib/api";
import MajorCard from "@/components/MajorCard";
import EmptyState from "@/components/ui/EmptyState";
import Loading from "@/components/ui/Loading";

interface MatchResultProps {
  loading: boolean;
  result: MatchResponseData | null;
}

export default function MatchResult({ loading, result }: MatchResultProps) {
  return (
    <aside aria-live="polite" aria-busy={loading}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">匹配结果</h2>
          <p className="mt-1 text-sm text-slate-500">按综合匹配得分从高到低排列</p>
        </div>
        {result ? (
          <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            已提取 {result.extracted_skill_count} 项技能
          </span>
        ) : null}
      </div>

      {loading ? (
        <Loading label="正在生成匹配结果" />
      ) : result?.recommendations.length ? (
        <div className="space-y-4">
          {result.recommendations.slice(0, 5).map((recommendation, index) => (
            <MajorCard
              key={`${recommendation.major_id}-${recommendation.rank}`}
              recommendation={recommendation}
              defaultExpanded={index === 0}
            />
          ))}
        </div>
      ) : result ? (
        <EmptyState
          title="暂未找到合适的专业"
          description="可以补充岗位职责、技术栈或能力要求后重新匹配。"
        />
      ) : (
        <EmptyState
          title="等待岗位描述"
          description="输入或填入示例 JD，点击开始匹配后，推荐结果会显示在这里。"
        />
      )}
    </aside>
  );
}
