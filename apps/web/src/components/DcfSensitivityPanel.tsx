"use client";

import { useMemo, useState } from "react";
import type { ValuationAssessment } from "@/lib/api";

function fmt(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function DcfSensitivityPanel({
  valuation,
}: {
  valuation: ValuationAssessment;
}) {
  const points = valuation.dcf_sensitivity ?? [];
  const [selected, setSelected] = useState(0);

  const labels = useMemo(() => points.map((p) => p.label), [points]);

  if (!valuation.dcf_fair_value || points.length === 0) {
    return null;
  }

  const active = points[selected] ?? points[0];

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 space-y-3">
      <h3 className="text-sm font-medium text-zinc-300">DCF scenario explorer</h3>
      <p className="text-xs text-zinc-500">
        Read-only view of precomputed sensitivity points (bear/base/bull + parameter tweaks).
      </p>
      {valuation.dcf_implied_growth_at_price != null && (
        <p className="text-xs text-zinc-400">
          Reverse DCF at current price: Y1 growth{" "}
          <span className="font-mono text-emerald-400/90">
            {(valuation.dcf_implied_growth_at_price * 100).toFixed(1)}%
          </span>
          {valuation.dcf_assumptions?.growth_rate != null && (
            <>
              {" "}
              vs model{" "}
              <span className="font-mono">
                {(Number(valuation.dcf_assumptions.growth_rate) * 100).toFixed(1)}%
              </span>
            </>
          )}
        </p>
      )}
      {valuation.dcf_assumptions?.terminal_value_pct_of_ev != null && (
        <p className="text-xs text-zinc-500">
          Terminal value:{" "}
          <span className="font-mono">
            {Number(valuation.dcf_assumptions.terminal_value_pct_of_ev).toFixed(0)}%
          </span>{" "}
          of enterprise PV — watch for TV trap if very high.
        </p>
      )}
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Scenario
        <select
          value={selected}
          onChange={(e) => setSelected(Number(e.target.value))}
          className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-zinc-200"
        >
          {labels.map((label, i) => (
            <option key={label} value={i}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <p className="text-sm font-mono text-emerald-400">
        Fair value @ {active.label}: ${fmt(active.fair_value)}
      </p>
      <p className="text-xs text-zinc-500">
        Base model: ${fmt(valuation.dcf_fair_value)}
        {valuation.current_price != null && (
          <> · Current ${fmt(valuation.current_price)}</>
        )}
      </p>
    </section>
  );
}
