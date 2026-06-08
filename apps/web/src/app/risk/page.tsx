"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { WarningBadge } from "@/components/WarningBadge";
import { evaluateRisk, saveJournal, type RiskEvaluateResponse } from "@/lib/api";

export default function RiskPage() {
  const [result, setResult] = useState<RiskEvaluateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({
    ticker: "AAPL",
    direction: "long",
    quantity: "10",
    entry_price: "150",
    account_size: "10000",
    instrument_type: "stock",
    holding_days: "7",
  });

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSaved(false);
    try {
      const res = await evaluateRisk({
        ticker: form.ticker,
        direction: form.direction,
        quantity: parseFloat(form.quantity),
        entry_price: parseFloat(form.entry_price),
        account_size: parseFloat(form.account_size),
        instrument_type: form.instrument_type,
        holding_days:
          form.instrument_type === "option"
            ? parseInt(form.holding_days, 10)
            : undefined,
      });
      setResult(res);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Risk evaluation failed");
    } finally {
      setLoading(false);
    }
  };

  const saveToJournal = async () => {
    if (!result) return;
    await saveJournal({
      ticker: result.ticker,
      direction: form.direction,
      quantity: parseFloat(form.quantity),
      entry_price: parseFloat(form.entry_price),
      account_size: parseFloat(form.account_size),
      instrument_type: form.instrument_type,
      ai_warnings: [
        ...result.warnings.map((w) => w.message),
        ...(result.derivative_note ? [result.derivative_note] : []),
      ],
    });
    setSaved(true);
  };

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-semibold">Pre-Trade Risk Check</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Reality check before execution — position sizing and stop-loss guidance.
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        {[
          { key: "ticker", label: "Ticker" },
          { key: "quantity", label: "Quantity", type: "number" },
          { key: "entry_price", label: "Entry price", type: "number" },
          { key: "account_size", label: "Account size ($)", type: "number" },
        ].map((f) => (
          <label key={f.key} className="block text-sm">
            {f.label}
            <input
              type={f.type || "text"}
              value={form[f.key as keyof typeof form]}
              onChange={(e) =>
                setForm({ ...form, [f.key]: e.target.value })
              }
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            />
          </label>
        ))}
        <label className="block text-sm">
          Direction
          <select
            value={form.direction}
            onChange={(e) => setForm({ ...form, direction: e.target.value })}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
          >
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </label>
        <label className="block text-sm">
          Instrument
          <select
            value={form.instrument_type}
            onChange={(e) =>
              setForm({ ...form, instrument_type: e.target.value })
            }
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
          >
            <option value="stock">Stock</option>
            <option value="option">Option</option>
            <option value="leveraged_etf">Leveraged ETF</option>
          </select>
        </label>
        {form.instrument_type === "option" && (
          <label className="block text-sm">
            Holding days
            <input
              type="number"
              value={form.holding_days}
              onChange={(e) =>
                setForm({ ...form, holding_days: e.target.value })
              }
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2"
            />
          </label>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-emerald-600 py-2 font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Calculating…" : "Evaluate risk"}
        </button>
      </form>

      {result && (
        <div className="space-y-4 rounded-lg border border-zinc-800 p-5">
          <p className="font-mono text-lg">{result.ticker}</p>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-zinc-500">Position value</dt>
            <dd>${result.position_value.toLocaleString()}</dd>
            <dt className="text-zinc-500">Portfolio %</dt>
            <dd className={result.exceeds_risk_limit ? "text-red-400" : ""}>
              {result.portfolio_pct}% (limit {result.risk_limit_pct}%)
            </dd>
            {result.suggested_position_size != null && (
              <>
                <dt className="text-zinc-500">Suggested size (shares)</dt>
                <dd>{result.suggested_position_size}</dd>
              </>
            )}
            {result.suggested_stop_loss != null && (
              <>
                <dt className="text-zinc-500">Suggested stop</dt>
                <dd>${result.suggested_stop_loss}</dd>
              </>
            )}
            {result.atr != null && (
              <>
                <dt className="text-zinc-500">ATR (14)</dt>
                <dd>{result.atr}</dd>
              </>
            )}
          </dl>
          {result.derivative_note && (
            <p className="text-sm text-amber-300/90 border border-amber-900/50 rounded p-3 bg-amber-950/30">
              {result.derivative_note}
            </p>
          )}
          {result.warnings.map((w) => (
            <WarningBadge key={w.code} warning={w} />
          ))}
          <Link
            href={`/context?ticker=${result.ticker}`}
            className="block text-sm text-emerald-400 hover:underline"
          >
            View fair-value context for {result.ticker}
          </Link>
          <button
            type="button"
            onClick={saveToJournal}
            className="text-sm text-emerald-400 hover:underline"
          >
            Save to journal
          </button>
          {saved && (
            <p className="text-xs text-emerald-500">Saved to trade journal.</p>
          )}
        </div>
      )}
    </div>
  );
}
