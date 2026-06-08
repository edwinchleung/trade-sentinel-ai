"use client";

import { useJobUpdatesContext } from "@/components/JobUpdatesProvider";

export function NavLiveIndicator() {
  const ctx = useJobUpdatesContext();
  if (!ctx) return null;

  return (
    <span
      className={`ml-auto text-xs font-mono ${
        ctx.connected ? "text-emerald-500/80" : "text-amber-500/80"
      }`}
      title={ctx.connected ? "Live updates connected" : "Reconnecting live updates"}
    >
      {ctx.connected ? "Live" : "Reconnecting…"}
    </span>
  );
}
