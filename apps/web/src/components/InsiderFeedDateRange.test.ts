import { describe, expect, it } from "vitest";
import { localCalendarIso, rangeFromPreset } from "@/components/InsiderFeedDateRange";

describe("localCalendarIso", () => {
  it("formats using local calendar date parts", () => {
    const d = new Date(2026, 0, 15, 12, 0, 0);
    expect(localCalendarIso(d)).toBe("2026-01-15");
  });
});

describe("rangeFromPreset", () => {
  it("7d window includes today as end date", () => {
    const today = localCalendarIso(new Date());
    const { start, end } = rangeFromPreset("7d");
    expect(end).toBe(today);
    const startDate = new Date(`${start}T12:00:00`);
    const endDate = new Date(`${end}T12:00:00`);
    const diffDays = Math.round((endDate.getTime() - startDate.getTime()) / 86400000);
    expect(diffDays).toBe(6);
  });

  it("today preset uses same start and end", () => {
    const today = localCalendarIso(new Date());
    const { start, end } = rangeFromPreset("today");
    expect(start).toBe(today);
    expect(end).toBe(today);
  });
});
