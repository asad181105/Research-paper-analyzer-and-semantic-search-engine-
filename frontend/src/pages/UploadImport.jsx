import { useState } from "react";
import { Link } from "react-router-dom";
import { Papers } from "../api";

export default function UploadImport() {
  const [jobs, setJobs] = useState([]);
  const [q, setQ] = useState("information retrieval neural ranking");
  const [hits, setHits] = useState([]);
  const [searching, setSearching] = useState(false);
  const [arxivId, setArxivId] = useState("");

  function watch(paper) {
    const job = { id: paper.id, title: paper.title, status: paper.status, progress: 0 };
    setJobs((j) => [job, ...j]);
    const t = setInterval(async () => {
      try {
        const st = await Papers.status(paper.id);
        setJobs((js) => js.map((x) => (x.id === paper.id ? { ...x, ...st } : x)));
        if (st.status === "ready" || st.status === "failed") clearInterval(t);
      } catch {
        clearInterval(t);
      }
    }, 1500);
  }

  async function onFiles(files) {
    for (const f of files) {
      const res = await Papers.upload(f);
      watch(res.paper);
    }
  }

  return (
    <div className="grid gap-10 md:grid-cols-2">
      <section>
        <h1 className="font-serif text-3xl">Upload PDFs</h1>
        <label className="mt-4 flex h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-stone-300 text-sm dark:border-zinc-700">
          Drop PDFs here or click to browse
          <input
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
          />
        </label>
      </section>
      <section>
        <h2 className="font-serif text-3xl">Import from arXiv</h2>
        <div className="mt-4 flex gap-2">
          <input
            value={arxivId}
            onChange={(e) => setArxivId(e.target.value)}
            placeholder="arXiv ID e.g. 1706.03762"
            className="flex-1 rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-zinc-700"
          />
          <button
            type="button"
            className="rounded-xl bg-stone-900 px-3 py-2 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900"
            onClick={async () => {
              const res = await Papers.importArxiv(arxivId);
              watch(res.paper);
            }}
          >
            Import
          </button>
        </div>
        <form
          className="mt-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setSearching(true);
            try {
              const d = await Papers.arxivSearch(q);
              setHits(d.results || []);
            } finally {
              setSearching(false);
            }
          }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-zinc-700"
          />
          <button type="submit" className="mt-2 rounded-full border px-4 py-1 text-sm">
            {searching ? "Searching…" : "Search arXiv"}
          </button>
        </form>
        <ul className="mt-4 space-y-3">
          {hits.map((h) => (
            <li key={h.arxiv_id} className="rounded-xl border border-stone-200 p-3 text-sm dark:border-zinc-800">
              <div className="font-medium">{h.title}</div>
              <div className="text-xs text-stone-500">{h.authors}</div>
              <p className="mt-1 line-clamp-3 text-stone-600 dark:text-zinc-400">{h.abstract}</p>
              <button
                type="button"
                className="mt-2 text-xs text-amber-800 dark:text-amber-300"
                onClick={async () => {
                  const res = await Papers.importArxiv(h.arxiv_id);
                  watch(res.paper);
                }}
              >
                Import {h.arxiv_id}
              </button>
            </li>
          ))}
        </ul>
      </section>
      {jobs.length > 0 && (
        <section className="md:col-span-2">
          <h3 className="font-medium">Ingestion jobs</h3>
          <ul className="mt-2 space-y-2">
            {jobs.map((j) => (
              <li key={j.id} className="rounded-xl bg-stone-100 p-3 text-sm dark:bg-zinc-900">
                <Link to={`/papers/${j.id}`} className="hover:underline">
                  {j.title}
                </Link>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-zinc-800">
                  <div
                    className="h-full bg-amber-700"
                    style={{ width: `${j.progress || 0}%` }}
                  />
                </div>
                <span className="text-xs">
                  {j.status} — {j.status_message}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
