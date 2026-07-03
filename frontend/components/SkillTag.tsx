interface SkillTagProps {
  name: string;
  status: "matched" | "missing";
}

export default function SkillTag({ name, status }: SkillTagProps) {
  const matched = status === "matched";

  return (
    <span
      className={`inline-flex max-w-full items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${
        matched ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
          matched ? "bg-emerald-500" : "bg-slate-400"
        }`}
      />
      <span className="truncate">{name}</span>
    </span>
  );
}
