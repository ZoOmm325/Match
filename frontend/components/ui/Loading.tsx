interface LoadingProps {
  label?: string;
  className?: string;
  compact?: boolean;
}

export default function Loading({
  label = "正在加载",
  className = "",
  compact = false,
}: LoadingProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className={`flex items-center justify-center gap-3 text-sm text-slate-500 ${
        compact ? "py-3" : "min-h-48 py-10"
      } ${className}`}
    >
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-sky-600"
      />
      <span>{label}</span>
    </div>
  );
}
