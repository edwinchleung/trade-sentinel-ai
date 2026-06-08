"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { DcfSensitivityPanel } from "@/components/DcfSensitivityPanel";
import { ValuationCard } from "@/components/ValuationCard";
import { TechnicalAssessmentCard } from "@/components/TechnicalAssessmentCard";
import { FundamentalAssessmentCard } from "@/components/FundamentalAssessmentCard";
import { RealityCheckCard } from "@/components/RealityCheckCard";
import { PriceChart } from "@/components/PriceChart";
import { WarningBadge } from "@/components/WarningBadge";
import { EarningsCard } from "@/components/EarningsCard";
import { OutlookCard } from "@/components/OutlookCard";
import { SmartMoneySection } from "@/components/SmartMoneySection";
import { FundamentalsCard } from "@/components/FundamentalsCard";
import { ContextVisualPanel } from "@/components/ContextVisualPanel";
import { SectorContextCard } from "@/components/SectorContextCard";
import { MacroContextCard } from "@/components/MacroContextCard";
import { SecFilingsPanel } from "@/components/SecFilingsPanel";
import {
  fetchContext,
  streamContext,
  type TickerContext,
} from "@/lib/api";
import { gapDisplayLabel } from "@/lib/gapLabels";
import { sectionNarrativeEntries } from "@/lib/contextBulletMap";

function sessionBadgeLabel(state?: string | null): string | null {
  if (!state) return null;
  const labels: Record<string, string> = {
    pre: "Pre-market",
    regular: "Regular hours",
    post: "After hours",
    closed: "At close",
  };
  return labels[state.toLowerCase()] ?? state;
}

