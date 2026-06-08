"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchMacroBriefing, type MacroBriefing } from "@/lib/api";

type ImpactFilter = "all" | "actionable" | "high";

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return v.toFixed(digits);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

export default function BriefingPage() {
  const [briefing, setBriefing] = useState<MacroBriefing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<ImpactFilter>("actionable");
  const [gapsOpen, setGapsOpen] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMacroBriefing({ refresh });
      setBriefing(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filteredEvents =
    briefing?.events.filter((ev) => {
      if (filter === "all") return true;
      if (filter === "high") return ev.impact === "high";
      return ev.impact === "high" || ev.impact === "moderate";
    }) ?? [];

  const impactChip = (level: string, count: number) => (
    <span
      key={level}
      className={`rounded-full px-2.5 py-0.5 text-xs font-mono capitalize ${
        level === "high"
          ? "bg-red-950/60 text-red-300 border border-red-900/50"
          : level === "moderate"
            ? "bg-amber-950/40 text-amber-300 border border-amber-900/40"
            : "bg-zinc-800 text-zinc-500 border border-zinc-700"
      }`}
    >
      {count} {level}
    </span>
  );

  const signals = briefing?.macro_signals;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Macro Signal Briefing</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Market indicators, calendar releases, and sector impacts for the US trading day.
          </p>
          {briefing?.as_of && (
            <p className="text-xs text-zinc-500 mt-1 font-mono">
              As of {new Date(briefing.as_of).toLocaleString()}
              {briefing.trading_date ? ` · Trading day ${briefing.trading_date}` : ""}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={loading}
          className="rounded border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading && !briefing && (
        <p className="text-zinc-500 text-sm">Loading briefing…</p>
      )}

      {briefing && (
        <>
          {briefing.market_weather && (
            <section className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-5">
              <h2 className="text-xs font-medium text-emerald-500 uppercase tracking-wide mb-2">
                Market weather
              </h2>
              <p className="text-lg text-zinc-100">{briefing.market_weather}</p>
            </section>
          )}

          {signals && signals.signals.length > 0 && (
            <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h2 className="text-sm font-medium text-zinc-300">Macro signals</h2>
                {signals.risk_tone === "elevated_vix" && (
                  <span className="text-xs font-mono text-amber-400 border border-amber-900/50 rounded px-2 py-0.5">
                    Elevated VIX
                  </span>
                )}
                {signals.yield_curve_10y_3m_bps != null && (
                  <span className="text-xs font-mono text-zinc-500">
                    10Y–3M spread: {signals.yield_curve_10y_3m_bps} bps
                  </span>
                )}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {signals.signals.map((s) => (
                  <div
                    key={s.symbol}
                    className="rounded border border-zinc-800/80 bg-zinc-950/40 px-3 py-2 text-sm"
                  >
                    <div className="font-medium text-zinc-200">{s.label}</div>
                    <div className="font-mono text-xs text-zinc-400 mt-1">
                      {fmtNum(s.level, s.level != null && s.level < 10 ? 2 : 2)}
                      <span className="mx-2 text-zinc-600">|</span>
                      1d {fmtPct(s.change_1d_pct)}
                      <span className="mx-1 text-zinc-700">·</span>
                      5d {fmtPct(s.change_5d_pct)}
                    </div>
                  </div>
                ))}
              </div>
              {signals.official && signals.official.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
                  {signals.official.map((o) => (
                    <span key={o.series_id} className="font-mono">
                      {o.label}: {o.value != null ? o.value : "—"}
                    </span>
                  ))}
                </div>
              )}
            </section>
          )}

          {briefing.signal_highlights && briefing.signal_highlights.length > 0 && (
            <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <h2 className="text-sm font-medium text-zinc-300 mb-3">Signal highlights</h2>
              <ul className="list-disc list-inside space-y-1 text-sm text-zinc-200">
                {briefing.signal_highlights.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
            </section>
          )}

          {briefing.impact_summary && (
            <div className="flex flex-wrap gap-2">
              {impactChip("high", briefing.impact_summary.high ?? 0)}
              {impactChip("moderate", briefing.impact_summary.moderate ?? 0)}
              {impactChip("noise", briefing.impact_summary.noise ?? 0)}
            </div>
          )}

          {briefing.release_stats &&
            (briefing.release_stats.beats > 0 ||
              briefing.release_stats.misses > 0 ||
              briefing.release_stats.inline > 0) && (
              <p className="text-xs text-zinc-500 font-mono">
                Releases: {briefing.release_stats.beats} beat · {briefing.release_stats.misses}{" "}
                miss · {briefing.release_stats.inline} inline
              </p>
            )}

          {briefing.headline_events && briefing.headline_events.length > 0 && (
            <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <h2 className="text-sm font-medium text-zinc-300 mb-3">Headline events</h2>
              <ul className="list-disc list-inside space-y-1 text-sm text-zinc-200">
                {briefing.headline_events.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
            </section>
          )}

          {briefing.macro_news && briefing.macro_news.length > 0 && (
            <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <h2 className="text-sm font-medium text-zinc-300 mb-3">Market headlines</h2>
              <ul className="space-y-2 text-sm">
                {briefing.macro_news.map((n, i) => (
                  <li key={i} className="text-zinc-300">
                    {n.url ? (
                      <a
                        href={n.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-400 hover:underline"
                      >
                        {n.title}
                      </a>
                    ) : (
                      n.title
                    )}
                    <span className="text-xs text-zinc-500 ml-2">
                      {n.source ?? "news"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {briefing.summary && (
            <section className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-5">
              <h2 className="text-sm font-medium text-emerald-400 mb-3">Summary</h2>
              <ul className="list-disc list-inside space-y-2">
                {briefing.summary.bullets.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </section>
          )}

          {briefing.sector_watch && briefing.sector_watch.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-zinc-300 mb-2">Sector watch</h2>
              <ul className="text-sm space-y-1 text-zinc-400 list-disc list-inside">
                {briefing.sector_watch.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
          )}

          {briefing.watchlist_exposure && briefing.watchlist_exposure.length > 0 && (
            <section className="rounded-lg border border-blue-900/40 bg-blue-950/20 p-5">
              <h2 className="text-sm font-medium text-blue-400 mb-2">Watchlist exposure</h2>
              <ul className="text-sm space-y-1 text-zinc-300 list-disc list-inside">
                {briefing.watchlist_exposure.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </section>
          )}

          {briefing.data_gaps && briefing.data_gaps.length > 0 && (
            <section className="rounded border border-zinc-800">
              <button
                type="button"
                onClick={() => setGapsOpen((o) => !o)}
                className="w-full text-left px-4 py-2 text-xs text-zinc-500 hover:bg-zinc-900/50"
              >
                Data gaps ({briefing.data_gaps.length}) {gapsOpen ? "▾" : "▸"}
              </button>
              {gapsOpen && (
                <ul className="px-4 pb-3 text-xs text-zinc-600 font-mono space-y-1">
                  {briefing.data_gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {briefing.empty_message && briefing.events.length === 0 ? (
            <p className="text-sm text-zinc-500">{briefing.empty_message}</p>
          ) : briefing.events.length > 0 ? (
            <section>
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <h2 className="text-sm font-medium text-zinc-300">Event calendar</h2>
                <div className="flex gap-1 text-xs">
                  {(["actionable", "high", "all"] as ImpactFilter[]).map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setFilter(f)}
                      className={`rounded px-2.5 py-1 capitalize ${
                        filter === f
                          ? "bg-emerald-600 text-white"
                          : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                      }`}
                    >
                      {f === "actionable" ? "High + Moderate" : f}
                    </button>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-left text-zinc-500 border-b border-zinc-800">
                      <th className="py-2 pr-4">Event</th>
                      <th className="py-2 pr-4">Time</th>
                      <th className="py-2 pr-4">Impact</th>
                      <th className="py-2 pr-4">Actual</th>
                      <th className="py-2 pr-4">Estimate</th>
                      <th className="py-2 pr-4">Prior</th>
                      <th className="py-2 pr-4">Surprise</th>
                      <th className="py-2 pr-4">Beat/Miss</th>
                      <th className="py-2 pr-4">Sectors</th>
                      <th className="py-2 pr-4">Source</th>
                      <th className="py-2">Playbook</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEvents.map((ev) => (
                      <tr
                        key={`${ev.name}-${ev.time_et ?? ""}`}
                        className={`border-b border-zinc-800/50 ${
                          ev.impact === "high" ? "bg-red-950/10" : ""
                        }`}
                      >
                        <td className="py-2 pr-4 font-medium">{ev.name}</td>
                        <td className="py-2 pr-4 font-mono text-xs text-zinc-500">
                          {ev.time_et ?? "—"}
                        </td>
                        <td className="py-2 pr-4 capitalize">{ev.impact}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{fmtNum(ev.actual)}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{fmtNum(ev.estimate)}</td>
                        <td className="py-2 pr-4 font-mono text-xs">{fmtNum(ev.prior)}</td>
                        <td className="py-2 pr-4 font-mono text-xs">
                          {fmtPct(ev.surprise_pct)}
                        </td>
                        <td className="py-2 pr-4 capitalize text-xs">{ev.beat_miss ?? "—"}</td>
                        <td className="py-2 pr-4 text-zinc-400">{ev.sectors.join(", ")}</td>
                        <td className="py-2 pr-4 text-xs text-zinc-500 capitalize">
                          {ev.source ?? "—"}
                        </td>
                        <td className="py-2 text-zinc-400 text-xs max-w-xs">
                          {ev.playbook ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
