interface ScoreBarProps {
  label: string;
  value: number;
  compact?: boolean;
}

export default function ScoreBar({ label, value, compact = false }: ScoreBarProps) {
  const normalized = Math.max(0, Math.min(1, value));
  const percentage = Math.round(normalized * 100);

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-4">
        <span className={compact ? "text-xs text-slate-600" : "text-sm font-medium text-slate-700"}>
          {label}
        </span>
        <span
          className={
            compact ? "text-xs font-semibold text-slate-700" : "text-sm font-semibold text-sky-700"
          }
        >
          {percentage}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        className={`overflow-hidden rounded bg-slate-100 ${compact ? "h-1.5" : "h-2"}`}
      >
        <div
          className="h-full rounded bg-sky-600 transition-[width] duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