function fmtCap(n: number) {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

const OPTIONS_WARNING_CODES = new Set(["OPTIONS_UNUSUAL"]);

function splitWarnings(warnings: TickerContext["warnings"]) {
  const technical = warnings.filter((w) => !OPTIONS_WARNING_CODES.has(w.code));
  const options = warnings.filter((w) => OPTIONS_WARNING_CODES.has(w.code));
  return { technical, options };
}

function ContextContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initial = searchParams.get("ticker") || "";
  const autoOff = searchParams.get("auto") === "0";
  const [ticker, setTicker] = useState(initial);
  const autoRan = useRef(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ctx, setCtx] = useState<TickerContext | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [useStream, setUseStream] = useState(false);

  const load = useCallback(
    async (symbol: string, stream: boolean) => {
      const t = symbol.trim().toUpperCase();
      if (!t) return;
      setLoading(true);
      setError(null);
      router.replace(`/context?ticker=${t}`);
      try {
        if (stream) {
          await new Promise<void>((resolve, reject) => {
            const IDLE_MS = 90_000;
            const MAX_MS = 180_000;
            let settled = false;
            let idleTimer: ReturnType<typeof setTimeout>;
            let closeStream: () => void = () => {};

            const finish = (fn: () => void) => {
              if (settled) return;
              settled = true;
              clearTimeout(idleTimer);
              clearTimeout(maxTimer);
              closeStream();
              fn();
            };

            const bumpIdle = () => {
              clearTimeout(idleTimer);
              idleTimer = setTimeout(() => {
                finish(() =>
                  reject(
                    new Error(
                      "Stream timeout — no progress from server (LLM may be slow; try again or disable Stream)"
                    )
                  )
                );
              }, IDLE_MS);
            };

            closeStream = streamContext(
              t,
              (msg) => {
                bumpIdle();
                if (msg.status === "error") {
                  finish(() =>
                    reject(new Error(msg.message ?? "Stream failed"))
                  );
                  return;
                }
                if (msg.status === "complete" && msg.context) {
                  setCtx(msg.context);
                  finish(() => resolve());
                }
              },
              (errMsg) => {
                finish(() => reject(new Error(errMsg)));
              }
            );

            bumpIdle();
            const maxTimer = setTimeout(() => {
              finish(() =>
                reject(
                  new Error(
                    "Stream timeout — request exceeded 3 minutes (try without Stream)"
                  )
                )
              );
            }, MAX_MS);
          });
        } else {
          const data = await fetchContext(t, {
            summarize: true,
            includeInsider: true,
            includeOptions: true,
          });
          setCtx(data);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load context");
      } finally {
        setLoading(false);
      }
    },
    [router]
  );

  useEffect(() => {
    const t = initial.trim().toUpperCase();
    if (!t || autoOff || autoRan.current) return;
    autoRan.current = true;
    load(t, useStream);
  }, [initial, autoOff, load, useStream]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    load(ticker, useStream);
  };

  const fund = ctx?.fundamentals;
  const profileBits = [
    fund?.sector,
    fund?.industry,
    fund?.market_cap != null ? fmtCap(fund.market_cap) : null,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Market Context Engine</h1>
        <p className="text-sm text-zinc-400 mt-1">
          The pause button — understand why a ticker is moving before you trade.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-wrap gap-3 items-end">
        <label className="flex flex-col gap-1 text-sm">
          Ticker
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="NVDA"
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 font-mono uppercase w-32"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => setUseStream(e.target.checked)}
          />
          Stream (SSE)
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {ctx && (
        <div className="space-y-6">
          <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <h2 className="text-xl font-mono">{ctx.ticker}</h2>
                <p className="text-zinc-400 text-sm">
                  {ctx.price != null ? `$${ctx.price.toFixed(2)}` : "Price N/A"}
                  {ctx.change_pct != null && (
                    <span
                      className={
                        ctx.change_pct >= 0 ? " text-emerald-400" : " text-red-400"
                      }
                    >
                      {" "}
                      {ctx.change_pct >= 0 ? "+" : ""}
                      {ctx.change_pct}%
                    </span>
                  )}
                  {sessionBadgeLabel(ctx.market_state) && (
                    <span className="ml-2 text-xs rounded border border-zinc-700 px-1.5 py-0.5 text-zinc-500">
                      {sessionBadgeLabel(ctx.market_state)}
                    </span>
                  )}
                </p>
                {ctx.is_extended_hours &&
                  ctx.regular_market_price != null &&
                  ctx.price != null &&
                  Math.abs(ctx.price - ctx.regular_market_price) > 0.01 && (
                    <p className="text-xs text-zinc-600 mt-1">
                      Regular close ${ctx.regular_market_price.toFixed(2)}
                    </p>
                  )}
                {profileBits.length > 0 && (
                  <p className="text-xs text-zinc-500 mt-1">{profileBits.join(" · ")}</p>
                )}
              </div>
            </div>
          </section>

          {(ctx.fundamental_warnings?.length ?? 0) > 0 && (
            <section className="space-y-2">
              <h3 className="text-sm font-medium text-zinc-300">Fundamental warnings</h3>
              {ctx.fundamental_warnings!.map((w) => (
                <WarningBadge key={w.code + w.message} warning={w} />
              ))}
            </section>
          )}

          {ctx.context_visuals && ctx.summary && (
            <section className="rounded-lg border border-zinc-800 bg-zinc-950/30 p-5">
              <h3 className="text-sm font-medium text-emerald-400 mb-4">At a glance</h3>
              <ContextVisualPanel visuals={ctx.context_visuals} summary={ctx.summary} />
            </section>
          )}

          {ctx.summary && (
            <details className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-5 group">
              <summary className="text-sm font-medium text-emerald-400 cursor-pointer list-none flex items-center justify-between">
                AI narrative
                <span className="text-xs text-zinc-500 group-open:hidden">Expand</span>
              </summary>
              <div className="mt-4 space-y-4">
                {ctx.summary.qualitative_analysis && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-400 mb-2">Qualitative analysis</h4>
                    <p className="text-zinc-200 text-sm leading-relaxed">
                      {ctx.summary.qualitative_analysis}
                    </p>
                  </div>
                )}
                {ctx.summary.fundamental_interpretation && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-400 mb-2">Fundamental read</h4>
                    <p className="text-zinc-200 text-sm leading-relaxed">
                      {ctx.summary.fundamental_interpretation}
                    </p>
                  </div>
                )}
                {ctx.summary.technical_interpretation && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-400 mb-2">Technical read</h4>
                    <p className="text-zinc-200 text-sm leading-relaxed">
                      {ctx.summary.technical_interpretation}
                    </p>
                  </div>
                )}
                {ctx.summary.reality_check_narrative && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-400 mb-2">Reality check</h4>
                    <p className="text-zinc-200 text-sm leading-relaxed">
                      {ctx.summary.reality_check_narrative}
                    </p>
                  </div>
                )}
                {sectionNarrativeEntries(ctx.summary).length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-400 mb-2">Section narratives</h4>
                    <ul className="space-y-3 text-zinc-200 text-sm">
                      {sectionNarrativeEntries(ctx.summary).map((entry) => (
                        <li key={entry.id} className="leading-relaxed">
                          <span className="text-xs font-medium text-zinc-500 block mb-0.5">
                            {entry.title}
                          </span>
                          {entry.text}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {ctx.summary.scenario_bullets && ctx.summary.scenario_bullets.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-zinc-400 mb-2">Scenarios</h4>
                    <ul className="list-disc list-inside space-y-1 text-sm text-zinc-300">
                      {ctx.summary.scenario_bullets.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {ctx.summary.data_gaps && ctx.summary.data_gaps.length > 0 && (
                  <div className="text-xs text-zinc-500">
                    <p className="font-medium text-zinc-400 mb-1">Data limitations</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      {ctx.summary.data_gaps.map((g) => (
                        <li key={g}>{gapDisplayLabel(g)}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </details>
          )}

          {ctx.macro_overlay && <MacroContextCard overlay={ctx.macro_overlay} />}

          {ctx.sector_context && <SectorContextCard sector={ctx.sector_context} />}

          {ctx.valuation && <ValuationCard valuation={ctx.valuation} />}
          {ctx.valuation?.dcf_sensitivity && ctx.valuation.dcf_sensitivity.length > 0 && (
            <DcfSensitivityPanel valuation={ctx.valuation} />
          )}

          {ctx.reality_check && (
            <RealityCheckCard realityCheck={ctx.reality_check} summary={ctx.summary} />
          )}

          {ctx.fundamental_assessment && (
            <FundamentalAssessmentCard assessment={ctx.fundamental_assessment} />
          )}

          {ctx.technical_assessment && (
            <TechnicalAssessmentCard assessment={ctx.technical_assessment} />
          )}

          <details className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 group">
            <summary className="text-sm font-medium text-zinc-300 cursor-pointer list-none flex items-center justify-between">
              Full fundamentals
              <span className="text-xs text-zinc-500 group-open:hidden">Expand</span>
            </summary>
            <div className="mt-4">
              {ctx.fundamentals && <FundamentalsCard fundamentals={ctx.fundamentals} />}
            </div>
          </details>

          {ctx.earnings && <EarningsCard earnings={ctx.earnings} />}

          {ctx.forward_outlook && <OutlookCard outlook={ctx.forward_outlook} />}

          {ctx.sec_filings && <SecFilingsPanel feed={ctx.sec_filings} />}

          {ctx.news.length > 0 && (
            <section>
              <h3 className="text-sm font-medium text-zinc-300 mb-2">Headlines</h3>
              {ctx.news_digest?.summary_line && (
                <p className="text-xs text-zinc-500 mb-2">{ctx.news_digest.summary_line}</p>
              )}
              <ul className="space-y-2 text-sm">
                {ctx.news.map((n, i) => (
                  <li key={i} className="border-l-2 border-zinc-700 pl-3">
                    {n.url ? (
                      <a
                        href={n.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-400 hover:underline"
                      >
                        {n.title}
                      </a>
                    ) : (
                      n.title
                    )}
                    {n.sentiment_label && (
                      <span className="ml-2 text-xs text-zinc-600 capitalize">
                        ({n.sentiment_label})
                      </span>
                    )}
                    {n.summary && (
                      <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{n.summary}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <SmartMoneySection ctx={ctx} />

          <details className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 group">
            <summary className="text-sm font-medium text-zinc-300 cursor-pointer list-none flex items-center justify-between">
              Technical analysis
              <span className="text-xs text-zinc-500 group-open:hidden">Expand</span>
            </summary>
            <div className="mt-4 space-y-4">
              <div className="text-sm text-zinc-400 font-mono space-y-0.5">
                <div>
                  RSI: {ctx.rsi ?? "N/A"} · Vol ratio: {ctx.volume_ratio ?? "N/A"}x
                </div>
                {ctx.macd && (
                  <div>
                    MACD: {ctx.macd.macd?.toFixed(2) ?? "N/A"} · Signal:{" "}
                    {ctx.macd.signal?.toFixed(2) ?? "N/A"} · Hist:{" "}
                    {ctx.macd.histogram?.toFixed(2) ?? "N/A"}
                  </div>
                )}
              </div>
              {(() => {
                const { technical, options } = splitWarnings(ctx.warnings);
                return (
                  <>
                    {technical.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-xs font-medium text-zinc-400">Technical warnings</h4>
                        {technical.map((w) => (
                          <WarningBadge key={w.code + w.message} warning={w} />
                        ))}
                      </div>
                    )}
                    {options.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-xs font-medium text-zinc-400">Options warnings</h4>
                        {options.map((w) => (
                          <WarningBadge key={w.code + w.message} warning={w} />
                        ))}
                      </div>
                    )}
                  </>
                );
              })()}
              {ctx.price_history?.length > 0 && (
                <PriceChart
                  data={ctx.price_history}
                  sma20={ctx.technical_assessment?.sma_20}
                  sma50={ctx.technical_assessment?.sma_50}
                />
              )}
            </div>
          </details>

          <button
            type="button"
            onClick={() => setShowRaw(!showRaw)}
            className="text-xs text-zinc-500 hover:text-zinc-300"
          >
            {showRaw ? "Hide" : "Show"} raw JSON
          </button>
          {showRaw && (
            <pre className="overflow-auto rounded bg-zinc-950 p-4 text-xs text-zinc-400 border border-zinc-800">
              {JSON.stringify(ctx, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function ContextPage() {
  return (
    <Suspense fallback={<p className="text-zinc-400">Loading…</p>}>
      <ContextContent />
    </Suspense>
  );
}
