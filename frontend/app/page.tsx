import Link from "next/link";

const sampleSkills = ["Python", "FastAPI", "PostgreSQL", "NLP", "Docker"];

export default function HomePage() {
  return (
    <section className="mx-auto grid min-h-[calc(100vh-73px)] max-w-6xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
      <div className="space-y-6">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">
            Recruitment JD to university major matching
          </p>
          <h1 className="text-4xl font-semibold tracking-normal text-slate-950 sm:text-5xl">
            Paste a job description and find aligned majors.
          </h1>
          <p className="max-w-2xl text-base leading-7 text-slate-600">
            Extract required skills from a recruitment JD, normalize them, and prepare a ranked
            university major match workflow.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/match"
            className="rounded-md bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700"
          >
            Start matching
          </Link>
          <Link
            href="/history"
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            View history
          </Link>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <label htmlFor="jd-preview" className="text-sm font-semibold text-slate-900">
          JD input preview
        </label>
        <textarea
          id="jd-preview"
          readOnly
          className="mt-3 h-56 w-full resize-none rounded-md border border-slate-300 bg-slate-50 p-3 text-sm leading-6 text-slate-700"
          value={
            "Backend engineer role. Requires Python, FastAPI, PostgreSQL, Docker, REST API design, and experience with NLP or machine learning projects."
          }
        />
        <div className="mt-4 flex flex-wrap gap-2">
          {sampleSkills.map((skill) => (
            <span
              key={skill}
              className="rounded-md bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700"
            >
              {skill}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
