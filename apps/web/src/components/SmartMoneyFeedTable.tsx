"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import type { SmartMoneyFeed, SmartMoneyFeedItem } from "@/lib/api";
import { itemStableId } from "@/lib/insiderFeedArchive";
import { applyClientFilters, type SideFilter } from "@/lib/insiderFeedFilters";
import { buildFeedPageEntries } from "@/components/smart-money/buildFeedPageEntries";
import { SmartMoneyChipGroup } from "@/components/smart-money/SmartMoneyChipGroup";
import {
  SmartMoneyDataTable,
  SmartMoneyTableBody,
  SmartMoneyTableHead,
} from "@/components/smart-money/SmartMoneyDataTable";
import { SmartMoneyPagination } from "@/components/smart-money/SmartMoneyPagination";
import { useClientPagination } from "@/components/smart-money/useClientPagination";
import { SignalPills } from "@/components/smart-money/SignalPills";
import { TransactionCodeBadge } from "@/components/smart-money/TransactionCodeBadge";
import {
  InsiderFeedDateRange,
  type FeedDateRange,
} from "@/components/InsiderFeedDateRange";

type FormTypeFilter = "4" | "3" | "5" | "all";

type Props = {
  feed: SmartMoneyFeed;
  items: SmartMoneyFeedItem[];
  sideFilter: SideFilter;
  onSideFilter: (f: SideFilter) => void;
  formTypeFilter: FormTypeFilter;
  onFormTypeFilter: (f: FormTypeFilter) => void;
  openMarketOnly: boolean;
  onOpenMarketOnly: (v: boolean) => void;
  dateRange: FeedDateRange;
  onDateRangeChange: (r: FeedDateRange) => void;
  archiveCount?: number;
  archiveUpdatedAt?: string | null;
  onClearArchive?: () => void;
  onRefresh?: () => void;
  loading?: boolean;
};

const sideStyles: Record<string, string> = {
  buy: "text-emerald-400",
  sell: "text-red-400",
  other: "text-zinc-400",
};

