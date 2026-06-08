"use client";

import type { InsiderTransaction } from "@/lib/api";

type Props = {
  transactions: InsiderTransaction[];
  compact?: boolean;
};

function sideTone(tx: InsiderTransaction): string {
  const type = (tx.transaction_type ?? "").toLowerCase();
  if (type.includes("sale") || type.includes("sell")) return "text-red-400";
  if (type.includes("purchase") || type.includes("buy")) return "text-emerald-400";
  return "text-zinc-400";
}

function fmtShares(n: number | null | undefined) {
  if (n == null) return null;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export function InsiderActivityTimeline({ transactions, compact = false }: Props) {
  if (transactions.length === 0) {
    return <p className="text-xs text-zinc-500">No recent Form 4 transactions.</p>;
  }

  return (
    <ul className={`space-y-2 ${compact ? "text-xs" : "text-sm"} text-zinc-400`}>
      {transactions.map((t, i) => (
        <li key={`${t.filing_date}-${t.insider_name}-${i}`} className="border-l-2 border-zinc-700 pl-3">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="font-mono text-zinc-500">{t.filing_date.slice(0, 10)}</span>
            <span className="text-zinc-300">{t.insider_name}</span>
            {t.title && <span className="text-zinc-600">({t.title})</span>}
          </div>
          <div className={`mt-0.5 ${sideTone(t)}`}>
            {t.transaction_type}
            {t.shares != null && (
              <span className="text-zinc-400">
                {" "}
                · {fmtShares(t.shares)} sh
                {t.price != null ? ` @ $${t.price.toFixed(2)}` : ""}
              </span>
            )}
            {t.filing_url && (
              <>
                {" "}
                <a
                  href={t.filing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-400 hover:underline"
                >
                  Filing
                </a>
              </>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
