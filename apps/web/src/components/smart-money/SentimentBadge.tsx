"use client";

const styles = {
  accumulation: "text-emerald-400",
  distribution: "text-red-400",
  neutral: "text-zinc-400",
} as const;

type Sentiment = keyof typeof styles;

export function SentimentBadge({ sentiment }: { sentiment: Sentiment | string }) {
  const key = (sentiment in styles ? sentiment : "neutral") as Sentiment;
  return <span className={`capitalize ${styles[key]}`}>{sentiment}</span>;
}
