import { useEffect, useState } from "react";
import { Analyze, Papers } from "../api";

const ROWS = ["problem", "approach", "data", "results", "strengths", "weaknesses"];

export default function Compare() {
  const [papers, setPapers] = useState([]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [cmp, setCmp] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Papers.list().then((d) => setPapers(d.papers || []));
  }, []);

  return (
    <div>
      <h1 className="font-serif text-3xl">Compare papers</h1>
      <div className="mt-4 flex flex-wrap gap-3">
        <select value={a} onChange={(e) => setA(e.target.value)} className="rounded-xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Paper A</option>
          {papers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <select value={b} onChange={(e) => setB(e.target.value)} className="rounded-xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Paper B</option>
          {papers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!a || !b || a === b}
          className="rounded-xl bg-stone-900 px-4 py-2 text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
          onClick={async () => {
            setLoading(true);
            try {
              setCmp(await Analyze.compare(Number(a), Number(b)));
            } finally {
              setLoading(false);
            }
          }}
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>
      {cmp && (
        <div className="mt-6 overflow-x-auto">
          {cmp.mode !== "llm" && (
            <p className="mb-3 text-sm text-amber-800 dark:text-amber-300">
              Extractive comparison — add an LLM API key for a richer table.
            </p>
          )}
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-stone-100 dark:bg-zinc-900">
                <th className="border border-stone-200 p-2 dark:border-zinc-800" />
                <th className="border border-stone-200 p-2 dark:border-zinc-800">{cmp.papers[0].title}</th>
                <th className="border border-stone-200 p-2 dark:border-zinc-800">{cmp.papers[1].title}</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row) => (
                <tr key={row}>
                  <td className="border border-stone-200 p-2 font-medium capitalize dark:border-zinc-800">{row}</td>
                  <td className="border border-stone-200 p-2 dark:border-zinc-800">{cmp.comparison[row]?.a}</td>
                  <td className="border border-stone-200 p-2 dark:border-zinc-800">{cmp.comparison[row]?.b}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
