"use client";

import type { WatchlistInsiderPulse } from "@/lib/api";
import { InsiderAccumulationTable } from "@/components/InsiderAccumulationTable";
import { SmartMoneyPanelMeta } from "@/components/smart-money/SmartMoneyPanelMeta";

type Props = {
  pulse: WatchlistInsiderPulse;
  loading?: boolean;
};

export function WatchlistInsiderPulsePanel({ pulse, loading }: Props) {
  const active = pulse.rows.filter((r) => r.data_available);

  return (
    <div className="space-y-4">
      <SmartMoneyPanelMeta
        loading={loading}
        loadingLabel="Scanning watchlist insider activity…"
        meta={
          !loading
            ? `Watchlist "${pulse.watchlist_name}" · 90-day Form 4 · ${active.length} ticker(s) with data`
            : undefined
        }
        message={!loading ? pulse.message ?? undefined : undefined}
      />

      {!loading && active.length === 0 && !pulse.message && (
        <p className="text-sm text-zinc-500">No insider data for watchlist tickers.</p>
      )}

      {active.length > 0 && <InsiderAccumulationTable rows={active} />}
    </div>
  );
}
