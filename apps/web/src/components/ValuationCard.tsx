import type { ValuationAssessment } from "@/lib/api";
import { ValuationBandBar } from "@/components/ValuationBandBar";
import { gapDisplayLabel } from "@/lib/gapLabels";

function fmt(n: number | null | undefined, digits = 2) {
  if (n == null) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

const MOS_COLORS: Record<string, string> = {
  undervalued: "text-emerald-400",
  fair: "text-zinc-300",
  overvalued: "text-amber-400",
};

function spreadInterpretation(pct: number | null | undefined): string | null {
  if (pct == null) return null;
  if (pct > 200) return `Methods span ${pct.toFixed(0)}% — treat the band as directional only.`;
  if (pct > 120) return `Methods disagree (${pct.toFixed(0)}% spread) — confidence may be lowered.`;
  return null;
}

export function ValuationCard({ valuation }: { valuation: ValuationAssessment }) {
  if (!valuation.data_available && !valuation.is_fund) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300">Fair-value assessment</h3>
        <p className="mt-2 text-sm text-zinc-500">
          {valuation.message ?? "Model-based fair value unavailable for this ticker."}
        </p>
      </section>
    );
  }

  if (valuation.is_fund && valuation.fund) {
    const f = valuation.fund;
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-3">
        <h3 className="text-sm font-medium text-emerald-400">Fund / ETF metrics</h3>
        <p className="text-xs text-zinc-500">
          Equity DCF and Graham models do not apply — review cost and NAV premium instead.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
          {f.expense_ratio != null && (
            <div>
              <p className="text-zinc-500 text-xs">Expense ratio</p>
              <p className="font-mono">{fmt(f.expense_ratio, 2)}%</p>
            </div>
          )}
          {f.nav_price != null && (
            <div>
              <p className="text-zinc-500 text-xs">NAV</p>
              <p className="font-mono">${fmt(f.nav_price)}</p>
            </div>
          )}
          {f.premium_discount_pct != null && (
            <div>
              <p className="text-zinc-500 text-xs">Premium / discount to NAV</p>
              <p
                className={
                  f.premium_discount_pct > 1
                    ? "font-mono text-amber-400"
                    : f.premium_discount_pct < -1
                      ? "font-mono text-emerald-400"
                      : "font-mono"
                }
              >
                {f.premium_discount_pct >= 0 ? "+" : ""}
                {fmt(f.premium_discount_pct, 1)}%
              </p>
            </div>
          )}
          {f.top_holdings_pct != null && (
            <div>
              <p className="text-zinc-500 text-xs">Top 5 holdings weight</p>
              <p className="font-mono">{fmt(f.top_holdings_pct, 1)}%</p>
            </div>
          )}
        </div>
        {(valuation.fair_value_mid ?? f.fair_value_mid) != null && (
          <p className="text-xs text-zinc-400">
            Model NAV band: ${fmt(valuation.fair_value_low ?? f.fair_value_low)} – $
            {fmt(valuation.fair_value_high ?? f.fair_value_high)} (mid $
            {fmt(valuation.fair_value_mid ?? f.fair_value_mid)})
          </p>
        )}
      </section>
    );
  }

  const price = valuation.current_price;
  const low = valuation.fair_value_low;
  const mid = valuation.fair_value_mid;
  const high = valuation.fair_value_high;
  const spreadMsg = spreadInterpretation(valuation.method_spread_pct);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-emerald-400">Fair-value assessment</h3>
        <div className="flex flex-wrap gap-2 text-xs">
          {valuation.confidence && (
            <span className="rounded border border-zinc-700 px-2 py-0.5 text-zinc-400">
              Confidence: {valuation.confidence}
            </span>
          )}
          {valuation.composite_mode && (
            <span className="rounded border border-zinc-800 px-2 py-0.5 text-zinc-500">
              Band: {valuation.composite_mode}
            </span>
          )}
        </div>
      </div>
      <p className="text-xs text-zinc-500">
        Headline band uses methods marked “in band” below. FCF yield is diagnostic only. MOS %
        is premium vs model mid — not a Graham-style buy discount. Not investment advice.
      </p>
      {valuation.composite_drivers && valuation.composite_drivers.length > 0 && (
        <p className="text-xs text-zinc-400">
          In band: {valuation.composite_drivers.join(", ")}
        </p>
      )}
      {spreadMsg && <p className="text-xs text-amber-400/90">{spreadMsg}</p>}
      {valuation.reliability_notes && valuation.reliability_notes.length > 0 && (
        <ul className="text-xs text-amber-500/90 list-disc list-inside space-y-0.5">
          {valuation.reliability_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {valuation.data_gaps && valuation.data_gaps.length > 0 && (
        <ul className="text-xs text-zinc-500 list-disc list-inside space-y-0.5">
          {valuation.data_gaps.map((g) => (
            <li
              key={g}
              className={g === "valuation_currency_mismatch" ? "text-amber-400" : ""}
            >
              {gapDisplayLabel(g)}
            </li>
          ))}
        </ul>
      )}

      {mid != null && price != null && (
        <div className="space-y-2">
          <ValuationBandBar
            price={price}
            low={low}
            mid={mid}
            high={high}
            stressLow={valuation.fair_value_stress_low}
            stressHigh={valuation.fair_value_stress_high}
          />
          <p className="text-sm">
            Current ${fmt(price)}
            {valuation.mos_pct != null && valuation.mos_label && (
              <span className={`ml-2 ${MOS_COLORS[valuation.mos_label] ?? ""}`}>
                {valuation.mos_pct >= 0 ? "+" : ""}
                {fmt(valuation.mos_pct, 1)}% premium vs fair mid ({valuation.mos_label})
              </span>
            )}
          </p>
          {valuation.margin_of_safety_met != null && valuation.mos_buy_threshold_pct != null && (
            <p
              className={
                valuation.margin_of_safety_met
                  ? "text-xs text-emerald-400/90"
                  : "text-xs text-zinc-500"
              }
            >
              {valuation.margin_of_safety_met
                ? `Meets ${fmt(valuation.mos_buy_threshold_pct, 0)}% margin-of-safety (price ≤ fair mid minus threshold).`
                : `Below ${fmt(valuation.mos_buy_threshold_pct, 0)}% margin-of-safety — undervalued label ≠ adequate buy discount.`}
            </p>
          )}
        </div>
      )}

      {valuation.methods.length > 0 && (
        <table className="w-full text-xs text-zinc-400">
          <thead>
            <tr className="text-left text-zinc-500">
              <th className="pb-1 w-8"></th>
              <th className="pb-1">Method</th>
              <th className="pb-1">Fair value</th>
              <th className="pb-1">Detail</th>
            </tr>
          </thead>
          <tbody>
            {valuation.methods.map((m) => (
              <tr
                key={m.method}
                className={
                  m.reliable_for_composite === false
                    ? "border-t border-zinc-800/80 opacity-70"
                    : "border-t border-zinc-800/80"
                }
              >
                <td className="py-1 text-emerald-500">
                  {m.reliable_for_composite ? "✓" : "—"}
                </td>
                <td className="py-1 font-mono text-zinc-300">{m.method}</td>
                <td className="py-1">
                  {m.data_available && m.fair_value != null ? `$${fmt(m.fair_value)}` : "—"}
                </td>
                <td className="py-1 text-zinc-500">{m.detail ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {valuation.dcf_fair_value != null && (
        <details className="text-xs text-zinc-400">
          <summary className="cursor-pointer text-zinc-300 hover:text-zinc-100">
            DCF sensitivity (optional model)
          </summary>
          <p className="mt-2">
            Base DCF fair value:{" "}
            <span className="font-mono">${fmt(valuation.dcf_fair_value)}</span>
          </p>
          {valuation.dcf_implied_growth_at_price != null && (
            <p className="mt-1">
              Reverse DCF: market implies{" "}
              <span className="font-mono">
                {(valuation.dcf_implied_growth_at_price * 100).toFixed(1)}%
              </span>{" "}
              Y1 FCF growth (fading to terminal) at current price.
            </p>
          )}
          {valuation.dcf_assumptions && (
            <pre className="mt-1 overflow-auto rounded bg-zinc-950 p-2 text-[10px]">
              {JSON.stringify(valuation.dcf_assumptions, null, 2)}
            </pre>
          )}
          {valuation.dcf_sensitivity && valuation.dcf_sensitivity.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {valuation.dcf_sensitivity.map((s) => (
                <li key={s.label}>
                  {s.label}: {s.fair_value != null ? `$${fmt(s.fair_value)}` : "—"}
                </li>
              ))}
            </ul>
          )}
        </details>
      )}
    </section>
  );
}
