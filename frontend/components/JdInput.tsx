"use client";

interface JdInputProps {
  value: string;
  maxLength: number;
  error?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  onUseExample: () => void;
}

export default function JdInput({
  value,
  maxLength,
  error,
  disabled = false,
  onChange,
  onUseExample,
}: JdInputProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <label htmlFor="jd-text" className="text-sm font-semibold text-slate-950">
            岗位描述
          </label>
          <p className="mt-1 text-sm text-slate-500">
            粘贴完整招聘 JD，系统将抽取技能并推荐相关大学专业。
          </p>
        </div>
        <button
          type="button"
          onClick={onUseExample}
          disabled={disabled}
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          填入示例 JD
        </button>
      </div>

      <textarea
        id="jd-text"
        value={value}
        maxLength={maxLength}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "jd-error jd-count" : "jd-count"}
        onChange={(event) => onChange(event.target.value)}
        placeholder="例如：负责后端服务开发，要求熟悉 Python、FastAPI、PostgreSQL、Docker，具备机器学习项目经验……"
        className={`min-h-72 w-full resize-y rounded-md border bg-white p-4 text-sm leading-6 text-slate-800 outline-none transition focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-100 ${
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-100"
            : "border-slate-300 focus:border-sky-500 focus:ring-sky-100"
        }`}
      />

      <div className="flex min-h-5 items-start justify-between gap-4 text-xs">
        <p id="jd-error" role="alert" className="font-medium text-red-600">
          {error ?? ""}
        </p>
        <p
          id="jd-count"
          className={`shrink-0 ${value.length >= maxLength ? "text-red-600" : "text-slate-500"}`}
        >
          {value.length.toLocaleString()} / {maxLength.toLocaleString()}
        </p>
      </div>
    </div>
  );
}
