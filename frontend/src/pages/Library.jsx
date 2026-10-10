import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Papers } from "../api";
import EmptyState from "../components/EmptyState";

export default function Library() {
  const [papers, setPapers] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const d = await Papers.list();
    setPapers(d.papers || []);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onDrop(e) {
    e.preventDefault();
    const files = [...e.dataTransfer.files].filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    setBusy(true);
    try {
      for (const f of files) await Papers.upload(f);
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      <h1 className="font-serif text-3xl">Library</h1>
      <p className="mt-1 text-sm text-stone-500">Drag PDFs onto this page for bulk upload.</p>
      {papers.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No papers yet" body="Upload a PDF or import from arXiv." />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-stone-200 dark:border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-stone-100 dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Year</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Cites</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {papers.map((p) => (
                <tr key={p.id} className="border-t border-stone-200 dark:border-zinc-800">
                  <td className="px-3 py-2">
                    <Link to={`/papers/${p.id}`} className="hover:underline">
                      {p.title}
                    </Link>
                    <div className="text-xs text-stone-400">{p.authors}</div>
                  </td>
                  <td className="px-3 py-2">{p.year || "—"}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        p.status === "ready"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
                          : p.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-amber-100 text-amber-900"
                      }`}
                    >
                      {p.status} {p.progress ? `${p.progress}%` : ""}
                    </span>
                  </td>
                  <td className="px-3 py-2">{p.citation_count}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      className="text-red-700"
                      onClick={async () => {
                        await Papers.delete(p.id);
                        load();
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {busy && <p className="mt-3 text-sm">Uploading…</p>}
    </div>
  );
}
