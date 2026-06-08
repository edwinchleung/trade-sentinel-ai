"use client";

import Link from "next/link";
import type { DigestTickerRow } from "@/lib/api";
import { ValuationBandBar } from "@/components/ValuationBandBar";

const MOS_COLORS: Record<string, string> = {
  undervalued: "text-emerald-400",
  fair: "text-zinc-300",
  overvalued: "text-amber-400",
};

type Props = {
  row: DigestTickerRow;
  compact?: boolean;
};

export function DigestRowPanel({ row, compact = false }: Props) {
  const premiumClass = MOS_COLORS[row.mos_label ?? ""] ?? "text-zinc-300";

  return (
    <article className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3 space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/context?ticker=${row.ticker}`}
              className="font-mono text-emerald-400 hover:underline"
            >
              {row.ticker}
            </Link>
            {row.price != null && (
              <span className="text-sm text-zinc-200">${row.price.toFixed(2)}</span>
            )}
            {row.change_pct != null && (
              <span
                className={`text-sm ${row.change_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}
              >
                {row.change_pct >= 0 ? "+" : ""}
                {row.change_pct.toFixed(2)}%
              </span>
            )}
            {row.mos_pct != null && (
              <span className={`text-sm ${premiumClass}`}>
                {row.mos_pct >= 0 ? "+" : ""}
                {row.mos_pct.toFixed(1)}% vs fair mid
                {row.mos_label ? ` (${row.mos_label})` : ""}
              </span>
            )}
            {row.valuation_confidence && (
              <span className="rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] uppercase text-zinc-500">
                {row.valuation_confidence}
              </span>
            )}
          </div>
          {!compact &&
            row.fair_value_low != null &&
            row.fair_value_high != null && (
              <ValuationBandBar
                price={row.price}
                low={row.fair_value_low}
                mid={row.fair_value_mid}
                high={row.fair_value_high}
              />
            )}
          <div className="flex flex-wrap gap-1.5">
            {row.sector && (
              <span className="rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
                {row.sector}
              </span>
            )}
            {row.pe_forward != null && (
              <span className="rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
                Fwd P/E {row.pe_forward.toFixed(1)}
              </span>
            )}
            {row.pe_sector_percentile != null && (
              <span className="rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
                Sector {row.pe_sector_percentile.toFixed(0)}th pctile
              </span>
            )}
            {row.earnings_days != null && (
              <span className="rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
                Earnings {row.earnings_days}d
              </span>
            )}
            {row.insider_sentiment && (
              <span className="rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500 capitalize">
                Insider {row.insider_sentiment}
              </span>
            )}
            {row.top_warning && (
              <span className="rounded border border-amber-900/50 px-1.5 py-0.5 text-[10px] text-amber-400">
                {row.top_warning}
              </span>
            )}
          </div>
          {row.macro_headline && !compact && (
            <p className="text-xs text-zinc-500 line-clamp-1">{row.macro_headline}</p>
          )}
          {row.one_liner && (
            <p className="text-xs text-zinc-400 line-clamp-2">{row.one_liner}</p>
          )}
        </div>
        <Link
          href={`/context?ticker=${row.ticker}`}
          className="text-xs text-emerald-400 hover:underline shrink-0"
        >
          Context
        </Link>
      </div>
    </article>
  );
}
