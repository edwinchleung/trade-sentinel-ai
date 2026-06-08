"use client";

import type { SectorContext } from "@/lib/api";

export function SectorContextCard({ sector }: { sector: SectorContext }) {
  if (!sector.data_available && !sector.sector) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300">Sector context</h3>
        <p className="mt-2 text-sm text-zinc-500">
          {sector.message ?? "Sector peer comparison unavailable."}
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-emerald-400">Sector context</h3>
        {sector.universe && (
          <span className="text-[10px] uppercase text-zinc-600 border border-zinc-800 px-1.5 py-0.5 rounded">
            {sector.universe} preset peers
          </span>
        )}
      </div>
      <p className="text-xs text-zinc-500">
        {[sector.sector, sector.industry].filter(Boolean).join(" · ")}
        {sector.peer_count > 0 && ` · ${sector.peer_count} cached peers`}
      </p>
      {sector.sector_headline && (
        <p className="text-sm text-zinc-200">{sector.sector_headline}</p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
        {sector.pe_forward_sector_percentile != null && (
          <div>
            <p className="text-zinc-500 text-xs">Forward P/E vs sector</p>
            <p className="font-mono">{sector.pe_forward_sector_percentile.toFixed(0)}th pctile</p>
          </div>
        )}
        {sector.mos_sector_percentile != null && (
          <div>
            <p className="text-zinc-500 text-xs">Premium vs fair vs sector</p>
            <p className="font-mono">{sector.mos_sector_percentile.toFixed(0)}th pctile</p>
          </div>
        )}
        {sector.pe_vs_sector_prior_pct != null && sector.sector_pe_prior != null && (
          <div>
            <p className="text-zinc-500 text-xs">vs sector prior P/E ({sector.sector_pe_prior})</p>
            <p
              className={
                sector.pe_vs_sector_prior_pct > 0 ? "font-mono text-amber-400" : "font-mono text-emerald-400"
              }
            >
              {sector.pe_vs_sector_prior_pct >= 0 ? "+" : ""}
              {sector.pe_vs_sector_prior_pct.toFixed(1)}%
            </p>
          </div>
        )}
      </div>
      {sector.sector_bullets.length > 0 && (
        <ul className="text-sm text-zinc-300 list-disc list-inside space-y-1">
          {sector.sector_bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      {sector.message && (
        <p className="text-xs text-zinc-600">{sector.message}</p>
      )}
    </section>
  );
}
