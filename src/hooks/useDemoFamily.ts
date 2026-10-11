"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DemoApiError, DemoFamily, demoRequest } from "@/lib/demo-api";

export function useDemoFamily(enabled: boolean, poll = false) {
  const [family, setFamily] = useState<DemoFamily>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const sequence = useRef(0);
  const refresh = useCallback(async () => {
    if (!enabled) return;
    const operation = ++sequence.current;
    setLoading(true);
    try {
      const result = await demoRequest("/family");
      if (operation === sequence.current) { setFamily(result); setError(""); }
    } catch (err) {
      if (operation === sequence.current) {
        setFamily(undefined);
        setError(err instanceof DemoApiError && err.status === 404 ? "" :
          err instanceof Error ? err.message : "Demo family could not be loaded.");
      }
    } finally { if (operation === sequence.current) setLoading(false); }
  }, [enabled]);
  const update = useCallback((value: DemoFamily) => {
    sequence.current++; setFamily(value); setLoading(false); setError("");
  }, []);
  useEffect(() => {
    void refresh();
    const focus = () => { void refresh(); };
    window.addEventListener("focus", focus);
    const timer = enabled && poll ? window.setInterval(focus, 3000) : undefined;
    return () => {
      sequence.current++; window.removeEventListener("focus", focus);
      if (timer) window.clearInterval(timer);
    };
  }, [refresh, enabled, poll]);
  return { family, update, loading, error, refresh };
}
