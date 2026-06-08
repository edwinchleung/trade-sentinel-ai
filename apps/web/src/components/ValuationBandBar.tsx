"use client";

type Props = {
  price?: number | null;
  low?: number | null;
  mid?: number | null;
  high?: number | null;
  stressLow?: number | null;
  stressHigh?: number | null;
};

export function ValuationBandBar({ price, low, mid, high, stressLow, stressHigh }: Props) {
  const bandLow = stressLow ?? low;
  const bandHigh = stressHigh ?? high;
  if (bandLow == null || bandHigh == null || bandHigh <= bandLow) {
    return null;
  }

  const range = bandHigh - bandLow;
  const pct = (v: number) => Math.min(100, Math.max(0, ((v - bandLow) / range) * 100));

  return (
    <div className="space-y-1">
      <div className="relative h-3 rounded-full bg-zinc-800 overflow-hidden">
        {low != null && high != null && (
          <div
            className="absolute inset-y-0 bg-emerald-900/50 border-x border-emerald-700/40"
            style={{ left: `${pct(low)}%`, right: `${100 - pct(high)}%` }}
          />
        )}
        {mid != null && (
          <div
            className="absolute top-0 bottom-0 w-px bg-zinc-400"
            style={{ left: `${pct(mid)}%` }}
          />
        )}
        {price != null && (
          <div
            className="absolute top-0 bottom-0 w-1 bg-amber-400 rounded-full"
            style={{ left: `${pct(price)}%`, transform: "translateX(-50%)" }}
            title={`Price $${price.toFixed(2)}`}
          />
        )}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-zinc-600">
        <span>${bandLow.toFixed(0)}</span>
        {mid != null && <span className="text-zinc-500">mid ${mid.toFixed(0)}</span>}
        <span>${bandHigh.toFixed(0)}</span>
      </div>
    </div>
  );
}
