"use client";

import type { InsiderSummary, InsiderTimeline } from "@/lib/api";

type Props = {
  summary?: InsiderSummary | null;
  timeline?: InsiderTimeline | null;
  embedded?: boolean;
};

const sentimentStyles = {
  accumulation: "bg-emerald-950/50 text-emerald-400 border-emerald-800",
  distribution: "bg-red-950/50 text-red-400 border-red-800",
  neutral: "bg-zinc-800 text-zinc-400 border-zinc-700",
};

export function InsiderSignalPanel({ summary, timeline, embedded = false }: Props) {
  const heading = embedded ? "Open-market insider activity" : "Open-market insider signal";
  const emptyHeading = embedded ? "Open-market insider activity" : "Insider signal (Form 4)";

  if (!summary?.data_available && !timeline?.transactions.length) {
    return (
      <section>
        <h3 className="text-sm font-medium text-zinc-300 mb-2">{emptyHeading}</h3>
        <p className="text-sm text-zinc-500">
          {timeline?.message ?? "Data Unavailable — no recent Form 4 filings."}
        </p>
      </section>
    );
  }

  const sentiment = summary?.sentiment ?? "neutral";
  const wrapperClass = embedded
    ? "space-y-4"
    : "rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-4";

  return (
    <section className={wrapperClass}>
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-medium text-zinc-300">{heading}</h3>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs capitalize ${sentimentStyles[sentiment]}`}
        >
          {sentiment}
        </span>
        {summary?.cluster_buying && (
          <span className="rounded-full border border-sky-800 bg-sky-950/40 px-2.5 py-0.5 text-xs text-sky-400">
            Cluster buying
          </span>
        )}
      </div>

      {summary && summary.data_available && (
        <dl className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-zinc-500 text-xs">Net 90d shares</dt>
            <dd
              className={`font-mono ${
                summary.net_shares_90d > 0
                  ? "text-emerald-400"
                  : summary.net_shares_90d < 0
                    ? "text-red-400"
                    : "text-zinc-200"
              }`}
            >
              {summary.net_shares_90d > 0 ? "+" : ""}
              {summary.net_shares_90d.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500 text-xs">Open-market buys</dt>
            <dd className="font-mono text-zinc-200">
              {summary.open_market_buy_count ?? summary.buy_count}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500 text-xs">Sells (90d)</dt>
            <dd className="font-mono text-zinc-200">{summary.sell_count}</dd>
          </div>
        </dl>
      )}

      {summary?.analysis_bullets && summary.analysis_bullets.length > 0 && (
        <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
          {summary.analysis_bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}

      {summary?.notable_transactions && summary.notable_transactions.length > 0 && (
        <div>
          <h4 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">
            Notable transactions (&gt;$1M)
          </h4>
          <ul className="text-sm space-y-3 text-zinc-400">
            {summary.notable_transactions.map((t, i) => (
              <li key={i} className="border-l-2 border-zinc-700 pl-3">
                <div>
                  {t.filing_date} — {t.insider_name}: {t.transaction_type}
                  {t.notional != null && (
                    <span className="text-zinc-500">
                      {" "}
                      (${t.notional.toLocaleString()})
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
                {t.excerpt_available && t.excerpt && (
                  <details className="mt-2">
                    <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300">
                      Read excerpt
                    </summary>
                    <p className="mt-2 text-xs text-zinc-400 rounded bg-zinc-950/60 p-3 border border-zinc-800">
                      {t.excerpt}
                    </p>
                  </details>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {timeline && timeline.transactions.length > 0 && (
        <details className="text-sm">
          <summary className="text-zinc-500 cursor-pointer hover:text-zinc-300">
            Recent filings ({timeline.transactions.length})
          </summary>
          <ul className="mt-2 space-y-1 text-zinc-400">
            {timeline.transactions.map((t, i) => (
              <li key={i}>
                {t.filing_date} — {t.insider_name}
                {t.title && <span className="text-zinc-500"> ({t.title})</span>}:{" "}
                {t.transaction_type}
                {t.shares != null && (
                  <span>
                    {" "}
                    ({t.shares.toLocaleString()} sh
                    {t.price != null ? ` @ $${t.price.toFixed(2)}` : ""})
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
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
