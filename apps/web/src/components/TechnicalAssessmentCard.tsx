import type { TechnicalAssessment } from "@/lib/api";

function fmt(n: number | null | undefined, digits = 2) {
  if (n == null) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

const TREND_COLORS: Record<string, string> = {
  bullish: "text-emerald-400",
  bearish: "text-red-400",
  neutral: "text-zinc-300",
  mixed: "text-amber-400",
};

const DIVERGENCE_LABELS: Record<string, string> = {
  bullish: "Bullish MACD divergence",
  bearish: "Bearish MACD divergence",
  none: "No MACD divergence",
};

export function TechnicalAssessmentCard({
  assessment,
}: {
  assessment: TechnicalAssessment;
}) {
  if (!assessment.data_available) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300">Technical assessment</h3>
        <p className="mt-2 text-sm text-zinc-500">
          {assessment.message ?? "Technical assessment unavailable for this ticker."}
        </p>
      </section>
    );
  }

  const rangePct = assessment.range_position_pct;
  const rangeBar =
    rangePct != null ? Math.min(100, Math.max(0, rangePct)) : null;

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-sky-400">Technical assessment</h3>
        {assessment.trend_label && (
          <span
            className={`text-xs rounded border border-zinc-700 px-2 py-0.5 capitalize ${TREND_COLORS[assessment.trend_label] ?? "text-zinc-400"}`}
          >
            Trend: {assessment.trend_label}
          </span>
        )}
      </div>

      {assessment.trend_summary && (
        <p className="text-sm text-zinc-300 leading-relaxed">{assessment.trend_summary}</p>
      )}

      {assessment.horizon_summary && (
        <div className="grid grid-cols-3 gap-2 text-xs">
          {(
            [
              ["Short", assessment.short_term_trend],
              ["Mid", assessment.mid_term_trend],
              ["Long", assessment.long_term_trend],
            ] as const
          ).map(
            ([label, trend]) =>
              trend && (
                <div
                  key={label}
                  className="rounded border border-zinc-800 bg-zinc-950/40 px-2 py-1.5 text-center"
                >
                  <p className="text-zinc-500">{label}</p>
                  <p className={`capitalize ${TREND_COLORS[trend] ?? "text-zinc-400"}`}>
                    {trend}
                  </p>
                </div>
              )
          )}
        </div>
      )}

      {assessment.macd_divergence && assessment.macd_divergence !== "none" && (
        <p className="text-xs rounded border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-amber-300">
          {DIVERGENCE_LABELS[assessment.macd_divergence] ?? assessment.macd_divergence}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-sm">
        <div>
          <p className="text-zinc-500 text-xs">RSI (14)</p>
          <p className="font-mono">{fmt(assessment.rsi_14, 1)}</p>
        </div>
        <div>
          <p className="text-zinc-500 text-xs">vs SMA20</p>
          <p className="font-mono">
            {assessment.price_vs_sma_20_pct != null
              ? `${assessment.price_vs_sma_20_pct >= 0 ? "+" : ""}${fmt(assessment.price_vs_sma_20_pct, 1)}%`
              : "—"}
          </p>
        </div>
        <div>
          <p className="text-zinc-500 text-xs">vs SMA50</p>
          <p className="font-mono">
            {assessment.price_vs_sma_50_pct != null
              ? `${assessment.price_vs_sma_50_pct >= 0 ? "+" : ""}${fmt(assessment.price_vs_sma_50_pct, 1)}%`
              : "—"}
          </p>
        </div>
        <div>
          <p className="text-zinc-500 text-xs">ATR % of price</p>
          <p className="font-mono">{fmt(assessment.atr_pct, 2)}%</p>
        </div>
        <div>
          <p className="text-zinc-500 text-xs">Support</p>
          <p className="font-mono">${fmt(assessment.support_level)}</p>
        </div>
        <div>
          <p className="text-zinc-500 text-xs">Resistance</p>
          <p className="font-mono">${fmt(assessment.resistance_level)}</p>
        </div>
        {assessment.sma_20 != null && (
          <div>
            <p className="text-zinc-500 text-xs">SMA20</p>
            <p className="font-mono">${fmt(assessment.sma_20)}</p>
          </div>
        )}
        {assessment.sma_50 != null && (
          <div>
            <p className="text-zinc-500 text-xs">SMA50</p>
            <p className="font-mono">${fmt(assessment.sma_50)}</p>
          </div>
        )}
      </div>

      {rangeBar != null &&
        assessment.range_52w_low != null &&
        assessment.range_52w_high != null && (
          <div>
            <div className="flex justify-between text-xs text-zinc-500 mb-1">
              <span>52W low ${fmt(assessment.range_52w_low)}</span>
              <span className="text-zinc-400">{fmt(rangePct, 0)}% of range</span>
              <span>52W high ${fmt(assessment.range_52w_high)}</span>
            </div>
            <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
              <div
                className="h-full bg-sky-500/70 rounded-full"
                style={{ width: `${rangeBar}%` }}
              />
            </div>
          </div>
        )}

      {assessment.signals.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {assessment.signals.map((sig) => (
            <span
              key={sig}
              className="text-xs rounded border border-zinc-700 bg-zinc-950/60 px-2 py-0.5 text-zinc-400 font-mono"
            >
              {sig}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
