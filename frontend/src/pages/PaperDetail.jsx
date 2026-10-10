import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Papers } from "../api";
import ChatPanel from "../components/ChatPanel";
import Skeleton from "../components/Skeleton";

export default function PaperDetail() {
  const { id } = useParams();
  const [paper, setPaper] = useState(null);
  const [summary, setSummary] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [open, setOpen] = useState("abstract");
  const [notice, setNotice] = useState("");

  async function load() {
    const p = await Papers.get(id);
    setPaper(p);
    if (p.summary) {
      try {
        setSummary(typeof p.summary === "string" ? JSON.parse(p.summary) : p.summary);
      } catch {
        setSummary(null);
      }
    }
    const s = await Papers.similar(id);
    setSimilar(s.similar || []);
  }

  useEffect(() => {
    load();
  }, [id]);

  if (!paper) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <p className="text-xs uppercase tracking-wide text-stone-400">{paper.status}</p>
        <h1 className="font-serif text-3xl">{paper.title}</h1>
        <p className="mt-1 text-sm text-stone-500">
          {paper.authors} {paper.year ? `· ${paper.year}` : ""} · {paper.citation_count} citations
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {(paper.keywords || []).map((k) => (
            <span key={k.id || k.keyword} className="rounded-full bg-stone-200 px-2 py-0.5 text-xs dark:bg-zinc-800">
              {k.keyword}
            </span>
          ))}
        </div>
        <button
          type="button"
          className="mt-4 rounded-full bg-amber-700 px-4 py-1.5 text-sm text-white"
          onClick={async () => {
            const r = await Papers.summarize(id, true);
            setSummary(r.summary);
            setNotice(r.notice || (r.mode !== "llm" ? "Extractive summary (no LLM key)." : ""));
          }}
        >
          Summarize
        </button>
        {notice && <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">{notice}</p>}
        {summary && (
          <div className="mt-4 rounded-2xl border border-stone-200 p-4 dark:border-zinc-800">
            <h2 className="font-medium">TL;DR</h2>
            <p className="mt-1 text-sm">{summary.tldr}</p>
            <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
              {["problem", "method", "dataset", "key_results", "limitations", "future_work"].map((k) => (
                <div key={k}>
                  <dt className="text-xs uppercase text-stone-400">{k.replace("_", " ")}</dt>
                  <dd>{summary[k]}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
        <div className="mt-6 space-y-2">
          {(paper.sections || []).map((s) => (
            <div key={s.id} className="rounded-xl border border-stone-200 dark:border-zinc-800">
              <button
                type="button"
                className="flex w-full justify-between px-4 py-2 text-left text-sm font-medium"
                onClick={() => setOpen(open === s.name ? "" : s.name)}
              >
                <span>
                  {s.title_raw || s.name}{" "}
                  <span className="text-xs text-stone-400">
                    p.{s.page_start}–{s.page_end}
                  </span>
                </span>
              </button>
              {open === s.name && (
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap px-4 pb-4 font-sans text-sm text-stone-700 dark:text-zinc-300">
                  {s.text}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>
      <aside className="space-y-6 lg:col-span-2">
        <div>
          <h3 className="font-medium">Ask this paper</h3>
          <div className="mt-2">
            <ChatPanel paperId={Number(id)} />
          </div>
        </div>
        <div>
          <h3 className="font-medium">Similar papers</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {similar.map((s) => (
              <li key={s.paper.id}>
                <Link to={`/papers/${s.paper.id}`} className="hover:underline">
                  {s.paper.title}
                </Link>
                <span className="ml-2 text-xs text-stone-400">{s.score}</span>
              </li>
            ))}
            {similar.length === 0 && <li className="text-stone-400">Need more papers in the library.</li>}
          </ul>
        </div>
      </aside>
    </div>
  );
}
