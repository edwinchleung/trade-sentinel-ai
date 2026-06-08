import { describe, expect, it } from "vitest";
import type { SmartMoneyFeedItem } from "@/lib/api";
import { applyClientFilters, detectClusterBuying, normalizeFeedItem } from "./insiderFeedFilters";

function item(partial: Partial<SmartMoneyFeedItem> & { filing_date: string }): SmartMoneyFeedItem {
  return {
    side: "other",
    is_notable: false,
    excerpt_available: false,
    ...partial,
  };
}

describe("normalizeFeedItem", () => {
  it("derives open market and buy side from P code", () => {
    const normalized = normalizeFeedItem(
      item({ filing_date: "2026-06-05", transaction_code: "P", side: "other" })
    );
    expect(normalized.is_open_market).toBe(true);
    expect(normalized.side).toBe("buy");
  });

  it("derives grant as other and not open market from A code", () => {
    const normalized = normalizeFeedItem(
      item({ filing_date: "2026-06-05", transaction_code: "A" })
    );
    expect(normalized.is_open_market).toBe(false);
    expect(normalized.side).toBe("other");
  });

  it("marks notable from notional", () => {
    const normalized = normalizeFeedItem(
      item({ filing_date: "2026-06-05", transaction_code: "P", notional: 2_000_000 })
    );
    expect(normalized.is_notable).toBe(true);
  });
});

describe("applyClientFilters", () => {
  const rows = [
    item({ filing_date: "2026-06-05", transaction_code: "P", side: "buy", is_open_market: true }),
    item({ filing_date: "2026-06-05", transaction_code: "S", side: "sell", is_open_market: true }),
    item({ filing_date: "2026-06-05", transaction_code: "A", side: "other", is_open_market: false }),
    item({
      filing_date: "2026-06-05",
      transaction_code: "P",
      side: "buy",
      is_open_market: true,
      is_notable: true,
      notional: 1_500_000,
    }),
  ];

  it("open market only excludes grants", () => {
    const filtered = applyClientFilters(rows, "all", true);
    expect(filtered).toHaveLength(3);
    expect(filtered.every((r) => r.is_open_market)).toBe(true);
  });

  it("include grants adds non-open-market rows", () => {
    const filtered = applyClientFilters(rows, "all", false);
    expect(filtered).toHaveLength(4);
  });

  it("buy filter keeps only buys", () => {
    const filtered = applyClientFilters(rows, "buy", true);
    expect(filtered).toHaveLength(2);
    expect(filtered.every((r) => r.side === "buy")).toBe(true);
  });

  it("sell filter keeps only sells", () => {
    const filtered = applyClientFilters(rows, "sell", true);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].side).toBe("sell");
  });

  it("notable filter keeps only notable rows", () => {
    const filtered = applyClientFilters(rows, "notable", true);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].is_notable).toBe(true);
  });

  it("cluster filter finds tickers with multiple open-market buyers", () => {
    const today = new Date().toISOString().slice(0, 10);
    const clusterRows = [
      item({
        filing_date: today,
        ticker: "AAPL",
        transaction_code: "P",
        side: "buy",
        is_open_market: true,
        insider_name: "Alice",
      }),
      item({
        filing_date: today,
        ticker: "AAPL",
        transaction_code: "P",
        side: "buy",
        is_open_market: true,
        insider_name: "Bob",
      }),
      item({
        filing_date: today,
        ticker: "MSFT",
        transaction_code: "P",
        side: "buy",
        is_open_market: true,
        insider_name: "Carol",
      }),
    ];
    const flagged = detectClusterBuying(clusterRows);
    expect(flagged.filter((r) => r.cluster_buying)).toHaveLength(2);
    const filtered = applyClientFilters(clusterRows, "cluster", true);
    expect(filtered).toHaveLength(2);
    expect(filtered.every((r) => r.ticker === "AAPL")).toBe(true);
  });
});
