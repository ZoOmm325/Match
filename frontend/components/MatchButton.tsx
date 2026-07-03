"use client";

interface MatchButtonProps {
  loading: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export default function MatchButton({ loading, disabled = false, onClick }: MatchButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      aria-busy={loading}
      className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-sky-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
    >
      {loading ? (
        <>
          <span
            aria-hidden="true"
            className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
          />
          正在分析并匹配
        </>
      ) : (
        "开始匹配"
      )}
    </button>
  );
}
