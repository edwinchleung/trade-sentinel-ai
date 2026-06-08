import { describe, expect, it } from "vitest";
import type { SmartMoneyFeedItem } from "@/lib/api";
import { buildFeedPageEntries } from "./buildFeedPageEntries";

function item(ticker: string, date: string): SmartMoneyFeedItem {
  return {
    ticker,
    filing_date: date,
    side: "buy",
    is_notable: false,
    excerpt_available: false,
  };
}

describe("buildFeedPageEntries", () => {
  it("inserts date headers when grouping by date", () => {
    const entries = buildFeedPageEntries(
      [item("AAPL", "2026-06-01"), item("MSFT", "2026-06-01"), item("GOOG", "2026-05-31")],
      true
    );
    expect(entries.filter((e) => e.kind === "header")).toHaveLength(2);
    expect(entries.filter((e) => e.kind === "row")).toHaveLength(3);
  });

  it("skips headers for single-day ranges", () => {
    const entries = buildFeedPageEntries(
      [item("AAPL", "2026-06-01"), item("MSFT", "2026-06-01")],
      false
    );
    expect(entries.every((e) => e.kind === "row")).toBe(true);
  });
});