function fmtMoney(n: number | null | undefined) {
  if (n == null) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function SmartMoneyFeedTable({
  feed,
  items,
  sideFilter,
  onSideFilter,
  formTypeFilter,
  onFormTypeFilter,
  openMarketOnly,
  onOpenMarketOnly,
  dateRange,
  onDateRangeChange,
  archiveCount,
  archiveUpdatedAt,
  onClearArchive,
  onRefresh,
  loading,
}: Props) {
  const [sortBy, setSortBy] = useState<"date" | "notional">("date");

  const sideChips = [
    { id: "all", label: "All sides" },
    { id: "buy", label: "Buys" },
    { id: "sell", label: "Sells" },
    { id: "notable", label: "Notable (>$1M)" },
    { id: "cluster", label: "Cluster buys" },
  ] as const;

  const formChips = [
    { id: "4", label: "Form 4" },
    { id: "all", label: "All forms" },
    { id: "3", label: "Form 3" },
    { id: "5", label: "Form 5" },
  ] as const;

  const filtered = useMemo(() => {
    let rows = applyClientFilters(items, sideFilter, openMarketOnly);
    if (formTypeFilter !== "all") {
      rows = rows.filter((i) => (i.source_form ?? "4") === formTypeFilter);
    }
    return rows;
  }, [items, sideFilter, openMarketOnly, formTypeFilter]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    if (sortBy === "notional") {
      copy.sort((a, b) => (b.notional ?? 0) - (a.notional ?? 0));
    } else {
      copy.sort((a, b) => b.filing_date.localeCompare(a.filing_date));
    }
    return copy;
  }, [filtered, sortBy]);

  const paginationResetKey = `${sideFilter}|${formTypeFilter}|${openMarketOnly}|${sortBy}|${dateRange.start}|${dateRange.end}`;
  const {
    page,
    setPage,
    pageCount,
    pageRows,
    rangeStart,
    rangeEnd,
    total,
  } = useClientPagination(sorted, { resetKey: paginationResetKey });

  const groupByDate = dateRange.start !== dateRange.end;

  const pageEntries = useMemo(
    () => buildFeedPageEntries(pageRows, groupByDate),
    [pageRows, groupByDate]
  );

  const stats = useMemo(() => {
    const buys = filtered.filter((i) => i.side === "buy").length;
    const sells = filtered.filter((i) => i.side === "sell").length;
    const notionals = filtered.map((i) => i.notional).filter((n): n is number => n != null);
    const totalNotional = notionals.length ? notionals.reduce((a, b) => a + b, 0) : null;
    return { buys, sells, totalNotional, count: filtered.length };
  }, [filtered]);

  return (
    <div className="space-y-4">
      <InsiderFeedDateRange range={dateRange} onChange={onDateRangeChange} />

      <div className="flex flex-wrap gap-2 items-center justify-between">
        <SmartMoneyChipGroup
          chips={[...sideChips]}
          activeId={sideFilter}
          onSelect={(id) => onSideFilter(id as SideFilter)}
        />
        <SmartMoneyChipGroup
          chips={[...formChips]}
          activeId={formTypeFilter}
          onSelect={(id) => onFormTypeFilter(id as FormTypeFilter)}
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onOpenMarketOnly(true)}
            className={`rounded-full border px-3 py-1 text-xs ${
              openMarketOnly
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-zinc-700 text-zinc-400"
            }`}
          >
            Open market only
          </button>
          <button
            type="button"
            onClick={() => onOpenMarketOnly(false)}
            className={`rounded-full border px-3 py-1 text-xs ${
              !openMarketOnly
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-zinc-700 text-zinc-400"
            }`}
          >
            Include grants &amp; exercises
          </button>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-300 hover:border-zinc-500 disabled:opacity-50"
            >
              {loading ? "Fetching…" : "Fetch range"}
            </button>
          )}
        </div>
      </div>

      <div className="rounded border border-zinc-800/80 bg-zinc-900/30 px-3 py-2 text-xs text-zinc-500 flex flex-wrap gap-x-4 gap-y-1">
        <span>
          {total > 0 ? (
            <>
              Showing {rangeStart}–{rangeEnd} of {stats.count} filtered
              {archiveCount != null && archiveCount > 0 ? ` (${archiveCount} in archive)` : ""}
            </>
          ) : (
            <>0 trades match filters</>
          )}
          {stats.count > 0 && (
            <>
              {" · "}
              <span className="text-emerald-400">{stats.buys} buys</span> /{" "}
              <span className="text-red-400">{stats.sells} sells</span>
              {stats.totalNotional != null && ` · ${fmtMoney(stats.totalNotional)} notional`}
            </>
          )}
        </span>
        {archiveCount != null && archiveCount > 0 && archiveUpdatedAt && (
          <span>Archive updated {new Date(archiveUpdatedAt).toLocaleString()}</span>
        )}
        {feed.start_date && feed.end_date && (
          <span>
            SEC fetch: {feed.raw_entry_count ?? 0} filings · {feed.enriched_count ?? 0} parsed
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2 items-center text-xs">
        <span className="text-zinc-600">Sort:</span>
        <button
          type="button"
          onClick={() => setSortBy("date")}
          className={sortBy === "date" ? "text-emerald-400" : "text-zinc-500"}
        >
          Date ↓
        </button>
        <button
          type="button"
          onClick={() => setSortBy("notional")}
          className={sortBy === "notional" ? "text-emerald-400" : "text-zinc-500"}
        >
          Notional ↓
        </button>
        {onClearArchive && archiveCount != null && archiveCount > 0 && (
          <button
            type="button"
            onClick={onClearArchive}
            className="text-zinc-600 hover:text-zinc-400 ml-auto"
          >
            Clear local history
          </button>
        )}
      </div>

      {loading && <p className="text-sm text-zinc-500">Loading market feed…</p>}

      {!loading && feed.message && (
        <p
          className={`text-sm ${
            feed.sec_rate_limited || /unavailable/i.test(feed.message)
              ? "text-amber-400"
              : "text-zinc-500"
          }`}
        >
          {feed.message}
        </p>
      )}

      {!loading && filtered.length === 0 && (
        <p className="text-sm text-zinc-500">
          No trades match the current filters for {dateRange.start}–{dateRange.end}.
          {openMarketOnly && " Try &quot;Include grants &amp; exercises&quot; or expand the date range."}
        </p>
      )}

      {!loading &&
        dateRange.preset === "today" &&
        filtered.length === 0 &&
        (feed.raw_entry_count ?? 0) === 0 && (
          <p className="text-sm text-amber-400/90">
            Same-day Form 4 filings may lag on SEC. Try &quot;Last 7 days&quot; or &quot;Include
            grants &amp; exercises&quot;, then click Fetch range.
          </p>
        )}

      {!loading && filtered.length > 0 && (
        <>
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
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Ticker</th>
                <th className="px-3 py-2">Insider</th>
                <th className="px-3 py-2">Transaction</th>
                <th className="px-3 py-2">Side</th>
                <th className="px-3 py-2 hidden md:table-cell">Shares</th>
                <th className="px-3 py-2 hidden md:table-cell">Price</th>
                <th className="px-3 py-2 text-right">Notional</th>
                <th className="px-3 py-2">Signals</th>
                <th className="px-3 py-2"></th>
              </tr>
            </SmartMoneyTableHead>
            <SmartMoneyTableBody key={`${paginationResetKey}|${page}`}>
              {pageEntries.map((entry) => {
                if (entry.kind === "header") {
                  return (
                    <tr key={`hdr-${entry.date}`} className="bg-zinc-900/50">
                      <td
                        colSpan={10}
                        className="px-3 py-1.5 text-[10px] uppercase tracking-wide text-zinc-600"
                      >
                        {entry.date}
                      </td>
                    </tr>
                  );
                }
                const item = entry.item;
                return (
                  <Fragment key={itemStableId(item)}>
                    <tr className="border-t border-zinc-800/80">
                      <td className="px-3 py-2 text-zinc-400 whitespace-nowrap text-xs">
                        {item.filing_date.slice(0, 10)}
                      </td>
                      <td className="px-3 py-2">
                        {item.ticker ? (
                          <Link
                            href={`/context?ticker=${item.ticker}`}
                            className="font-mono text-emerald-400 hover:underline"
                          >
                            {item.ticker}
                          </Link>
                        ) : (
                          <span className="text-zinc-500 text-xs">{item.company_name ?? "—"}</span>
                        )}
                        {item.company_name && item.ticker && (
                          <span className="block text-[10px] text-zinc-600 truncate max-w-[120px]">
                            {item.company_name}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-zinc-300">
                        <span className="block text-sm">{item.insider_name ?? "—"}</span>
                        {item.title && (
                          <span className="block text-[10px] text-zinc-500">{item.title}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <TransactionCodeBadge
                          code={item.transaction_code}
                          transactionType={item.transaction_type}
                        />
                        {(item.source_form === "3" || item.source_form === "5") && (
                          <span className="ml-1 rounded border border-zinc-700 px-1 py-0.5 text-[10px] text-zinc-500">
                            F{item.source_form}
                          </span>
                        )}
                        {item.signal_type === "insider_appointment" && (
                          <span className="ml-1 rounded border border-sky-800/50 bg-sky-950/30 px-1 py-0.5 text-[10px] text-sky-400">
                            Appointment
                          </span>
                        )}
                      </td>
                      <td className={`px-3 py-2 capitalize text-sm ${sideStyles[item.side]}`}>
                        {item.side}
                      </td>
                      <td className="px-3 py-2 font-mono text-zinc-300 hidden md:table-cell">
                        {item.shares != null ? item.shares.toLocaleString() : "—"}
                      </td>
                      <td className="px-3 py-2 font-mono text-zinc-300 hidden md:table-cell">
                        {item.price != null ? `$${item.price.toFixed(2)}` : "—"}
                      </td>
                      <td
                        className={`px-3 py-2 font-mono text-right ${
                          item.is_notable ? "text-amber-300 font-medium" : "text-zinc-300"
                        }`}
                      >
                        {fmtMoney(item.notional)}
                      </td>
                      <td className="px-3 py-2">
                        <SignalPills notable={item.is_notable} cluster={item.cluster_buying} />
                      </td>
                      <td className="px-3 py-2">
                        {item.filing_url && (
                          <a
                            href={item.filing_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-emerald-400 hover:underline"
                          >
                            Filing
                          </a>
                        )}
                      </td>
                    </tr>
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
        </>
      )}
    </div>
  );
}
