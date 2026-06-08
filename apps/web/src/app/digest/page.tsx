"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { JobStatusBanner } from "@/components/JobStatusBanner";
import { DigestRowPanel } from "@/components/DigestRowPanel";
import { fetchDigestToday, triggerJobsRefresh, type DigestToday } from "@/lib/api";
import { useJobUpdates } from "@/hooks/useJobUpdates";
import { mergeRowsByTicker } from "@/lib/screenerFilters";

const WS_CHANNELS = ["jobs", "digest:default"];

type SortKey = "ticker" | "mos_pct" | "change_pct";

export default function DigestPage() {
  const [digest, setDigest] = useState<DigestToday | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("mos_pct");

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      setDigest(await fetchDigestToday({ refresh }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load digest");
    } finally {
      setLoading(false);
    }
  }, []);

  const { status: jobStatus, scanProgress, connected } = useJobUpdates(WS_CHANNELS, {
    onDigestRows: (ev) => {
      if (ev.watchlist_name !== "default") return;
      setDigest((prev) => {
        const base = prev ?? {
          as_of: new Date().toISOString(),
          trading_date: "",
          watchlist_name: "default",
          tickers: [],
        };
        return {
          ...base,
          tickers: mergeRowsByTicker(base.tickers, ev.rows),
        };
      });
    },
  });

  const forceRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await triggerJobsRefresh("watchlist");
      await load(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh digest");
    } finally {
      setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  const sortedTickers = useMemo(() => {
    const rows = [...(digest?.tickers ?? [])];
    rows.sort((a, b) => {
      if (sortKey === "ticker") return a.ticker.localeCompare(b.ticker);
      const av = a[sortKey] ?? (sortKey === "mos_pct" ? 999 : -999);
      const bv = b[sortKey] ?? (sortKey === "mos_pct" ? 999 : -999);
      return (av as number) - (bv as number);
    });
    return rows;
  }, [digest?.tickers, sortKey]);

  const maxTickers = digest?.digest_max_tickers ?? 20;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Watchlist digest</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Full watchlist snapshot — fair band, sector ranks, earnings, and warnings. Use Screener
            for filtered presets.
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
        jobName="digest"
        status={jobStatus}
        scanProgress={scanProgress}
        connected={connected}
        scanResource="digest"
      />

      {loading && <p className="text-zinc-400 text-sm">Loading digest…</p>}
      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {digest && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
            <span>
              Trading day {digest.trading_date} · {digest.tickers.length} ticker(s)
            </span>
            <label className="flex items-center gap-1.5">
              Sort
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-zinc-300"
              >
                <option value="mos_pct">Cheapest vs fair mid</option>
                <option value="change_pct">Change %</option>
                <option value="ticker">Ticker A–Z</option>
              </select>
            </label>
          </div>
          {digest.tickers.length >= maxTickers && (
            <p className="text-xs text-amber-500/90">
              Showing up to {maxTickers} tickers. Raise DIGEST_MAX_TICKERS in .env to include more.
            </p>
          )}
          {digest.empty_message && digest.tickers.length === 0 && (
            <p className="text-sm text-zinc-400">{digest.empty_message}</p>
          )}
          {sortedTickers.length > 0 && (
            <ul className="space-y-2">
              {sortedTickers.map((row) => (
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
