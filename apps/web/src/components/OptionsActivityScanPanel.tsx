"use client";

import Link from "next/link";
import type { OptionsScanResult, ScanUniverse } from "@/lib/api";
import { SmartMoneyPagination } from "@/components/smart-money/SmartMoneyPagination";
import { useClientPagination } from "@/components/smart-money/useClientPagination";

type Props = {
  scan: OptionsScanResult;
  universe: ScanUniverse;
  onUniverse: (u: ScanUniverse) => void;
  signalsOnly: boolean;
  onSignalsOnly: (v: boolean) => void;
  loading?: boolean;
  bannerMessage?: string | null;
};

const UNIVERSE_OPTIONS: { id: ScanUniverse; label: string }[] = [
  { id: "sp500", label: "S&P 500" },
  { id: "sp100", label: "S&P 100" },
  { id: "watchlist", label: "Watchlist" },
];

export function OptionsActivityScanPanel({
  scan,
  universe,
  onUniverse,
  signalsOnly,
  onSignalsOnly,
  loading,
  bannerMessage,
}: Props) {
  const { page, setPage, pageCount, pageRows, rangeStart, rangeEnd, total } =
    useClientPagination(scan.rows, {
      resetKey: `${scan.as_of}|${universe}|${signalsOnly}`,
    });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        {UNIVERSE_OPTIONS.map((u) => (
          <button
            key={u.id}
            type="button"
            onClick={() => onUniverse(u.id)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              universe === u.id
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {u.label}
          </button>
        ))}
        <span className="text-zinc-600 mx-1">|</span>
        <button
          type="button"
          onClick={() => onSignalsOnly(true)}
          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
            signalsOnly
              ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
              : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
          }`}
        >
          Signals only
        </button>
        <button
          type="button"
          onClick={() => onSignalsOnly(false)}
          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
            !signalsOnly
              ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
              : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
          }`}
        >
          Show all
        </button>
      </div>

      <p className="text-xs text-zinc-500">{scan.disclaimer}</p>

      {loading && <p className="text-sm text-zinc-500">Scanning options chains…</p>}

      {!loading && (
        <p className="text-xs text-zinc-500">
          Scanned {scan.scanned_count} ticker(s)
          {scan.fetched_count != null && scan.fetched_count > 0
            ? ` · ${scan.fetched_count} with options data`
            : ""}
          {scan.partial ? " · scan in progress" : ""}
          {" · "}Last scan {new Date(scan.as_of).toLocaleString()}
        </p>
      )}

      {bannerMessage && (
        <p className="text-sm text-amber-400/90">{bannerMessage}</p>
      )}

      {!loading && scan.provider_degraded && (
        <p className="text-sm text-amber-400/90">
          Market data provider throttled — scanned {scan.scanned_count} tickers but fetched 0.
          Retry shortly or wait for the next background scan.
        </p>
      )}

      {!loading && scan.message && (
        <p className="text-sm text-zinc-500">
          {scan.message}
          {/could not be fetched/i.test(scan.message) && (
            <span className="block text-xs text-zinc-600 mt-1">
              Scanned {scan.scanned_count} · fetched {scan.fetched_count ?? 0}. Provider may be
              rate-limited after large universe scans.
            </span>
          )}
          {signalsOnly &&
            universe !== "watchlist" &&
            /no unusual/i.test(scan.message) && (
              <span className="block text-xs text-zinc-600 mt-1">
                Try &quot;Show all&quot; or switch to Watchlist to see every ticker with valid
                options data.
              </span>
            )}
        </p>
      )}

      {scan.rows.length > 0 && (
        <div className="space-y-3">
          <SmartMoneyPagination
            page={page}
            pageCount={pageCount}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            total={total}
            onPageChange={setPage}
          />

          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-900/80 text-zinc-500 text-left">
                <tr>
                  <th className="px-3 py-2">Ticker</th>
                  <th className="px-3 py-2">P/C</th>
                  <th className="px-3 py-2">Unusual</th>
                  <th className="px-3 py-2">Sweeps</th>
                  <th className="px-3 py-2">Top strike</th>
                  <th className="px-3 py-2">Vol/OI</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row) => (
                <tr key={row.ticker} className="border-t border-zinc-800/80">
                  <td className="px-3 py-2 font-mono">
                    <Link
                      href={`/context?ticker=${row.ticker}`}
                      className="text-emerald-400 hover:underline"
                    >
                      {row.ticker}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-zinc-300">
                    {row.put_call_ratio != null ? row.put_call_ratio.toFixed(2) : "—"}
                  </td>
                  <td className="px-3 py-2">
                    {row.unusual ? (
                      <span className="text-amber-400 text-xs">{row.unusual_reason ?? "Yes"}</span>
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {(row.sweep_count ?? 0) > 0 ? (
                      <span className="text-violet-400">{row.sweep_count} sweep(s)</span>
                    ) : row.data_source === "polygon_ticks" ? (
                      <span className="text-zinc-600">0</span>
                    ) : (
                      <span className="text-zinc-600" title="Aggregate fallback — no tick sweeps">
                        —
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-zinc-400">
                    {row.top_strike_summary ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-zinc-400">
                    {row.max_vol_oi_ratio != null ? `${row.max_vol_oi_ratio.toFixed(1)}x` : "—"}
                  </td>
                </tr>
                ))}
              </tbody>
            </table>
          </div>

          <SmartMoneyPagination
            page={page}
            pageCount={pageCount}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            total={total}
            onPageChange={setPage}
          />
        </div>
      )}
    </div>
  );
}
