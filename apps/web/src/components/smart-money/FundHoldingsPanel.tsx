"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { fetchFundHoldings, type FundHoldingsSnapshot } from "@/lib/api";

const ETF_PRESETS = ["SPY", "QQQ", "ARKK", "IWM", "VTI"];

export function FundHoldingsPanel({ loading: externalLoading }: { loading?: boolean }) {
  const [ticker, setTicker] = useState("SPY");
  const [input, setInput] = useState("SPY");
  const [snapshot, setSnapshot] = useState<FundHoldingsSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (sym: string) => {
    const symbol = sym.trim().toUpperCase();
    if (!symbol) return;
    setLoading(true);
    setError(null);
    setTicker(symbol);
    try {
      setSnapshot(await fetchFundHoldings(symbol));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load N-PORT holdings");
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const busy = loading || externalLoading;

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        SEC Form N-PORT fund-level holdings for ETFs and mutual funds. Requires N-PORT bulk ingest or
        live EdgarTools fallback.
      </p>

      <div className="flex flex-wrap gap-2 items-center">
        {ETF_PRESETS.map((sym) => (
          <button
            key={sym}
            type="button"
            onClick={() => {
              setInput(sym);
              load(sym);
            }}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              ticker === sym
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {sym}
          </button>
        ))}
        <form
          className="flex gap-2 ml-auto"
          onSubmit={(e) => {
            e.preventDefault();
            load(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            placeholder="ETF ticker"
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm font-mono w-24"
          />
          <button
            type="submit"
            className="rounded border border-zinc-600 px-3 py-1 text-xs text-zinc-300 hover:border-zinc-400"
          >
            Load
          </button>
        </form>
      </div>

      {busy && <p className="text-sm text-zinc-500">Loading N-PORT holdings…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {snapshot && !busy && (
        <div className="space-y-3">
          <div className="text-sm text-zinc-400">
            {snapshot.fund_name ?? snapshot.fund_ticker}
            {snapshot.report_date ? ` · report ${snapshot.report_date}` : ""}
            {snapshot.equity_pct != null ? ` · ${snapshot.equity_pct.toFixed(0)}% equity` : ""}
          </div>

          {!snapshot.data_available ? (
            <p className="text-sm text-zinc-500">
              {snapshot.message ?? "No N-PORT data for this fund ticker."}
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead className="bg-zinc-900/80 text-zinc-500 text-left">
                  <tr>
                    <th className="px-3 py-2">Holding</th>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2">Fair value</th>
                    <th className="px-3 py-2">% NAV</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.holdings.slice(0, 25).map((h, i) => (
                    <tr key={`${h.ticker ?? h.cusip}-${i}`} className="border-t border-zinc-800/80">
                      <td className="px-3 py-2 font-mono">
                        {h.ticker ? (
                          <Link
                            href={`/context?ticker=${h.ticker}`}
                            className="text-emerald-400 hover:underline"
                          >
                            {h.ticker}
                          </Link>
                        ) : (
                          <span className="text-zinc-500">{h.cusip ?? "—"}</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-zinc-400">{h.asset_category ?? "—"}</td>
                      <td className="px-3 py-2 text-zinc-300">
                        {h.fair_value_usd != null
                          ? `$${(h.fair_value_usd / 1_000_000).toFixed(2)}M`
                          : "—"}
                      </td>
                      <td className="px-3 py-2 text-zinc-400">
                        {h.pct_of_nav != null ? `${h.pct_of_nav.toFixed(2)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
