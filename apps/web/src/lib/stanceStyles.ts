import type { MetricTone, VisualStance } from "@/lib/api";

export function stancePillClass(stance: VisualStance): string {
  switch (stance) {
    case "favorable":
      return "border-emerald-800/60 bg-emerald-950/40 text-emerald-400";
    case "caution":
      return "border-amber-800/60 bg-amber-950/40 text-amber-400";
    case "unavailable":
      return "border-zinc-700 bg-zinc-900/60 text-zinc-500";
    default:
      return "border-zinc-700 bg-zinc-900/40 text-zinc-400";
  }
}

export function stanceDotClass(stance: VisualStance): string {
  switch (stance) {
    case "favorable":
      return "bg-emerald-400";
    case "caution":
      return "bg-amber-400";
    case "unavailable":
      return "bg-zinc-600";
    default:
      return "bg-zinc-400";
  }
}

export function metricToneClass(tone?: MetricTone | null): string {
  switch (tone) {
    case "positive":
      return "text-emerald-400";
    case "negative":
      return "text-red-400";
    case "muted":
      return "text-zinc-500";
    default:
      return "text-zinc-300";
  }
}
