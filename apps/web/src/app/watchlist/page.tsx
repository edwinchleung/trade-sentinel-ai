"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  fetchDigestToday,
  fetchWatchlist,
  patchWatchlistTickers,
  type DigestToday,
  type Watchlist,
} from "@/lib/api";
import { useJobUpdates } from "@/hooks/useJobUpdates";
import { mergeRowsByTicker } from "@/lib/screenerFilters";

const DIGEST_MAX_TICKERS = 20;

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null);
  const [digest, setDigest] = useState<DigestToday | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDigest = useCallback(async (refresh = false) => {
    setDigest(await fetchDigestToday({ refresh }));
  }, []);

  useJobUpdates(["jobs", "digest:default"], {
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
    onJobFinished: (name, status) => {
      if (status === "ok" && name === "digest") loadDigest(false);
    },
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const wl = await fetchWatchlist();
      setWatchlist(wl);
      await loadDigest(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, [loadDigest]);

  useEffect(() => {
    load();
  }, [load]);

  const savePatch = async (patch: { add?: string[]; remove?: string[] }) => {
    setSaving(true);
    setError(null);
    try {
      const wl = await patchWatchlistTickers(patch);
      setWatchlist(wl);
      await loadDigest(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save watchlist");
    } finally {
      setSaving(false);
    }
  };

  const onAdd = async (e: FormEvent) => {
    e.preventDefault();
    const symbol = input.trim().toUpperCase();
    if (!symbol || !watchlist || saving) return;
    if (watchlist.tickers.includes(symbol)) {
      setInput("");
      return;
    }
    setInput("");
    await savePatch({ add: [symbol] });
  };

  const onRemove = async (symbol: string) => {
    if (!watchlist || saving) return;
    await savePatch({ remove: [symbol] });
  };

  const truncated =
    watchlist && watchlist.tickers.length > DIGEST_MAX_TICKERS;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Watchlist</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Tickers you track — digest and screener run automatically; context opens with auto-analyze.
        </p>
      </div>

      <form onSubmit={onAdd} className="flex flex-wrap gap-3 items-end">
        <label className="flex flex-col gap-1 text-sm">
          Add ticker
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            placeholder="NVDA"
            disabled={saving}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 font-mono uppercase w-32"
          />
        </label>
        <button
          type="submit"
          disabled={!input.trim() || saving}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Add"}
        </button>
      </form>

      {truncated && (
        <p className="text-xs text-amber-500/90">
          Digest, screener, and smart-money scan the first {DIGEST_MAX_TICKERS} tickers
          (alphabetically). You have {watchlist.tickers.length} saved — raise DIGEST_MAX_TICKERS
          in .env to include more.
        </p>
      )}

      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading && <p className="text-zinc-400 text-sm">Loading…</p>}

      {!loading && watchlist && (
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
          {watchlist.tickers.length === 0 ? (
            <p className="text-sm text-zinc-500">No tickers yet. Add one above.</p>
          ) : (
            <ul className="space-y-2">
              {watchlist.tickers.map((symbol) => {
                const row = digest?.tickers.find((t) => t.ticker === symbol);
                return (
                <li
                  key={symbol}
                  className="flex items-center justify-between gap-4 text-sm"
                >
                  <div className="flex items-center gap-2 flex-wrap">
                  <Link
                    href={`/context?ticker=${symbol}`}
                    className="font-mono text-emerald-400 hover:underline"
                  >
                    {symbol}
                  </Link>
                  {row?.top_warning === "PRICE_ABOVE_FAIR_VALUE" && (
                    <span className="text-[10px] rounded border border-amber-800 text-amber-400 px-1.5">
                      Above fair band
                    </span>
                  )}
                  {row?.mos_pct != null && (
                    <span
                      className={
                        row.mos_label === "undervalued"
                          ? "text-[10px] text-emerald-500"
                          : row.mos_label === "overvalued"
                            ? "text-[10px] text-amber-400"
                            : "text-[10px] text-zinc-500"
                      }
                    >
                      {row.mos_pct >= 0 ? "+" : ""}
                      {row.mos_pct.toFixed(0)}% vs fair mid
                    </span>
                  )}
                  </div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => onRemove(symbol)}
                    className="text-zinc-500 hover:text-red-400 text-xs disabled:opacity-40"
                  >
                    Remove
                  </button>
                </li>
              );
              })}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
