"use client";

import Link from "next/link";
import type { MacroContextOverlay } from "@/lib/api";
import { gapDisplayLabel } from "@/lib/gapLabels";

type Props = {
  overlay: MacroContextOverlay;
};

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

const ACTIONABLE_MACRO_GAPS = new Set(["fred_auth_failed", "fred_api_key_missing"]);

export function MacroContextCard({ overlay }: Props) {
  if (!overlay.has_content) return null;

  const signals = overlay.macro_signals;
  const events = overlay.relevant_events ?? [];
  const macroInfraGaps = (overlay.data_gaps ?? []).filter((g) =>
    ACTIONABLE_MACRO_GAPS.has(g),
  );

  return (
    <section className="rounded-lg border border-amber-900/40 bg-amber-950/15 p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium text-amber-400">Macro backdrop</h3>
          <p className="text-xs text-zinc-500 mt-0.5 font-mono">
            US trading day {overlay.trading_date}
            {overlay.ticker_sector ? ` · ${overlay.ticker_sector}` : ""}
          </p>
        </div>
        <Link
          href="/briefing"
          className="text-xs text-amber-500/90 hover:text-amber-400 underline"
        >
          Full macro briefing
        </Link>
      </div>

      {macroInfraGaps.length > 0 && (
        <ul className="text-xs text-amber-300/90 list-disc list-inside space-y-0.5">
          {macroInfraGaps.map((g) => (
            <li key={g}>{gapDisplayLabel(g)}</li>
          ))}
        </ul>
      )}

      {overlay.market_weather && (
        <p className="text-sm text-zinc-200">{overlay.market_weather}</p>
      )}

      {signals && (
        <div className="flex flex-wrap gap-2 text-xs font-mono text-zinc-500">
          {signals.risk_tone === "elevated_vix" && (
            <span className="text-amber-400 border border-amber-900/50 rounded px-2 py-0.5">
              Elevated VIX
            </span>
          )}
          {signals.yield_curve_10y_3m_bps != null && (
            <span>10Y–3M: {signals.yield_curve_10y_3m_bps} bps</span>
          )}
          {signals.signals.slice(0, 4).map((s) => (
            <span key={s.symbol}>
              {s.label}: {s.level?.toFixed(2) ?? "—"} ({fmtPct(s.change_1d_pct)} 1d)
            </span>
          ))}
        </div>
      )}

      {overlay.signal_highlights && overlay.signal_highlights.length > 0 && (
        <ul className="list-disc list-inside text-sm text-zinc-400 space-y-1">
          {overlay.signal_highlights.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      )}

      {events.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="text-left text-zinc-500 border-b border-zinc-800">
                <th className="py-1 pr-3">Release</th>
                <th className="py-1 pr-3">Impact</th>
                <th className="py-1 pr-3">Surprise</th>
                <th className="py-1">Beat/Miss</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.name} className="border-b border-zinc-800/50">
                  <td className="py-1 pr-3 text-zinc-300">{ev.name}</td>
                  <td className="py-1 pr-3 capitalize">{ev.impact}</td>
                  <td className="py-1 pr-3 font-mono">{fmtPct(ev.surprise_pct)}</td>
                  <td className="py-1 capitalize">{ev.beat_miss ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
