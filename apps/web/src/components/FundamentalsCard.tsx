"use client";

import type { FundamentalsSnapshot } from "@/lib/api";
import { BenchmarkQuantileBar } from "@/components/BenchmarkQuantileBar";

type Props = {
  fundamentals: FundamentalsSnapshot;
};

function moneySymbol(ccy: string | null | undefined): string {
  const c = (ccy || "USD").toUpperCase();
  if (c === "USD") return "$";
  if (c === "EUR") return "€";
  if (c === "GBP") return "£";
  if (c === "JPY") return "¥";
  return `${c} `;
}

function fmtNum(
  n: number | null | undefined,
  opts?: { pct?: boolean; compact?: boolean; currency?: string | null }
) {
  if (n == null) return "N/A";
  if (opts?.pct) return `${(n * 100).toFixed(1)}%`;
  const sym = moneySymbol(opts?.currency);
  if (opts?.compact && Math.abs(n) >= 1e9) {
    return `${sym}${(n / 1e9).toFixed(2)}B`;
  }
  if (opts?.compact && Math.abs(n) >= 1e6) {
    return `${sym}${(n / 1e6).toFixed(1)}M`;
  }
  return `${sym}${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

const flagStyles: Record<string, string> = {
  HIGH_DEBT: "bg-red-950/50 text-red-400 border-red-800",
  NEGATIVE_MARGIN: "bg-red-950/50 text-red-400 border-red-800",
  REVENUE_DECLINE: "bg-amber-950/50 text-amber-400 border-amber-800",
  NEAR_52W_HIGH: "bg-emerald-950/50 text-emerald-400 border-emerald-800",
  VALUATION_ABOVE_HISTORY: "bg-amber-950/50 text-amber-400 border-amber-800",
  VALUATION_BELOW_HISTORY: "bg-emerald-950/50 text-emerald-400 border-emerald-800",
  MARGIN_EXPANDING: "bg-emerald-950/50 text-emerald-400 border-emerald-800",
  MARGIN_CONTRACTING: "bg-red-950/50 text-red-400 border-red-800",
  GROWTH_DECELERATING: "bg-amber-950/50 text-amber-400 border-amber-800",
  currency_converted: "bg-sky-950/50 text-sky-400 border-sky-800",
  currency_mismatch_unresolved: "bg-amber-950/50 text-amber-400 border-amber-800",
};

export function FundamentalsCard({ fundamentals }: Props) {
  if (!fundamentals.data_available && fundamentals.message) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">Fundamentals</h3>
        <p className="text-sm text-zinc-500">{fundamentals.message}</p>
      </section>
    );
  }

  const bench = fundamentals.benchmark;
  const statementCurrency =
    fundamentals.amounts_currency ??
    (fundamentals.monetary_values_normalized ? "USD" : fundamentals.trading_currency);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-300">Fundamentals</h3>
        {fundamentals.valuation_label && (
          <span className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-xs capitalize text-zinc-400">
            {fundamentals.valuation_label} valuation
          </span>
        )}
      </div>

      <p className="text-xs text-zinc-500">
        {[fundamentals.sector, fundamentals.industry].filter(Boolean).join(" · ") ||
          "Sector N/A"}
        {fundamentals.market_cap != null && (
          <>
            {" "}
            · Mkt cap{" "}
            {fmtNum(fundamentals.market_cap, {
              compact: true,
              currency: fundamentals.trading_currency,
            })}
          </>
        )}
        {fundamentals.trading_currency && (
          <> · Quote {fundamentals.trading_currency}</>
        )}
        {fundamentals.financial_currency &&
          fundamentals.financial_currency !== fundamentals.trading_currency && (
            <> · Financials {fundamentals.financial_currency}</>
          )}
      </p>
      {fundamentals.monetary_values_normalized &&
        fundamentals.fx_rate_financial_to_trading != null &&
        fundamentals.financial_currency && (
          <p className="text-xs text-sky-400/90">
            Statement amounts in USD ({fundamentals.financial_currency}→USD @{" "}
            {fundamentals.fx_rate_financial_to_trading.toFixed(4)}). Quarterly EPS is USD per
            local share; P/E uses quote trailing/forward when listed in a different currency.
          </p>
        )}

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-zinc-500 text-xs">P/E (trail / fwd)</dt>
          <dd className="font-mono text-zinc-200">
            {fundamentals.pe_trailing?.toFixed(1) ?? "—"} /{" "}
            {fundamentals.pe_forward?.toFixed(1) ?? "—"}
          </dd>
          {fundamentals.trailing_eps_quote != null &&
            fundamentals.financial_currency !== fundamentals.trading_currency && (
              <dd className="text-[10px] text-zinc-500 mt-0.5">
                Quote EPS (TTM):{" "}
                {fmtNum(fundamentals.trailing_eps_quote, {
                  currency: fundamentals.trading_currency,
                })}
              </dd>
            )}
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">P/S · P/B</dt>
          <dd className="font-mono text-zinc-200">
            {fundamentals.price_to_sales?.toFixed(1) ?? "—"} ·{" "}
            {fundamentals.price_to_book?.toFixed(1) ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">52W range</dt>
          <dd className="font-mono text-zinc-200 text-xs">
            {fundamentals.fifty_two_week_low?.toFixed(0) ?? "—"} –{" "}
            {fundamentals.fifty_two_week_high?.toFixed(0) ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Analyst target</dt>
          <dd className="font-mono text-zinc-200">
            {fundamentals.target_price?.toFixed(2) ?? "N/A"}
            {fundamentals.target_upside_pct != null && (
              <span
                className={
                  fundamentals.target_upside_pct >= 0
                    ? " text-emerald-400"
                    : " text-red-400"
                }
              >
                {" "}
                ({fundamentals.target_upside_pct > 0 ? "+" : ""}
                {fundamentals.target_upside_pct.toFixed(1)}%)
              </span>
            )}
          </dd>
        </div>
      </dl>

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-zinc-500 text-xs">Rev growth</dt>
          <dd className="font-mono text-zinc-200">
            {fmtNum(fundamentals.revenue_growth, { pct: true })}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Earnings growth</dt>
          <dd className="font-mono text-zinc-200">
            {fmtNum(fundamentals.earnings_growth, { pct: true })}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Profit / op margin</dt>
          <dd className="font-mono text-zinc-200">
            {fmtNum(fundamentals.profit_margin, { pct: true })} /{" "}
            {fmtNum(fundamentals.operating_margin, { pct: true })}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">ROE</dt>
          <dd className="font-mono text-zinc-200">
            {fmtNum(fundamentals.roe, { pct: true })}
          </dd>
        </div>
      </dl>

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-zinc-500 text-xs">D/E</dt>
          <dd className="font-mono text-zinc-200">
            {fundamentals.debt_to_equity?.toFixed(0) ?? "N/A"}%
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Current ratio</dt>
          <dd className="font-mono text-zinc-200">
            {fundamentals.current_ratio?.toFixed(2) ?? "N/A"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">Cash / debt</dt>
          <dd className="font-mono text-zinc-200 text-xs">
            {fmtNum(fundamentals.total_cash, {
              compact: true,
              currency: statementCurrency,
            })}{" "}
            /{" "}
            {fmtNum(fundamentals.total_debt, { compact: true, currency: statementCurrency })}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 text-xs">FCF (latest Q)</dt>
          <dd className="font-mono text-zinc-200">
            {fmtNum(fundamentals.free_cash_flow, {
              compact: true,
              currency: statementCurrency,
            })}
          </dd>
        </div>
      </dl>

      {fundamentals.quarterly_trends.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Quarterly trends</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-zinc-500 text-left">
                  <th className="pb-1 pr-3">Period</th>
                  <th className="pb-1 pr-3">Revenue</th>
                  <th className="pb-1 pr-3">EPS</th>
                  <th className="pb-1">YoY %</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {fundamentals.quarterly_trends.map((q) => (
                  <tr key={q.period} className="border-t border-zinc-800/60">
                    <td className="py-1 pr-3">{q.period}</td>
                    <td className="py-1 pr-3">
                      {q.revenue != null
                        ? fmtNum(q.revenue, { compact: true, currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.eps != null
                        ? fmtNum(q.eps, { currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1">
                      {q.revenue_yoy_pct != null ? (
                        <span
                          className={
                            q.revenue_yoy_pct >= 0 ? "text-emerald-400" : "text-red-400"
                          }
                        >
                          {q.revenue_yoy_pct > 0 ? "+" : ""}
                          {q.revenue_yoy_pct.toFixed(1)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(fundamentals.income_statement_trends?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Income statement (quarterly)</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-zinc-500 text-left">
                  <th className="pb-1 pr-3">Period</th>
                  <th className="pb-1 pr-3">Revenue</th>
                  <th className="pb-1 pr-3">Op income</th>
                  <th className="pb-1 pr-3">Net income</th>
                  <th className="pb-1">Op margin</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {fundamentals.income_statement_trends!.map((q) => (
                  <tr key={q.period} className="border-t border-zinc-800/60">
                    <td className="py-1 pr-3">{q.period}</td>
                    <td className="py-1 pr-3">
                      {q.revenue != null
                        ? fmtNum(q.revenue, { compact: true, currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.operating_income != null
                        ? fmtNum(q.operating_income, {
                            compact: true,
                            currency: statementCurrency,
                          })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.net_income != null
                        ? fmtNum(q.net_income, { compact: true, currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1">
                      {q.operating_margin_pct != null
                        ? `${q.operating_margin_pct.toFixed(1)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(fundamentals.cash_flow_trends?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Cash flow (quarterly)</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-zinc-500 text-left">
                  <th className="pb-1 pr-3">Period</th>
                  <th className="pb-1 pr-3">OCF</th>
                  <th className="pb-1 pr-3">CapEx</th>
                  <th className="pb-1 pr-3">FCF</th>
                  <th className="pb-1">FCF margin</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {fundamentals.cash_flow_trends!.map((q) => (
                  <tr key={q.period} className="border-t border-zinc-800/60">
                    <td className="py-1 pr-3">{q.period}</td>
                    <td className="py-1 pr-3">
                      {q.operating_cash_flow != null
                        ? fmtNum(q.operating_cash_flow, {
                            compact: true,
                            currency: statementCurrency,
                          })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.capital_expenditure != null
                        ? fmtNum(Math.abs(q.capital_expenditure), {
                            compact: true,
                            currency: statementCurrency,
                          })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.free_cash_flow != null
                        ? fmtNum(q.free_cash_flow, {
                            compact: true,
                            currency: statementCurrency,
                          })
                        : "—"}
                    </td>
                    <td className="py-1">
                      {q.fcf_margin_pct != null ? `${q.fcf_margin_pct.toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(fundamentals.balance_sheet_trends?.length ?? 0) > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Balance sheet (quarterly)</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-zinc-500 text-left">
                  <th className="pb-1 pr-3">Period</th>
                  <th className="pb-1 pr-3">Debt</th>
                  <th className="pb-1 pr-3">Cash</th>
                  <th className="pb-1 pr-3">Net debt</th>
                  <th className="pb-1">D/E</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {fundamentals.balance_sheet_trends!.map((q) => (
                  <tr key={q.period} className="border-t border-zinc-800/60">
                    <td className="py-1 pr-3">{q.period}</td>
                    <td className="py-1 pr-3">
                      {q.total_debt != null
                        ? fmtNum(q.total_debt, { compact: true, currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.cash != null
                        ? fmtNum(q.cash, { compact: true, currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1 pr-3">
                      {q.net_debt != null
                        ? fmtNum(q.net_debt, { compact: true, currency: statementCurrency })
                        : "—"}
                    </td>
                    <td className="py-1">
                      {q.debt_to_equity != null ? `${q.debt_to_equity.toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {bench?.data_available && (
        <div className="rounded border border-zinc-800 bg-zinc-950/40 p-4 space-y-3">
          <h4 className="text-xs font-medium text-zinc-400">Vs own history</h4>
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <dt className="text-zinc-500 text-xs">3Y revenue CAGR</dt>
              <dd className="font-mono text-zinc-200">
                {bench.revenue_cagr_3y != null ? `${bench.revenue_cagr_3y.toFixed(1)}%` : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">Margin vs 3Y avg</dt>
              <dd className="font-mono text-zinc-200">
                {bench.margin_vs_3y_avg_pct != null
                  ? `${bench.margin_vs_3y_avg_pct > 0 ? "+" : ""}${bench.margin_vs_3y_avg_pct.toFixed(1)} pp`
                  : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">P/E vs 3Y TTM median</dt>
              <dd className="font-mono text-zinc-200">
                {bench.pe_vs_3y_median_pct != null
                  ? `${bench.pe_vs_3y_median_pct > 0 ? "+" : ""}${bench.pe_vs_3y_median_pct.toFixed(0)}%`
                  : "N/A"}
                {bench.median_pe_3y != null && (
                  <span className="text-zinc-500 text-xs ml-1">
                    (median {bench.median_pe_3y.toFixed(1)}×)
                  </span>
                )}
              </dd>
              {bench.historical_pe_reliable === false && (
                <p className="text-xs text-amber-400/80 mt-0.5">
                  Historical P/E fair value excluded from headline band.
                </p>
              )}
              {bench.pe_vs_3y_median_pct == null && bench.message && (
                <p className="text-xs text-zinc-500 mt-1">{bench.message}</p>
              )}
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">EPS trend</dt>
              <dd className="font-mono text-zinc-200 capitalize">
                {bench.eps_trend ?? "N/A"}
                {bench.debt_trend && (
                  <span className="text-zinc-500 text-xs ml-1">· D/E {bench.debt_trend}</span>
                )}
              </dd>
            </div>
          </dl>
          {bench.pe_percentiles && (
            <BenchmarkQuantileBar
              label="P/E vs own 3Y TTM range"
              percentiles={bench.pe_percentiles}
              currentPercentile={bench.pe_current_percentile}
              valueSuffix="×"
            />
          )}
          {bench.margin_percentiles && (
            <BenchmarkQuantileBar
              label="Operating margin vs history"
              percentiles={bench.margin_percentiles}
              currentPercentile={bench.margin_current_percentile}
              valueSuffix="%"
            />
          )}
          {bench.benchmark_bullets.length > 0 && (
            <ul className="text-xs text-zinc-400 space-y-1 list-disc list-inside">
              {bench.benchmark_bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {fundamentals.fundamental_flags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {fundamentals.fundamental_flags.map((f) => (
            <span
              key={f}
              className={`rounded-full border px-2 py-0.5 text-xs ${flagStyles[f] ?? "bg-zinc-800 text-zinc-400 border-zinc-700"}`}
            >
              {f.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
