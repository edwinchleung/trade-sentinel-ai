"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import type { InstitutionalConvictionScan } from "@/lib/api";
import {
  SmartMoneyDataTable,
  SmartMoneyTableBody,
  SmartMoneyTableHead,
} from "@/components/smart-money/SmartMoneyDataTable";
import { SmartMoneyPanelMeta } from "@/components/smart-money/SmartMoneyPanelMeta";
import { SmartMoneyPagination } from "@/components/smart-money/SmartMoneyPagination";
import { InstitutionalChangeTimeline } from "@/components/smart-money/InstitutionalChangeTimeline";
import { useClientPagination } from "@/components/smart-money/useClientPagination";
import { SignalPills } from "@/components/smart-money/SignalPills";

type Props = {
  scan: InstitutionalConvictionScan | null;
  loading?: boolean;
};

function changeTone(type: string) {
  if (type === "new") return "text-emerald-400";
  if (type === "increased") return "text-teal-400";
  if (type === "exit" || type === "decreased") return "text-red-400";
  return "text-zinc-400";
}

function fmtMoney(n: number | null | undefined) {
  if (n == null) return null;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function InstitutionalConvictionPanel({ scan, loading }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const rows = scan?.rows ?? [];
  const { page, setPage, pageCount, pageRows, rangeStart, rangeEnd, total } =
    useClientPagination(rows, { resetKey: scan?.as_of ?? "" });

  return (
    <div className="space-y-4">
      <SmartMoneyPanelMeta
        disclaimer={
          scan?.disclaimer ??
          "13F data is quarterly and up to 45 days delayed after quarter end."
        }
        loading={loading}
        loadingLabel="Loading 13F conviction scan…"
        meta={
          scan
            ? `Last scan ${new Date(scan.as_of).toLocaleString()}${
                scan.rows.length > 0 ? ` · ${scan.rows.length} conviction ticker(s)` : ""
              }${
                scan.filers_refreshed != null
                  ? ` · ${scan.filers_refreshed} filer(s) refreshed`
                  : ""
              }${
                scan.data_scope === "full_universe" ? " · full 13F universe" : " · tracked filers only"
              }`
            : undefined
        }
        message={
          !loading
            ? scan?.message ??
              (scan && scan.rows.length === 0
                ? "No conviction buys among tracked filers in the current quarter window."
                : undefined)
            : undefined
        }
        messageTone={
          scan?.message && /unavailable/i.test(scan.message) ? "warn" : "muted"
        }
      />

      {scan && rows.length > 0 && (
        <div className="space-y-3">
          <SmartMoneyPagination
            page={page}
            pageCount={pageCount}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            total={total}
            onPageChange={setPage}
          />

          <SmartMoneyDataTable>
            <SmartMoneyTableHead>
              <tr>
                <th className="px-3 py-2 w-8"></th>
                <th className="px-3 py-2">Ticker</th>
                <th className="px-3 py-2">Funds</th>
                <th className="px-3 py-2">Holders</th>
                <th className="px-3 py-2">Lead change</th>
                <th className="px-3 py-2">Top filers</th>
                <th className="px-3 py-2">Quarter</th>
                <th className="px-3 py-2"></th>
              </tr>
            </SmartMoneyTableHead>
            <SmartMoneyTableBody>
              {pageRows.map((row) => {
                const open = expanded === row.ticker;
                return (
                  <Fragment key={row.ticker}>
                    <tr className="border-t border-zinc-800/80">
                      <td className="px-2 py-2">
                        {(row.filer_changes?.length ?? row.filer_previews?.length ?? 0) > 0 && (
                          <button
                            type="button"
                            onClick={() => setExpanded(open ? null : row.ticker)}
                            className="text-zinc-500 hover:text-zinc-300 text-xs"
                            aria-expanded={open}
                          >
                            {open ? "▼" : "▶"}
                          </button>
                        )}
                      </td>
                      <td className="px-3 py-2 font-mono">
                        <Link
                          href={`/context?ticker=${row.ticker}`}
                          className="text-emerald-400 hover:underline"
                        >
                          {row.ticker}
                        </Link>
                        <div className="mt-1">
                          <SignalPills conviction={row.conviction_buy} />
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <span className="inline-flex min-w-[1.75rem] justify-center rounded-full border border-zinc-700 bg-zinc-900/60 px-2 py-0.5 text-xs text-zinc-300">
                          {row.filer_count}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-zinc-400">
                        {row.holder_count != null ? (
                          <>
                            <span className="text-zinc-300">{row.holder_count}</span>
                            {row.holder_count_delta != null && (
                              <span
                                className={
                                  row.holder_count_delta >= 0
                                    ? "text-emerald-500 ml-1"
                                    : "text-red-400 ml-1"
                                }
                              >
                                ({row.holder_count_delta >= 0 ? "+" : ""}
                                {row.holder_count_delta})
                              </span>
                            )}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-zinc-400 max-w-[200px]">
                        {row.headline_filer && (
                          <span className="block text-zinc-300">{row.headline_filer}</span>
                        )}
                        <span className="capitalize">{row.strongest_change ?? "—"}</span>
                        {row.headline_value_usd != null && (
                          <span className="block text-zinc-500">
                            {fmtMoney(row.headline_value_usd)}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1 max-w-[220px]">
                          {(row.top_filers ?? []).map((f) => (
                            <span
                              key={f}
                              className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-400 truncate max-w-[100px]"
                              title={f}
                            >
                              {f}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-xs text-zinc-500">
                        {row.quarter_end ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        <Link
                          href={`/context?ticker=${row.ticker}`}
                          className="text-xs text-zinc-500 hover:text-emerald-400"
                        >
                          Context
                        </Link>
                      </td>
                    </tr>
                    {open && (row.filer_changes?.length ?? row.filer_previews?.length ?? 0) > 0 && (
                      <tr
                        className="border-t border-zinc-800/40 bg-zinc-950/40"
                      >
                        <td />
                        <td colSpan={7} className="px-3 py-3">
                          <p className="text-[10px] uppercase tracking-wide text-zinc-600 mb-2">
                            Institutional quarter activity
                          </p>
                          {row.filer_changes && row.filer_changes.length > 0 ? (
                            <InstitutionalChangeTimeline changes={row.filer_changes} />
                          ) : (
                            row.filer_previews?.map((preview, idx) => (
                              <div key={`${row.ticker}-${idx}`} className="text-xs mb-2">
                                <span className="text-zinc-300">{preview.filer_name}</span>
                                {" · "}
                                <span className={changeTone(String(preview.change_type ?? ""))}>
                                  {preview.change_type}
                                </span>
                                {preview.pct_change != null && (
                                  <span className="text-zinc-500">
                                    {" "}
                                    ({Number(preview.pct_change) > 0 ? "+" : ""}
                                    {Number(preview.pct_change).toFixed(0)}%)
                                  </span>
                                )}
                              </div>
                            ))
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </SmartMoneyTableBody>
          </SmartMoneyDataTable>

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
