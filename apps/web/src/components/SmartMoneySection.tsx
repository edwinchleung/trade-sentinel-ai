"use client";

import Link from "next/link";
import type { TickerContext } from "@/lib/api";
import { InsiderSignalPanel } from "@/components/InsiderSignalPanel";
import { OptionsFlowChart } from "@/components/OptionsFlowChart";

type Props = {
  ctx: TickerContext;
};

const sentimentStyles = {
  accumulation: "bg-emerald-950/50 text-emerald-400 border-emerald-800",
  distribution: "bg-red-950/50 text-red-400 border-red-800",
  neutral: "bg-zinc-800 text-zinc-400 border-zinc-700",
};

const changeTypeStyles: Record<string, string> = {
  new: "text-emerald-400",
  increased: "text-emerald-300",
  decreased: "text-red-400",
  exit: "text-red-500",
  held: "text-zinc-400",
};

export function SmartMoneySection({ ctx }: Props) {
  const hasInsider = Boolean(ctx.insider || ctx.insider_summary);
  const hasOptions =
    ctx.options_flow &&
    (ctx.options_flow.message ||
      ctx.options_flow.call_volume != null ||
      ctx.options_flow.put_volume != null);
  const has13f = Boolean(
    ctx.institutional_13f?.data_available && ctx.institutional_13f.changes.length > 0
  );
  const hasActivist = Boolean(ctx.activist_filing);
  const assessment = ctx.smart_money_assessment;
  const hasAssessment = Boolean(assessment?.data_available && assessment.layers.length > 0);

  if (!hasInsider && !hasOptions && !has13f && !hasActivist && !hasAssessment) {
    return null;
  }

  const sentiment = ctx.insider_summary?.sentiment;
  const optionsUnusual = ctx.options_flow?.unusual;
  const institutional = ctx.institutional_13f;
  const activist = ctx.activist_filing;

  return (
    <section className="rounded-lg border border-zinc-700/80 bg-zinc-900/50 p-5 space-y-5">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-base font-semibold text-zinc-100">Smart Money</h2>
          {sentiment && (
            <span
              className={`rounded-full border px-2.5 py-0.5 text-xs capitalize ${sentimentStyles[sentiment]}`}
            >
              Insider: {sentiment}
            </span>
          )}
          {ctx.options_flow?.high_conviction && (
            <span className="rounded-full border border-amber-700 bg-amber-950/50 px-2.5 py-0.5 text-xs text-amber-300">
              High-conviction options
            </span>
          )}
          {optionsUnusual && !ctx.options_flow?.high_conviction && (
            <span className="rounded-full border border-amber-800 bg-amber-950/40 px-2.5 py-0.5 text-xs text-amber-400">
              Unusual options
            </span>
          )}
          {institutional?.conviction_buy && (
            <span className="rounded-full border border-emerald-800 bg-emerald-950/40 px-2.5 py-0.5 text-xs text-emerald-400">
              13F conviction
            </span>
          )}
          {hasActivist && (
            <span className="rounded-full border border-amber-700 bg-amber-950/50 px-2.5 py-0.5 text-xs text-amber-300">
              Activist 13D
            </span>
          )}
          {assessment?.conviction_pct != null && (
            <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-300">
              Conviction {assessment.conviction_pct}%
            </span>
          )}
        </div>
        <p className="text-xs text-zinc-500">
          Institutional footprint — Form 4 insiders, 13F holdings, activist stakes, and options flow
          (not investment advice)
        </p>
      </div>

      {hasInsider && (
        <InsiderSignalPanel
          summary={ctx.insider_summary}
          timeline={ctx.insider}
          embedded
        />
      )}

      {has13f && institutional && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-300">Institutional 13F changes</h3>
          <p className="text-xs text-zinc-500">{institutional.disclaimer}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="py-1.5 pr-3 font-medium">Filer</th>
                  <th className="py-1.5 pr-3 font-medium">Change</th>
                  <th className="py-1.5 font-medium">QoQ</th>
                </tr>
              </thead>
              <tbody>
                {institutional.changes.slice(0, 6).map((ch) => (
                  <tr key={`${ch.filer_cik}-${ch.change_type}`} className="border-b border-zinc-800/60">
                    <td className="py-1.5 pr-3 text-zinc-300">{ch.filer_name}</td>
                    <td
                      className={`py-1.5 pr-3 capitalize ${changeTypeStyles[ch.change_type] ?? "text-zinc-400"}`}
                    >
                      {ch.change_type}
                    </td>
                    <td className="py-1.5 text-zinc-400">
                      {ch.pct_change != null ? `${ch.pct_change > 0 ? "+" : ""}${ch.pct_change.toFixed(0)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {hasActivist && activist && (
        <div className="space-y-1">
          <h3 className="text-sm font-medium text-zinc-300">Activist stake</h3>
          <p className="text-xs text-zinc-400">
            {activist.filing_date} — {activist.filer_name ?? "Unknown filer"}
            {activist.percent_owned != null ? ` — ${activist.percent_owned.toFixed(1)}% owned` : ""}
            {activist.signal ? ` · ${activist.signal}` : ""}
          </p>
        </div>
      )}

      {hasOptions && ctx.options_flow && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-zinc-300">Options flow</h3>
          <OptionsFlowChart flow={ctx.options_flow} />
          {ctx.options_flow.max_vol_oi_ratio != null && (
            <p className="text-xs text-zinc-500">
              Max Vol/OI ratio: {ctx.options_flow.max_vol_oi_ratio}
            </p>
          )}
        </div>
      )}

      {hasAssessment && assessment && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-300">{assessment.headline}</h3>
          {assessment.calendar_notes && assessment.calendar_notes.length > 0 && (
            <ul className="text-xs text-amber-600/90 space-y-1">
              {assessment.calendar_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
          <ul className="text-xs text-zinc-500 space-y-1">
            {assessment.layers.map((layer) => (
              <li key={layer.layer}>
                {layer.label}: {layer.score}/{layer.max_score}
                {layer.detail ? ` — ${layer.detail}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="pt-1 border-t border-zinc-800">
        <Link href="/smart-money" className="text-xs text-emerald-400 hover:underline">
          View market-wide smart money activity →
        </Link>
      </div>
    </section>
  );
}
