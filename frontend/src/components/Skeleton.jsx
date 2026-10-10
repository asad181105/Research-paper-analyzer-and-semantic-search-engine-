export default function Skeleton({ className = "h-4 w-full" }) {
  return <div className={`animate-pulse rounded bg-stone-200 dark:bg-zinc-800 ${className}`} />;
}
