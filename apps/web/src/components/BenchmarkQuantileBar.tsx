"use client";

import type { MetricPercentiles } from "@/lib/api";

type Props = {
  label: string;
  percentiles: MetricPercentiles;
  currentPercentile?: number | null;
  valueSuffix?: string;
};

export function BenchmarkQuantileBar({
  label,
  percentiles,
  currentPercentile,
  valueSuffix = "",
}: Props) {
  const p10 = percentiles.p10;
  const p90 = percentiles.p90;
  if (p10 == null || p90 == null || p90 <= p10) {
    return null;
  }

  const marker =
    currentPercentile != null
      ? Math.min(100, Math.max(0, currentPercentile))
      : null;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-500">
        <span>{label}</span>
        {marker != null && <span>Current ~{marker.toFixed(0)}th pctile</span>}
      </div>
      <div className="relative h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div className="absolute inset-y-0 left-[10%] right-[10%] bg-zinc-600/60" />
        {marker != null && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-emerald-400"
            style={{ left: `${marker}%` }}
            title={`${marker}th percentile`}
          />
        )}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-zinc-600">
        <span>
          P10 {p10.toFixed(1)}
          {valueSuffix}
        </span>
        <span>
          P50 {percentiles.p50?.toFixed(1) ?? "—"}
          {valueSuffix}
        </span>
        <span>
          P90 {p90.toFixed(1)}
          {valueSuffix}
        </span>
      </div>
    </div>
  );
}
