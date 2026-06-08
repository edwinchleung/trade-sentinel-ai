import type { Warning } from "@/lib/api";

const severityStyles: Record<string, string> = {
  high: "bg-red-950 text-red-300 border-red-800",
  medium: "bg-amber-950 text-amber-300 border-amber-800",
  low: "bg-zinc-800 text-zinc-400 border-zinc-700",
};

export function WarningBadge({ warning }: { warning: Warning }) {
  const style = severityStyles[warning.severity] ?? severityStyles.low;
  return (
    <div className={`rounded border px-3 py-2 text-sm ${style}`}>
      <span className="font-mono text-xs opacity-70">{warning.code}</span>
      <p className="mt-1">{warning.message}</p>
    </div>
  );
}
