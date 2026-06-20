const placeholderResult = [
  { major: "Software Engineering", score: 92 },
  { major: "Computer Science and Technology", score: 88 },
  { major: "Artificial Intelligence", score: 81 }
];

export default function MatchPage() {
  return (
    <section className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_360px]">
      <form className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4">
          <h1 className="text-2xl font-semibold text-slate-950">JD matching</h1>
          <p className="mt-1 text-sm text-slate-600">
            Paste a recruitment JD to prepare skill extraction and major matching.
          </p>
        </div>
        <label htmlFor="jd-text" className="text-sm font-medium text-slate-800">
          Job description
        </label>
        <textarea
          id="jd-text"
          name="jdText"
          className="mt-2 min-h-80 w-full rounded-md border border-slate-300 p-3 text-sm leading-6 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
          placeholder="Paste the full JD here..."
        />
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-md bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Start match
          </button>
          <button
            type="reset"
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Clear
          </button>
        </div>
      </form>

      <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-slate-950">Result preview</h2>
        <div className="mt-4 space-y-3">
          {placeholderResult.map((item) => (
            <div key={item.major} className="rounded-md border border-slate-200 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-900">{item.major}</p>
                <span className="text-sm font-semibold text-brand-700">{item.score}%</span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-brand-600"
                  style={{ width: `${item.score}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </aside>
    </section>
  );
}
