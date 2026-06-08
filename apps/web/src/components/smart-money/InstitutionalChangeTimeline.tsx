"use client";

import type { Institutional13FChange } from "@/lib/api";

type Props = {
  changes: Institutional13FChange[];
};

function changeTone(type: string) {
  if (type === "new") return "text-emerald-400";
  if (type === "increased") return "text-teal-400";
  if (type === "exit" || type === "decreased") return "text-red-400";
  return "text-zinc-400";
}

function fmtShares(n: number | null | undefined) {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtMoney(n: number | null | undefined) {
  if (n == null) return null;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function InstitutionalChangeTimeline({ changes }: Props) {
  if (changes.length === 0) {
    return <p className="text-xs text-zinc-500">No filer change details available.</p>;
  }

  return (
    <ul className="space-y-2 text-xs text-zinc-400">
      {changes.map((c, i) => (
        <li
          key={`${c.filer_name}-${c.quarter_end ?? i}`}
          className="border-l-2 border-zinc-700 pl-3"
        >
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            {c.quarter_end && (
              <span className="font-mono text-zinc-500">Q ended {c.quarter_end}</span>
            )}
            <span className="text-zinc-300">{c.filer_name}</span>
            {c.is_notable_filer && (
              <span className="rounded border border-amber-800/60 bg-amber-950/30 px-1 py-0.5 text-[10px] text-amber-400">
                Notable
              </span>
            )}
            <span className={`capitalize ${changeTone(c.change_type ?? "")}`}>
              {c.change_type?.replace("_", " ")}
            </span>
            {c.pct_change != null && (
              <span className="text-zinc-500">
                ({c.pct_change > 0 ? "+" : ""}
                {c.pct_change.toFixed(0)}%)
              </span>
            )}
          </div>
          <div className="mt-0.5 text-zinc-500">
            {fmtShares(c.prior_shares)} → {fmtShares(c.shares)} sh
            {c.value_usd != null && (
              <span className="text-zinc-600"> · {fmtMoney(c.value_usd)}</span>
            )}
            {c.quarter_note && <span className="block text-[10px] text-zinc-600">{c.quarter_note}</span>}
          </div>
        </li>
      ))}
      <li className="text-[10px] text-zinc-600 pt-1">
        13F positions are reported quarterly (up to ~45 days after quarter end).
      </li>
    </ul>
  );
}
