"use client";

import type { SecFilingsFeed } from "@/lib/api";

type Props = {
  feed: SecFilingsFeed;
};

export function SecFilingsPanel({ feed }: Props) {
  if (!feed.data_available) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">SEC filings</h3>
        <p className="text-sm text-zinc-500">{feed.message ?? "Data Unavailable"}</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
      <h3 className="text-sm font-medium text-zinc-300 mb-3">Recent SEC filings</h3>
      <ul className="space-y-3 text-sm">
        {feed.filings.map((f, i) => (
          <li key={`${f.form}-${f.filing_date}-${i}`} className="border-l-2 border-zinc-700 pl-3">
            <div>
              <span className="font-mono text-xs text-zinc-500 mr-2">{f.form}</span>
              <span className="text-zinc-500 text-xs mr-2">{f.filing_date}</span>
              {f.url ? (
                <a
                  href={f.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-400 hover:underline"
                >
                  {f.title ?? f.form}
                </a>
              ) : (
                <span className="text-zinc-300">{f.title ?? f.form}</span>
              )}
            </div>
            {f.excerpt_available && f.excerpt && (
              <details className="mt-2">
                <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300">
                  Read excerpt
                  {f.excerpt_chars != null && (
                    <span className="ml-1 text-zinc-600">({f.excerpt_chars} chars)</span>
                  )}
                </summary>
                <pre className="mt-2 max-h-48 overflow-y-auto text-xs text-zinc-400 whitespace-pre-wrap font-sans rounded bg-zinc-950/60 p-3 border border-zinc-800">
                  {f.excerpt}
                </pre>
              </details>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
