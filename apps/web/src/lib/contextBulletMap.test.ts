import assert from "node:assert/strict";
import {
  bulletsToKeyedFallback,
  CANONICAL_SECTION_IDS,
  mapBulletsToSections,
  SECTION_UNAVAILABLE,
} from "./contextBulletMap";
import type { ContextSectionLabel, ContextVisualSection } from "./api";

function section(id: string): ContextVisualSection {
  return {
    id,
    title: id,
    stance: "neutral",
    metrics: [],
    sparkline: [],
  };
}

const allSections = CANONICAL_SECTION_IDS.map((id) => section(id));

function runTests() {
  // 8 legacy bullets without sector — growth must not receive sector text
  const legacy8 = [
    "Valuation text",
    "Macro text",
    "Sector text",
    "Growth text",
    "Balance text",
    "Catalyst text",
    "Insider text",
    "Technical text",
  ];
  const { paired: legacyPaired } = mapBulletsToSections(allSections, legacy8, []);
  assert.equal(legacyPaired.find((p) => p.section.id === "sector")?.bullet, "Sector text");
  assert.equal(legacyPaired.find((p) => p.section.id === "growth")?.bullet, "Growth text");
  assert.equal(
    legacyPaired.find((p) => p.section.id === "forward")?.bullet,
    SECTION_UNAVAILABLE
  );

  // Keyed bullets — correct placement regardless of array order
  const keyed = bulletsToKeyedFallback([]);
  keyed.sector = "Keyed sector";
  keyed.growth = "Keyed growth";
  const labels: ContextSectionLabel[] = CANONICAL_SECTION_IDS.map(() => ({
    stance: "neutral",
    headline: "Ok",
  }));
  const { paired: keyedPaired } = mapBulletsToSections(
    allSections,
    [],
    labels,
    keyed
  );
  assert.equal(keyedPaired.find((p) => p.section.id === "sector")?.bullet, "Keyed sector");
  assert.equal(keyedPaired.find((p) => p.section.id === "growth")?.bullet, "Keyed growth");

  console.log("contextBulletMap tests passed");
}

runTests();
