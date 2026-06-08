import type { ContextSectionLabel, ContextVisualSection } from "@/lib/api";

/** Canonical section ids — matches backend SECTION_ORDER and context_visuals sections. */
export const CANONICAL_SECTION_IDS = [
  "valuation",
  "macro",
  "sector",
  "growth",
  "balance_sheet",
  "catalysts",
  "insider_options",
  "technical",
  "forward",
] as const;

export type CanonicalSectionId = (typeof CANONICAL_SECTION_IDS)[number];

export const SECTION_UNAVAILABLE = "Data unavailable for this section.";

export const SECTION_TITLES: Record<CanonicalSectionId, string> = {
  valuation: "Valuation",
  macro: "Macro",
  sector: "Sector",
  growth: "Growth & profitability",
  balance_sheet: "Balance sheet & cash flow",
  catalysts: "Catalysts",
  insider_options: "Insider / options",
  technical: "Technical",
  forward: "Forward outlook",
};

export function sectionNarrativeEntries(
  summary: {
    bullets: string[];
    section_bullets?: Record<string, string> | null;
  }
): { id: string; title: string; text: string }[] {
  if (summary.section_bullets && Object.keys(summary.section_bullets).length > 0) {
    return CANONICAL_SECTION_IDS.map((id) => ({
      id,
      title: SECTION_TITLES[id],
      text: summary.section_bullets![id] ?? SECTION_UNAVAILABLE,
    })).filter((e) => e.text && e.text !== SECTION_UNAVAILABLE);
  }
  return summary.bullets.map((text, i) => ({
    id: String(i),
    title: `Section ${i + 1}`,
    text,
  }));
}

/** @deprecated Use CANONICAL_SECTION_IDS — kept for imports that referenced V8 order. */
export const BULLET_SECTION_ORDER_V8 = CANONICAL_SECTION_IDS;

/** @deprecated Legacy V7 omitted sector — do not use for mapping. */
export const BULLET_SECTION_ORDER_V7 = [
  "valuation",
  "macro",
  "growth",
  "balance_sheet",
  "catalysts",
  "insider_options",
  "technical",
  "forward",
] as const;

export function bulletsToKeyedFallback(bullets: string[]): Record<string, string> {
  const keyed: Record<string, string> = {};
  for (let i = 0; i < CANONICAL_SECTION_IDS.length; i++) {
    const id = CANONICAL_SECTION_IDS[i];
    keyed[id] = i < bullets.length ? bullets[i] : SECTION_UNAVAILABLE;
  }
  return keyed;
}

export function labelsFromKeyedOrOrdered(
  labels: ContextSectionLabel[]
): Record<string, ContextSectionLabel | undefined> {
  const byId: Record<string, ContextSectionLabel | undefined> = {};
  CANONICAL_SECTION_IDS.forEach((id, idx) => {
    byId[id] = labels[idx];
  });
  return byId;
}

export function resolveBulletSectionOrder(
  sections: ContextVisualSection[],
  bulletCount: number
): readonly string[] {
  void sections;
  void bulletCount;
  return CANONICAL_SECTION_IDS;
}

export function mapBulletsToSections(
  sections: ContextVisualSection[],
  bullets: string[],
  labels: ContextSectionLabel[],
  sectionBullets?: Record<string, string> | null
): {
  paired: { section: ContextVisualSection; bullet?: string; label?: ContextSectionLabel }[];
  orphanBullets: string[];
} {
  const bulletById = sectionBullets ?? bulletsToKeyedFallback(bullets);
  const labelById = labelsFromKeyedOrOrdered(labels);

  const paired = sections.map((section) => ({
    section,
    bullet: bulletById[section.id],
    label: labelById[section.id],
  }));

  const usedTexts = new Set(
    paired.map((p) => p.bullet).filter((b): b is string => Boolean(b))
  );
  const orphanBullets = bullets.filter((b) => !usedTexts.has(b));

  return { paired, orphanBullets };
}

export function shouldCollapseSectionCard(
  section: ContextVisualSection,
  bullet?: string
): boolean {
  return (
    section.stance === "unavailable" &&
    section.metrics.length === 0 &&
    section.sparkline.length < 2 &&
    (!bullet || bullet === SECTION_UNAVAILABLE)
  );
}
