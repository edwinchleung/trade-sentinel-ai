"use client";

type Props = {
  completed: number;
  total: number;
  label?: string;
  running?: boolean;
};

export function ScanProgressBar({ completed, total, label, running }: Props) {
  if (total <= 0) return null;
  const pct = Math.min(100, Math.round((completed / total) * 100));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-500">
        <span>
          {label ?? "Scanning"}
          {running ? "…" : ""}
        </span>
        <span>
          {completed} / {total} ({pct}%)
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
        <div
          className="h-full rounded-full bg-emerald-600/70 transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
