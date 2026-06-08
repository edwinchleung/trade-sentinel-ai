"use client";

import { useEffect, useState } from "react";
import { fetchJournal, type TradeJournalEntry } from "@/lib/api";

export default function JournalPage() {
  const [entries, setEntries] = useState<TradeJournalEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetchJournal()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Trade Journal</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Saved trades from risk checks — stored in local PostgreSQL (Docker).
        </p>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {entries.length === 0 && !error && (
        <p className="text-zinc-500 text-sm">
          No entries yet. Run a risk check and click &quot;Save to journal&quot;.
        </p>
      )}

      <ul className="space-y-4">
        {entries.map((e) => (
          <li
            key={e.id}
            className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 text-sm"
          >
            <div className="flex justify-between">
              <span className="font-mono text-emerald-400">{e.ticker}</span>
              <span className="text-zinc-500">
                {e.created_at
                  ? new Date(e.created_at).toLocaleString()
                  : ""}
              </span>
            </div>
            <p className="mt-2 text-zinc-400">
              {e.direction} · {e.quantity} @ ${e.entry_price} · {e.instrument_type}
            </p>
            {e.ai_warnings.length > 0 && (
              <ul className="mt-2 list-disc list-inside text-zinc-500">
                {e.ai_warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
