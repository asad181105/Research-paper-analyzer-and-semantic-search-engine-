import { useEffect, useRef, useState } from "react";
import { QA } from "../api";

function renderAnswer(text, sources, onCite) {
  if (!text) return null;
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    if (m) {
      const n = Number(m[1]);
      return (
        <button
          type="button"
          key={i}
          className="mx-0.5 text-amber-800 underline dark:text-amber-300"
          onClick={() => onCite(sources[n - 1])}
        >
          [{n}]
        </button>
      );
    }
    return <span key={i}>{p}</span>;
  });
}

export default function ChatPanel({ paperId }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState([]);
  const [streaming, setStreaming] = useState("");
  const [sources, setSources] = useState([]);
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState("");
  const bottom = useRef(null);

  useEffect(() => {
    QA.history(paperId).then((d) => {
      setTurns((d.history || []).slice().reverse());
    });
  }, [paperId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streaming]);

  async function send(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setQuestion("");
    setStreaming("");
    setSelected(null);
    const url = QA.streamUrl(q, paperId);
    const es = new EventSource(url);
    let acc = "";
    let srcs = [];
    es.addEventListener("sources", (ev) => {
      srcs = JSON.parse(ev.data);
      setSources(srcs);
    });
    es.addEventListener("token", (ev) => {
      acc += JSON.parse(ev.data);
      setStreaming(acc);
    });
    es.addEventListener("done", (ev) => {
      const meta = JSON.parse(ev.data);
      if (meta.mode === "retrieval") {
        setNotice("LLM is not configured — showing retrieved passages.");
      } else {
        setNotice("");
      }
      setTurns((t) => [...t, { question: q, answer: acc, sources: srcs }]);
      setStreaming("");
      es.close();
    });
    es.onerror = () => {
      es.close();
      if (!acc) {
        QA.ask({ question: q, paper_id: paperId }).then((r) => {
          setSources(r.sources || []);
          setTurns((t) => [...t, { question: q, answer: r.answer, sources: r.sources }]);
          if (r.mode !== "llm") setNotice("LLM is not configured — showing retrieved passages.");
        });
      }
    };
  }

  return (
    <div className="flex h-[28rem] flex-col rounded-2xl border border-stone-200 dark:border-zinc-800">
      <div className="flex-1 space-y-4 overflow-y-auto p-4 text-sm">
        {notice && (
          <div className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            {notice}
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i}>
            <div className="font-medium">You: {t.question}</div>
            <div className="mt-1 whitespace-pre-wrap text-stone-700 dark:text-zinc-300">
              {renderAnswer(t.answer, t.sources || sources, setSelected)}
            </div>
          </div>
        ))}
        {streaming && <div className="whitespace-pre-wrap">{streaming}</div>}
        <div ref={bottom} />
      </div>
      {selected && (
        <div className="border-t border-stone-200 p-3 text-xs dark:border-zinc-800">
          <div className="font-medium">
            {selected.paper_title} · {selected.section} · p.{selected.page}
          </div>
          <p className="mt-1 text-stone-600 dark:text-zinc-400">{selected.snippet}</p>
        </div>
      )}
      <form onSubmit={send} className="flex gap-2 border-t border-stone-200 p-3 dark:border-zinc-800">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={paperId ? "Ask about this paper…" : "Ask the whole library…"}
          className="flex-1 rounded-xl bg-stone-100 px-3 py-2 dark:bg-zinc-900"
        />
        <button type="submit" className="rounded-xl bg-stone-900 px-4 text-white dark:bg-zinc-100 dark:text-zinc-900">
          Send
        </button>
      </form>
    </div>
  );
}
