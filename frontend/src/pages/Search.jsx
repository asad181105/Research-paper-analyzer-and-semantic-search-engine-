import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Papers, Search } from "../api";
import EmptyState from "../components/EmptyState";
import Skeleton from "../components/Skeleton";

export default function SearchPage() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [section, setSection] = useState("");
  const [year, setYear] = useState("");
  const [author, setAuthor] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  async function run(e) {
    e?.preventDefault();
    setLoading(true);
    try {
      const res = await Search.query({
        q,
        mode,
        k: 10,
        section: section || undefined,
        year: year || undefined,
        author: author || undefined,
      });
      setData(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="font-serif text-4xl">Search the library by meaning</h1>
      <p className="mt-2 max-w-2xl text-stone-600 dark:text-zinc-400">
        Hybrid ranking fuses dense retrieval with BM25, then boosts highly cited papers.
      </p>
      <form onSubmit={run} className="mt-8">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. dense retrieval for scientific documents"
          className="w-full rounded-2xl border border-stone-300 bg-white px-5 py-4 text-lg outline-none ring-stone-400 focus:ring-2 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          {["hybrid", "semantic", "keyword"].map((m) => (
            <button
              type="button"
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full px-3 py-1 text-sm capitalize ${
                mode === m
                  ? "bg-stone-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "bg-stone-200 dark:bg-zinc-800"
              }`}
            >
              {m}
            </button>
          ))}
          <select
            value={section}
            onChange={(e) => setSection(e.target.value)}
            className="rounded-full border border-stone-300 bg-transparent px-3 py-1 text-sm dark:border-zinc-700"
          >
            <option value="">Any section</option>
            {["abstract", "introduction", "methodology", "results", "conclusion"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="Year"
            className="w-24 rounded-full border border-stone-300 bg-transparent px-3 py-1 text-sm dark:border-zinc-700"
          />
          <input
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Author"
            className="rounded-full border border-stone-300 bg-transparent px-3 py-1 text-sm dark:border-zinc-700"
          />
          <button
            type="submit"
            className="rounded-full bg-amber-700 px-5 py-1.5 text-sm text-white"
          >
            Search
          </button>
        </div>
      </form>

      <div className="mt-8 space-y-4">
        {loading &&
          [1, 2, 3].map((i) => (
            <div key={i} className="space-y-2 rounded-2xl border border-stone-200 p-5 dark:border-zinc-800">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-16 w-full" />
            </div>
          ))}
        {!loading && data && data.results.length === 0 && (
          <EmptyState
            title="No matches"
            body={data.message || "Try another query or add papers to the library."}
          />
        )}
        {data?.results.map((r) => (
          <article
            key={r.paper.id + "-" + r.chunk_id}
            className="rounded-2xl border border-stone-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <Link to={`/papers/${r.paper.id}`} className="font-serif text-xl hover:underline">
                {r.paper.title}
              </Link>
              <div className="flex gap-2 text-xs">
                <span className="rounded-full bg-stone-900 px-2 py-1 text-white dark:bg-zinc-100 dark:text-zinc-900">
                  score {r.score}
                </span>
                <span className="rounded-full bg-stone-100 px-2 py-1 dark:bg-zinc-800">
                  {r.citation_count} cites
                </span>
              </div>
            </div>
            <p className="mt-1 text-sm text-stone-500">{r.paper.authors}</p>
            <p
              className="mt-3 text-sm leading-relaxed"
              dangerouslySetInnerHTML={{ __html: r.passage }}
            />
            <p className="mt-2 text-xs uppercase tracking-wide text-stone-400">
              {r.section} · p.{r.page} · rel {r.scores?.relevance} · final {r.scores?.final}
            </p>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="rounded-full border px-3 py-1 text-xs"
                onClick={async () => {
                  await Papers.summarize(r.paper.id);
                  nav(`/papers/${r.paper.id}`);
                }}
              >
                Summarize
              </button>
              <Link to={`/ask?paper=${r.paper.id}`} className="rounded-full border px-3 py-1 text-xs">
                Ask
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
