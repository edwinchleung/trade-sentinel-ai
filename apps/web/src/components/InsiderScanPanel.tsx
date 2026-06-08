"use client";

import type { InsiderScanResult } from "@/lib/api";
import { InsiderAccumulationTable } from "@/components/InsiderAccumulationTable";
import { SmartMoneyPanelMeta } from "@/components/smart-money/SmartMoneyPanelMeta";

type Props = {
  scan: InsiderScanResult | null;
  loading?: boolean;
};

export function InsiderScanPanel({ scan, loading }: Props) {
  return (
    <div className="space-y-4">
      <SmartMoneyPanelMeta
        disclaimer="S&P 500 tickers with insider accumulation or cluster buying from per-ticker Form 4 submissions (90-day window)."
        loading={loading}
        loadingLabel="Loading insider scan…"
        meta={
          scan
            ? `Scanned ${scan.scanned_count} ticker(s)${
                scan.fetched_count != null ? ` · ${scan.fetched_count} with Form 4 data` : ""
              }${scan.rows.length > 0 ? ` · ${scan.rows.length} signal(s)` : ""}${
                scan.partial ? " · scan in progress" : ""
              } · Last scan ${new Date(scan.as_of).toLocaleString()}`
            : undefined
        }
        degradedMessage={
          !loading && scan?.provider_degraded
            ? `SEC Form 4 data unavailable — scanned ${scan.scanned_count} tickers but fetched 0. Retry shortly or wait for the next background scan.`
            : undefined
        }
        message={!loading ? scan?.message ?? undefined : undefined}
      />

      {scan && scan.rows.length > 0 && <InsiderAccumulationTable rows={scan.rows} />}
    </div>
  );
}
