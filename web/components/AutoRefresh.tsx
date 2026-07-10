"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Re-runs the server component on an interval so counts stay live without
// a full page reload. Used on Screen A (funnel) per OPS_UI_V1.md.
export default function AutoRefresh({ ms = 60_000 }: { ms?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), ms);
    return () => clearInterval(id);
  }, [router, ms]);
  return null;
}
