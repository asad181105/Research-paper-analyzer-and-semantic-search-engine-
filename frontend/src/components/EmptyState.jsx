export default function EmptyState({ title, body, action }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone-300 p-10 text-center dark:border-zinc-700">
      <h3 className="font-serif text-xl">{title}</h3>
      {body && <p className="mt-2 text-sm text-stone-500 dark:text-zinc-400">{body}</p>}
      {action}
    </div>
  );
}
