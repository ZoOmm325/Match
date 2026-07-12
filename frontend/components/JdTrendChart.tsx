import Loading from "@/components/ui/Loading";
import type { JdTrendData } from "@/lib/api";

interface JdTrendChartProps {
  data: JdTrendData | null;
  loading: boolean;
  error?: string;
}

const WIDTH = 640;
const HEIGHT = 220;
const PADDING = 34;

export default function JdTrendChart({ data, loading, error = "" }: JdTrendChartProps) {
  const points = data?.points ?? [];
  const maxCount = Math.max(1, ...points.map((point) => point.count));
  const chartWidth = WIDTH - PADDING * 2;
  const chartHeight = HEIGHT - PADDING * 2;
  const plotted = points.map((point, index) => {
    const x =
      points.length <= 1 ? PADDING + chartWidth / 2 : PADDING + (index / (points.length - 1)) * chartWidth;
    const y = PADDING + chartHeight - (point.count / maxCount) * chartHeight;
    return { ...point, x, y };
  });
  const polyline = plotted.map((point) => `${point.x},${point.y}`).join(" ");
  const latest = points.at(-1);

  return (
    <section className="mb-6 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">岗位数量趋势</h2>
          <p className="mt-1 text-sm text-slate-500">最近 {data?.days ?? 30} 天每日新增岗位数</p>
        </div>
        <div className="rounded-md bg-slate-50 px-3 py-2 text-right">
          <p className="text-xs text-slate-500">区间合计</p>
          <p className="text-lg font-semibold text-slate-950">{data?.total ?? 0}</p>
        </div>
      </div>

      {loading ? <Loading compact label="正在加载趋势数据" /> : null}

      {!loading && error ? (
        <div role="alert" className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="mt-4 overflow-hidden rounded-md border border-slate-100 bg-slate-50/60">
          <svg
            role="img"
            aria-label="岗位数量随时间变化折线图"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="h-64 w-full"
            preserveAspectRatio="none"
          >
            <line x1={PADDING} y1={PADDING} x2={PADDING} y2={HEIGHT - PADDING} stroke="#cbd5e1" />
            <line
              x1={PADDING}
              y1={HEIGHT - PADDING}
              x2={WIDTH - PADDING}
              y2={HEIGHT - PADDING}
              stroke="#cbd5e1"
            />
            {[0, 0.5, 1].map((ratio) => {
              const y = PADDING + chartHeight - ratio * chartHeight;
              return (
                <g key={ratio}>
                  <line x1={PADDING} y1={y} x2={WIDTH - PADDING} y2={y} stroke="#e2e8f0" />
                  <text x={10} y={y + 4} className="fill-slate-500 text-[11px]">
                    {Math.round(maxCount * ratio)}
                  </text>
                </g>
              );
            })}
            {polyline ? (
              <polyline points={polyline} fill="none" stroke="#0284c7" strokeWidth="3" strokeLinejoin="round" />
            ) : null}
            {plotted.map((point) => (
              <g key={point.date}>
                <circle cx={point.x} cy={point.y} r="4" fill="#0284c7" />
                <title>{`${formatDate(point.date)}：${point.count} 个岗位`}</title>
              </g>
            ))}
            {plotted[0] ? (
              <text x={PADDING} y={HEIGHT - 10} className="fill-slate-500 text-[12px]">
                {formatDate(plotted[0].date)}
              </text>
            ) : null}
            {latest ? (
              <text x={WIDTH - PADDING - 54} y={HEIGHT - 10} className="fill-slate-500 text-[12px]">
                {formatDate(latest.date)}
              </text>
            ) : null}
          </svg>
        </div>
      ) : null}
    </section>
  );
}

function formatDate(value: string): string {
  const [, month, day] = value.split("-");
  return month && day ? `${month}/${day}` : value;
}
