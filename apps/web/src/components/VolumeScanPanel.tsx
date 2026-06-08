"use client";

import Link from "next/link";
import type { ScanUniverse, VolumeScanResult } from "@/lib/api";
import { SmartMoneyPagination } from "@/components/smart-money/SmartMoneyPagination";
import { useClientPagination } from "@/components/smart-money/useClientPagination";

type Props = {
  scan: VolumeScanResult;
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

export function VolumeScanPanel({
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

      <p className="text-xs text-zinc-500">
        OBV/A/D divergence and VWAP deviation from daily OHLCV.
      </p>

      {loading && <p className="text-sm text-zinc-500">Scanning volume footprint…</p>}

      {!loading && (
        <p className="text-xs text-zinc-500">
          Scanned {scan.scanned_count} ticker(s)
          {scan.fetched_count != null && scan.fetched_count > 0
            ? ` · ${scan.fetched_count} with OHLCV data`
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
            /no accumulation/i.test(scan.message) && (
              <span className="block text-xs text-zinc-600 mt-1">
                Try &quot;Show all&quot; or switch to Watchlist to see every ticker with valid
                volume data.
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
                  <th className="px-3 py-2">Stance</th>
                  <th className="px-3 py-2">OBV div</th>
                  <th className="px-3 py-2">VWAP dev</th>
                  <th className="px-3 py-2">RVOL</th>
                  <th className="px-3 py-2">Quiet acc.</th>
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
                  <td className="px-3 py-2 capitalize text-zinc-300">{row.stance}</td>
                  <td className="px-3 py-2 text-zinc-400">{row.obv_divergence ?? "—"}</td>
                  <td className="px-3 py-2 text-zinc-400">
                    {row.vwap_deviation_pct != null
                      ? `${row.vwap_deviation_pct.toFixed(1)}%`
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-zinc-400">
                    {row.volume_ratio != null ? `${row.volume_ratio}x` : "—"}
                  </td>
                  <td className="px-3 py-2">
                    {row.quiet_accumulation ? (
                      <span className="text-sky-400 text-xs">Yes</span>
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
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
