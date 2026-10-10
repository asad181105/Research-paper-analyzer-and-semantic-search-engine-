import { useEffect, useState } from "react";

export default function usePoll(fn, intervalMs, enabled) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    const tick = async () => {
      try {
        const d = await fn();
        if (alive) setData(d);
      } catch {
        /* ignore poll errors */
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [fn, intervalMs, enabled]);
  return data;
}
