"use client";

import type { ForwardOutlook } from "@/lib/api";

type Props = {
  outlook: ForwardOutlook;
};

export function OutlookCard({ outlook }: Props) {
  if (!outlook.data_available) {
    return null;
  }

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
      <h3 className="text-sm font-medium text-zinc-300">Outlook & watchlist</h3>

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-zinc-500 text-xs">Next earnings</dt>
          <dd className="font-mono text-zinc-200">
            {outlook.next_earnings_date ?? "—"}
            {outlook.days_until_earnings != null && (
              <span className="text-zinc-500 text-xs ml-1">
                ({outlook.days_until_earnings}d)
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Analyst target</dt>
          <dd className="font-mono text-zinc-200">
            {outlook.analyst_target?.toFixed(2) ?? "—"}
            {outlook.target_upside_pct != null && (
              <span
                className={
                  outlook.target_upside_pct >= 0 ? " text-emerald-400" : " text-red-400"
                }
              >
                {" "}
                ({outlook.target_upside_pct > 0 ? "+" : ""}
                {outlook.target_upside_pct.toFixed(1)}%)
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Recommendation</dt>
          <dd className="font-mono text-zinc-200 capitalize">
            {outlook.recommendation ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Rev / earn growth</dt>
          <dd className="font-mono text-zinc-200 text-xs">
            {outlook.revenue_growth != null
              ? `${(outlook.revenue_growth * 100).toFixed(1)}%`
              : "—"}{" "}
            /{" "}
            {outlook.earnings_growth != null
              ? `${(outlook.earnings_growth * 100).toFixed(1)}%`
              : "—"}
          </dd>
        </div>
      </dl>

      {outlook.outlook_bullets.length > 0 && (
        <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
          {outlook.outlook_bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}

      {outlook.watch_items.length > 0 && (
        <div>
          <h4 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">
            What to watch
          </h4>
          <ul className="text-sm space-y-1 text-zinc-400 list-disc list-inside">
            {outlook.watch_items.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
