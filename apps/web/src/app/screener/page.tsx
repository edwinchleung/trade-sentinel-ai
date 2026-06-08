"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { JobStatusBanner } from "@/components/JobStatusBanner";
import { DigestRowPanel } from "@/components/DigestRowPanel";
import {
  fetchScreenerMarket,
  fetchScreenerWatchlist,
  triggerJobsRefresh,
  type DigestTickerRow,
  type ScreenerResult,
} from "@/lib/api";
import { useJobUpdates } from "@/hooks/useJobUpdates";
import { mergeRowsByTicker } from "@/lib/screenerFilters";

const PRESETS: { id: string; label: string }[] = [
  { id: "", label: "All" },
  { id: "undervalued", label: "Undervalued vs fair band" },
  { id: "earnings_week", label: "Earnings this week" },
  { id: "insider_accumulation", label: "Open-market insider accumulation" },
  { id: "insider_cluster_buy", label: "Insider cluster buy" },
  { id: "institutional_conviction", label: "Institutional conviction" },
  { id: "options_unusual", label: "Unusual options" },
  { id: "high_risk", label: "Above fair value" },
];

type MarketUniverse = "sp100" | "sp500";
type Universe = "watchlist" | MarketUniverse;

export default function ScreenerPage() {
  const [universe, setUniverse] = useState<Universe>("watchlist");
  const [preset, setPreset] = useState("");
  const [result, setResult] = useState<ScreenerResult | null>(null);
  const [allRows, setAllRows] = useState<DigestTickerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadSeqRef = useRef(0);
  const marketUniverseRef = useRef<string | null>(null);
  const universeRef = useRef<Universe>("watchlist");

  const marketUniverse = universe === "watchlist" ? null : universe;
  marketUniverseRef.current = marketUniverse;
  universeRef.current = universe;
  const wsChannels = useMemo(() => {
    const ch = ["jobs"];
    if (marketUniverse) ch.push(`screener:${marketUniverse}`);
    else ch.push("digest:default");
    return ch;
  }, [marketUniverse]);

  const load = useCallback(async (u: Universe, presetId: string, refresh = false) => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const presetOpt = presetId || undefined;
      const data =
        u === "watchlist"
          ? await fetchScreenerWatchlist({ refresh, preset: presetOpt })
          : await fetchScreenerMarket({ universe: u, refresh, preset: presetOpt });
      if (seq !== loadSeqRef.current) return;
      setResult(data);
      setAllRows(data.rows);
    } catch (e) {
      if (seq !== loadSeqRef.current) return;
      setError(e instanceof Error ? e.message : "Screener failed");
    } finally {
      if (seq === loadSeqRef.current) setLoading(false);
    }
  }, []);

  const wsHandlers = useMemo(
    () => ({
      onScreenerRows: (ev: { universe: string; rows: DigestTickerRow[]; completed: number }) => {
        const mu = marketUniverseRef.current;
        if (!mu || ev.universe !== mu) return;
        setAllRows((prev) => mergeRowsByTicker(prev, ev.rows));
        setResult((prev) =>
          prev
            ? { ...prev, stale: true, scanned_count: ev.completed }
            : {
                as_of: new Date().toISOString(),
                universe: mu as MarketUniverse,
                rows: [],
                stale: true,
                scanned_count: ev.completed,
              }
        );
      },
      onDigestRows: (ev: { watchlist_name: string; rows: DigestTickerRow[]; completed: number }) => {
        if (universeRef.current !== "watchlist" || ev.watchlist_name !== "default") return;
        setAllRows((prev) => mergeRowsByTicker(prev, ev.rows));
        setResult((prev) =>
          prev
            ? { ...prev, stale: true, scanned_count: ev.completed }
            : {
                as_of: new Date().toISOString(),
                universe: "watchlist",
                rows: [],
                stale: true,
                scanned_count: ev.completed,
              }
        );
      },
    }),
    []
  );

  const { status: jobStatus, scanProgress, connected } = useJobUpdates(wsChannels, wsHandlers);

  useEffect(() => {
    setAllRows([]);
    setResult(null);
    void load(universe, preset, false);
  }, [universe, preset, load]);

  const forceRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    setAllRows([]);
    try {
      const scope = universe === "watchlist" ? "watchlist" : "market";
      await triggerJobsRefresh(scope);
      await load(universe, preset, false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  }, [universe, preset, load]);

  const displayRows = allRows;
  const presetLabel = PRESETS.find((p) => p.id === preset)?.label ?? "All";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Screener</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Filter cached watchlist or S&P presets by premium vs fair mid, earnings, insider tone,
            and warnings. Digest shows the full watchlist without filters.
          </p>
        </div>
        <button
          type="button"
          onClick={() => forceRefresh()}
          disabled={loading}
          className="rounded border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 hover:border-zinc-500 disabled:opacity-50"
        >
          Force refresh
        </button>
      </div>

      <JobStatusBanner
        jobName={marketUniverse ? "market_screener" : "digest"}
        status={jobStatus}
        scanProgress={scanProgress}
        connected={connected}
        scanResource={marketUniverse ? "market_screener" : "digest"}
      />

      <div className="flex flex-wrap gap-2">
        {(
          [
            { id: "watchlist" as const, label: "Watchlist" },
            { id: "sp500" as const, label: "S&P 500 preset" },
            { id: "sp100" as const, label: "S&P 100 preset" },
          ] as const
        ).map((u) => (
          <button
            key={u.id}
            type="button"
            onClick={() => setUniverse(u.id)}
            className={
              universe === u.id
                ? "rounded-full bg-emerald-600/20 border border-emerald-700 px-3 py-1 text-xs text-emerald-300"
                : "rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-400 hover:border-zinc-500"
            }
          >
            {u.label}
          </button>
        ))}
      </div>

      {marketUniverse && (
        <p className="text-xs text-zinc-500">
          Curated {marketUniverse === "sp500" ? "~500" : "~100"} large caps — sector peer ranks use
          this cache when warm.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.id || "all"}
            type="button"
            onClick={() => setPreset(p.id)}
            className={
              preset === p.id
                ? "rounded-full bg-emerald-600/20 border border-emerald-700 px-3 py-1 text-xs text-emerald-300"
                : "rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-400 hover:border-zinc-500"
            }
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading && !result && (
        <p className="text-sm text-zinc-400">
          {marketUniverse ? "Loading cached market scan…" : "Loading cached watchlist…"}
        </p>
      )}
      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && (
        <>
          {result.stale && (
            <p className="text-sm text-amber-400/90">
              Cache warming — background scan running. New rows appear as each batch completes.
            </p>
          )}
          {result.cached_at && (
            <p className="text-xs text-zinc-500">
              Cache as of {new Date(result.cached_at).toLocaleString()}
            </p>
          )}
          <p className="text-xs text-zinc-500">
            Preset: {presetLabel}
            {result.scanned_count != null && result.scanned_count > 0 && (
              <> · Scanned {result.scanned_count}</>
            )}
            {displayRows.length > 0 && <> · {displayRows.length} shown</>}
          </p>
          {result.empty_message && displayRows.length === 0 && (
            <p className="text-sm text-zinc-400">{result.empty_message}</p>
          )}
          {displayRows.length > 0 && (
            <ul className="space-y-2">
              {displayRows.map((row) => (
                <li key={row.ticker}>
                  <DigestRowPanel row={row} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
