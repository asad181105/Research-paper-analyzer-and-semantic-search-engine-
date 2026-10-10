import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { Analyze } from "../api";
import EmptyState from "../components/EmptyState";

const COLORS = ["#b45309", "#1d4ed8", "#047857", "#be123c", "#7c3aed", "#0f766e", "#c2410c", "#334155"];

export default function Topics() {
  const [data, setData] = useState(null);

  useEffect(() => {
    Analyze.topics().then(setData);
  }, []);

  if (!data) return <p>Loading topics…</p>;
  if (!data.points?.length) {
    return <EmptyState title="Not enough papers" body={data.message || "Add at least two ready papers."} />;
  }

  const groups = {};
  data.points.forEach((p) => {
    groups[p.cluster] = groups[p.cluster] || [];
    groups[p.cluster].push(p);
  });

  return (
    <div>
      <h1 className="font-serif text-3xl">Library topics</h1>
      <p className="mt-1 text-sm text-stone-500">KMeans clusters (k={data.k}) with 2D projection.</p>
      <div className="mt-6 h-96 rounded-2xl border border-stone-200 p-2 dark:border-zinc-800">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" dataKey="x" name="x" />
            <YAxis type="number" dataKey="y" name="y" />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              content={({ payload }) => {
                const p = payload?.[0]?.payload;
                if (!p) return null;
                return (
                  <div className="rounded bg-white p-2 text-xs shadow dark:bg-zinc-900">
                    {p.title}
                  </div>
                );
              }}
            />
            <Legend />
            {Object.entries(groups).map(([cid, pts]) => {
              const label = data.clusters.find((c) => String(c.id) === String(cid))?.label || `Cluster ${cid}`;
              return (
                <Scatter
                  key={cid}
                  name={label}
                  data={pts}
                  fill={COLORS[Number(cid) % COLORS.length]}
                />
              );
            })}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-6 space-y-3">
        {data.clusters.map((c) => (
          <li key={c.id} className="text-sm">
            <span className="font-medium">{c.label}</span>
            <span className="text-stone-400"> ({c.size})</span>
            <div className="mt-1 flex flex-wrap gap-2">
              {c.paper_ids.map((pid) => {
                const pt = data.points.find((p) => p.paper_id === pid);
                return (
                  <Link key={pid} to={`/papers/${pid}`} className="rounded-full bg-stone-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                    {pt?.title || pid}
                  </Link>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
