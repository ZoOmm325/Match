const historyItems = [
  {
    id: "demo-1",
    title: "AI Backend Engineer",
    createdAt: "2026-06-19",
    topMajor: "Artificial Intelligence"
  },
  {
    id: "demo-2",
    title: "Data Platform Developer",
    createdAt: "2026-06-19",
    topMajor: "Data Science and Big Data Technology"
  }
];

export default function HistoryPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-950">Match history</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recent JD matching records will appear here after API integration.
        </p>
      </div>
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-semibold">JD title</th>
              <th className="px-4 py-3 font-semibold">Created</th>
              <th className="px-4 py-3 font-semibold">Top major</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {historyItems.map((item) => (
              <tr key={item.id}>
                <td className="px-4 py-3 font-medium text-slate-950">{item.title}</td>
                <td className="px-4 py-3 text-slate-600">{item.createdAt}</td>
                <td className="px-4 py-3 text-slate-600">{item.topMajor}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
