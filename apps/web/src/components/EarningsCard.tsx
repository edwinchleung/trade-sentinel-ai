"use client";

import type { EarningsSnapshot } from "@/lib/api";

type Props = {
  earnings: EarningsSnapshot;
};

function dash(v: string | number | null | undefined, isPct = false) {
  if (v == null) return "—";
  if (isPct && typeof v === "number") {
    return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
  }
  return String(v);
}

export function EarningsCard({ earnings }: Props) {
  if (!earnings.data_available && earnings.message) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">Earnings</h3>
        <p className="text-sm text-zinc-500">{earnings.message}</p>
      </section>
    );
  }

  const missingNextDate =
    earnings.data_available && !earnings.next_report_date;

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
      <h3 className="text-sm font-medium text-zinc-300 mb-3">Earnings snapshot</h3>
      {missingNextDate && (
        <p className="text-xs text-zinc-500 mb-3">
          Next earnings date unavailable from data provider.
        </p>
      )}
      {earnings.message && (
        <p className="text-xs text-zinc-500 mb-3">{earnings.message}</p>
      )}
      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-zinc-500 text-xs">Next report</dt>
          <dd className="font-mono text-zinc-200">
            {earnings.next_report_date ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Days until</dt>
          <dd className="font-mono text-zinc-200">
            {earnings.days_until != null ? earnings.days_until : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Last EPS (act / est)</dt>
          <dd className="font-mono text-zinc-200">
            {dash(earnings.last_eps_actual)} / {dash(earnings.last_eps_estimate)}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Surprise</dt>
          <dd
            className={`font-mono ${
              earnings.surprise_pct != null && earnings.surprise_pct > 0
                ? "text-emerald-400"
                : earnings.surprise_pct != null && earnings.surprise_pct < 0
                  ? "text-red-400"
                  : "text-zinc-200"
            }`}
          >
            {dash(earnings.surprise_pct, true)}
            {earnings.revenue_beat_miss && (
              <span className="text-zinc-500 text-xs ml-1">
                ({earnings.revenue_beat_miss})
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Last revenue (act / est)</dt>
          <dd className="font-mono text-zinc-200 text-xs">
            {earnings.last_revenue_actual != null
              ? earnings.last_revenue_actual.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })
              : "—"}{" "}
            /{" "}
            {earnings.last_revenue_estimate != null
              ? earnings.last_revenue_estimate.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Revenue surprise</dt>
          <dd
            className={`font-mono ${
              earnings.revenue_surprise_pct != null && earnings.revenue_surprise_pct > 0
                ? "text-emerald-400"
                : earnings.revenue_surprise_pct != null && earnings.revenue_surprise_pct < 0
                  ? "text-red-400"
                  : "text-zinc-200"
            }`}
          >
            {dash(earnings.revenue_surprise_pct, true)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
