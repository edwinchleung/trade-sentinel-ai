"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import type { InsiderScanRow, WatchlistInsiderPulseRow } from "@/lib/api";
import {
  SmartMoneyDataTable,
  SmartMoneyTableBody,
  SmartMoneyTableHead,
} from "@/components/smart-money/SmartMoneyDataTable";
import { InsiderActivityTimeline } from "@/components/smart-money/InsiderActivityTimeline";
import { SmartMoneyPagination } from "@/components/smart-money/SmartMoneyPagination";
import { useClientPagination } from "@/components/smart-money/useClientPagination";
import { SentimentBadge } from "@/components/smart-money/SentimentBadge";
import { SignalPills } from "@/components/smart-money/SignalPills";

export type InsiderAccumulationRow = InsiderScanRow | WatchlistInsiderPulseRow;

function fmtNet(n: number) {
  const prefix = n > 0 ? "+" : "";
  return `${prefix}${n.toLocaleString()}`;
}

function netClass(n: number) {
  if (n > 0) return "text-emerald-400";
  if (n < 0) return "text-red-400";
  return "text-zinc-300";
}

function rowTransactions(row: InsiderAccumulationRow) {
  return row.recent_transactions ?? [];
}

type Props = {
  rows: InsiderAccumulationRow[];
};

export function InsiderAccumulationTable({ rows }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { page, setPage, pageCount, pageRows, rangeStart, rangeEnd, total } =
    useClientPagination(rows, { resetKey: String(rows.length) });

  if (rows.length === 0) return null;

  return (
    <div className="space-y-3">
      <SmartMoneyPagination
        page={page}
        pageCount={pageCount}
        rangeStart={rangeStart}
        rangeEnd={rangeEnd}
        total={total}
        onPageChange={setPage}
      />

      <SmartMoneyDataTable sticky>
        <SmartMoneyTableHead>
          <tr>
            <th className="px-2 py-2 w-8"></th>
            <th className="px-3 py-2">Ticker</th>
            <th className="px-3 py-2">Sentiment</th>
            <th className="px-3 py-2">Net 90d</th>
            <th className="px-3 py-2">OM buys</th>
            <th className="px-3 py-2">Buys</th>
            <th className="px-3 py-2">Sells</th>
            <th className="px-3 py-2">Notable</th>
            <th className="px-3 py-2">Signals</th>
            <th className="px-3 py-2"></th>
          </tr>
        </SmartMoneyTableHead>
        <SmartMoneyTableBody>
          {pageRows.map((row) => {
            const txs = rowTransactions(row);
            const open = expanded === row.ticker;
            return (
              <Fragment key={row.ticker}>
                <tr className="border-t border-zinc-800/80">
                  <td className="px-2 py-2">
                    {txs.length > 0 && (
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
                  </td>
                  <td className="px-3 py-2">
                    <SentimentBadge sentiment={row.sentiment} />
                  </td>
                  <td className={`px-3 py-2 font-mono ${netClass(row.net_shares_90d ?? 0)}`}>
                    {fmtNet(row.net_shares_90d ?? 0)}
                  </td>
                  <td className="px-3 py-2 font-mono text-zinc-300">
                    {row.open_market_buy_count ?? "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-zinc-300">{row.buy_count}</td>
                  <td className="px-3 py-2 font-mono text-zinc-300">{row.sell_count}</td>
                  <td
                    className="px-3 py-2 text-xs text-zinc-400 max-w-[220px] truncate"
                    title={row.latest_notable ?? undefined}
                  >
                    {row.latest_notable ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <SignalPills cluster={row.cluster_buying} />
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/context?ticker=${row.ticker}`}
                      className="text-xs text-zinc-500 hover:text-emerald-400"
                    >
                      Analyze
                    </Link>
                  </td>
                </tr>
                {open && txs.length > 0 && (
                  <tr className="border-t border-zinc-800/40 bg-zinc-950/40">
                    <td />
                    <td colSpan={9} className="px-3 py-3">
                      <p className="text-[10px] uppercase tracking-wide text-zinc-600 mb-2">
                        Recent Form 4 activity (90d window)
                      </p>
                      <InsiderActivityTimeline transactions={txs} compact />
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
  );
}
