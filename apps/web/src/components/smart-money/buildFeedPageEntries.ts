import type { SmartMoneyFeedItem } from "@/lib/api";

export type FeedPageEntry =
  | { kind: "header"; date: string }
  | { kind: "row"; item: SmartMoneyFeedItem };

export function buildFeedPageEntries(
  pageRows: SmartMoneyFeedItem[],
  groupByDate: boolean
): FeedPageEntry[] {
  const entries: FeedPageEntry[] = [];
  let lastDate = "";
  for (const item of pageRows) {
    const d = item.filing_date.slice(0, 10);
    if (groupByDate && d !== lastDate) {
      entries.push({ kind: "header", date: d });
      lastDate = d;
    }
    entries.push({ kind: "row", item });
  }
  return entries;
}
