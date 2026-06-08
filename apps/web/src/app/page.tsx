"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DigestRowPanel } from "@/components/DigestRowPanel";
import { fetchDigestToday, type DigestToday } from "@/lib/api";

export default function Home() {
  const [digest, setDigest] = useState<DigestToday | null>(null);

  useEffect(() => {
    fetchDigestToday().then(setDigest).catch(() => setDigest(null));
  }, []);

  const highlights = digest?.tickers?.slice(0, 3) ?? [];

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight">
          Institutional-grade clarity for the retail investor
        </h1>
        <p className="max-w-2xl text-zinc-400">
          TradeSentinel AI is your rationality co-pilot — not an execution bot.
          Pause before you trade. Understand context, macro signals, institutional
          footprints, and risk before capital is deployed.
        </p>
      </header>

      {highlights.length > 0 && (
        <section className="rounded-lg border border-emerald-900/40 bg-emerald-950/10 p-4 space-y-2">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <h2 className="text-sm font-medium text-emerald-400">Today — watchlist</h2>
            <div className="flex gap-3 text-xs">
              <Link href="/smart-money" className="text-emerald-400 hover:underline">
                Smart Money feed
              </Link>
              <Link href="/digest" className="text-emerald-400 hover:underline">
                Full digest
              </Link>
            </div>
          </div>
          <ul className="space-y-2">
            {highlights.map((row) => (
              <li key={row.ticker}>
                <DigestRowPanel row={row} compact />
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {[
          {
            href: "/context",
            title: "Market Context Engine",
            desc: "Fair-value band, fundamentals, news, AI summary",
          },
          {
            href: "/smart-money",
            title: "Smart Money",
            desc: "Market-wide insider feed and options activity scan",
          },
          {
            href: "/digest",
            title: "Watchlist digest",
            desc: "Auto snapshot of every saved ticker",
          },
          {
            href: "/screener",
            title: "Watchlist screener",
            desc: "Filter by MOS, earnings, insider, warnings",
          },
          {
            href: "/risk",
            title: "Pre-Trade Risk Check",
            desc: "Position sizing, ATR stop-loss, derivative warnings",
          },
          {
            href: "/briefing",
            title: "Macro Briefing",
            desc: "Daily market weather and sector impact",
          },
          {
            href: "/journal",
            title: "Trade Journal",
            desc: "Log trades with AI risk warnings for review",
          },
          {
            href: "/watchlist",
            title: "Watchlist",
            desc: "Saved tickers for digest and screener",
          },
        ].map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 hover:border-emerald-800 transition-colors"
          >
            <h2 className="font-medium text-emerald-400">{card.title}</h2>
            <p className="mt-2 text-sm text-zinc-400">{card.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
