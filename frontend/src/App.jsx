import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { setToastHandler } from "./api";
import Ask from "./pages/Ask";
import Compare from "./pages/Compare";
import Library from "./pages/Library";
import PaperDetail from "./pages/PaperDetail";
import SearchPage from "./pages/Search";
import Topics from "./pages/Topics";
import UploadImport from "./pages/UploadImport";

const links = [
  { to: "/", label: "Search" },
  { to: "/library", label: "Library" },
  { to: "/upload", label: "Upload" },
  { to: "/ask", label: "Ask" },
  { to: "/compare", label: "Compare" },
  { to: "/topics", label: "Topics" },
];

export default function App() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    setToastHandler((message, type = "info") => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t, { id, message, type }]);
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
    });
  }, []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-stone-200/80 bg-stone-50/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <NavLink to="/" className="font-serif text-lg tracking-tight">
            Paper Engine
          </NavLink>
          <nav className="flex flex-wrap items-center gap-1 text-sm">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `rounded-full px-3 py-1.5 ${
                    isActive
                      ? "bg-stone-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                      : "text-stone-600 hover:bg-stone-200/70 dark:text-zinc-400 dark:hover:bg-zinc-800"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
            <button
              type="button"
              onClick={() => setDark((d) => !d)}
              className="ml-2 rounded-full border border-stone-300 px-3 py-1.5 text-xs dark:border-zinc-700"
            >
              {dark ? "Light" : "Dark"}
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/library" element={<Library />} />
          <Route path="/upload" element={<UploadImport />} />
          <Route path="/papers/:id" element={<PaperDetail />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/topics" element={<Topics />} />
        </Routes>
      </main>
      <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`rounded-lg px-3 py-2 text-sm shadow-lg ${
              t.type === "error"
                ? "bg-red-700 text-white"
                : "bg-stone-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
