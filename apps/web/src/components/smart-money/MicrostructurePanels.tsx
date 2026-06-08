"use client";

import type { CongressionalFeed, MicrostructureSnapshot } from "@/lib/api";

export function MicrostructurePanel({
  data,
  loading,
}: {
  data: MicrostructureSnapshot | null;
  loading?: boolean;
}) {
  if (loading) return <p className="text-sm text-zinc-500">Loading market structure…</p>;
  if (!data) return <p className="text-sm text-zinc-500">No microstructure data.</p>;

  const gex = data.gex;
  const dix = data.dix;

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        GEX computed from options OI; DIX uses FINRA short-volume proxy unless SqueezeMetrics key is set.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
          <h3 className="text-sm font-medium text-zinc-200">Gamma exposure (GEX)</h3>
          {gex?.data_available ? (
            <>
              <p className="text-2xl font-semibold mt-2">
                {gex.net_gex_usd != null ? gex.net_gex_usd.toLocaleString() : "—"}
              </p>
              <p className="text-sm text-zinc-400 mt-1">
                Regime: {gex.regime ?? "—"} · source: {gex.data_source}
              </p>
            </>
          ) : (
            <p className="text-sm text-zinc-500 mt-2">{gex?.message ?? "Unavailable"}</p>
          )}
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
          <h3 className="text-sm font-medium text-zinc-200">DIX proxy</h3>
          {dix?.data_available ? (
            <>
              <p className="text-2xl font-semibold mt-2">
                {dix.short_volume_ratio != null ? `${dix.short_volume_ratio}%` : "—"}
              </p>
              <p className="text-sm text-zinc-400 mt-1">
                {dix.elevated_dark_accumulation ? "Elevated dark accumulation signal" : "Normal range"} ·{" "}
                {dix.data_source}
              </p>
            </>
          ) : (
            <p className="text-sm text-zinc-500 mt-2">{dix?.message ?? "Unavailable"}</p>
          )}
        </div>
      </div>
      {data.notes?.length ? (
        <ul className="text-xs text-amber-500/90 list-disc pl-4">
          {data.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function CongressionalPanel({
  feed,
  loading,
}: {
  feed: CongressionalFeed | null;
  loading?: boolean;
}) {
  if (loading) return <p className="text-sm text-zinc-500">Loading congressional trades…</p>;
  if (!feed?.data_available) {
    return (
      <p className="text-sm text-zinc-500">
        {feed?.message ?? "Congressional trade feed unavailable. Configure CONGRESSIONAL_TRADES_API_KEY or provider."}
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-zinc-500 border-b border-zinc-800">
            <th className="py-2 pr-3">Politician</th>
            <th className="py-2 pr-3">Ticker</th>
            <th className="py-2 pr-3">Type</th>
            <th className="py-2 pr-3">Tx date</th>
            <th className="py-2">Amount</th>
          </tr>
        </thead>
        <tbody>
          {feed.trades.slice(0, 50).map((t, i) => (
            <tr key={`${t.politician}-${t.ticker}-${i}`} className="border-b border-zinc-900">
              <td className="py-2 pr-3">{t.politician}</td>
              <td className="py-2 pr-3 font-mono">{t.ticker ?? "—"}</td>
              <td className="py-2 pr-3">{t.transaction_type ?? "—"}</td>
              <td className="py-2 pr-3">{t.transaction_date ?? "—"}</td>
              <td className="py-2">{t.amount_range ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-zinc-600 mt-2">Source: {feed.data_source}</p>
    </div>
  );
}
