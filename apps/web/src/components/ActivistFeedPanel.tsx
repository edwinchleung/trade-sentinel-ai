"use client";

import Link from "next/link";
import type { ActivistFeed } from "@/lib/api";
import { SmartMoneyPagination } from "@/components/smart-money/SmartMoneyPagination";
import { useClientPagination } from "@/components/smart-money/useClientPagination";

type FormFilter = "all" | "13d" | "13g";

type Props = {
  feed: ActivistFeed | null;
  formFilter: FormFilter;
  onFormFilter: (f: FormFilter) => void;
  onRefresh?: () => void;
  loading?: boolean;
};

const FORM_OPTIONS: { id: FormFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "13d", label: "13D activist" },
  { id: "13g", label: "13G passive" },
];

export function ActivistFeedPanel({
  feed,
  formFilter,
  onFormFilter,
  onRefresh,
  loading,
}: Props) {
  const items = feed?.items ?? [];
  const { page, setPage, pageCount, pageRows, rangeStart, rangeEnd, total } =
    useClientPagination(items, {
      resetKey: `${feed?.as_of ?? ""}:${formFilter}`,
    });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        {FORM_OPTIONS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => onFormFilter(f.id)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              formFilter === f.id
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {f.label}
          </button>
        ))}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-300 hover:border-zinc-500 disabled:opacity-50"
          >
            {loading ? "Fetching…" : "Refresh"}
          </button>
        )}
      </div>

      {loading && <p className="text-sm text-zinc-500">Loading 13D/G feed…</p>}

      {!loading && feed && (
        <p className="text-xs text-zinc-500">
          {feed.items.length} filing(s) in last {feed.days_window} day(s)
          {" · "}As of {new Date(feed.as_of).toLocaleString()}
        </p>
      )}

      {!loading && feed?.message && (
        <p className="text-sm text-zinc-500">{feed.message}</p>
      )}

      {items.length > 0 && (
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
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Form</th>
                  <th className="px-3 py-2">Ticker</th>
                  <th className="px-3 py-2">Company</th>
                  <th className="px-3 py-2">Filer</th>
                  <th className="px-3 py-2">%</th>
                  <th className="px-3 py-2">Signal</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((item, i) => (
                  <tr
                    key={`${rangeStart + i}-${item.filing_date}-${item.form_type}-${item.ticker ?? ""}`}
                    className="border-t border-zinc-800/80"
                  >
                    <td className="px-3 py-2 text-zinc-400">{item.filing_date}</td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          item.form_type === "13D" ? "text-amber-400" : "text-zinc-400"
                        }
                      >
                        {item.form_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono">
                      {item.ticker ? (
                        <Link
                          href={`/context?ticker=${item.ticker}`}
                          className="text-emerald-400 hover:underline"
                        >
                          {item.ticker}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-3 py-2 text-zinc-300">{item.company_name ?? "—"}</td>
                    <td className="px-3 py-2 text-zinc-400">{item.filer_name ?? "—"}</td>
                    <td className="px-3 py-2 text-zinc-400">
                      {item.percent_owned != null ? `${item.percent_owned}%` : "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-zinc-500">{item.signal ?? "—"}</td>
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
