"""Deterministic forward-looking context from existing snapshot fields."""

from trade_sentinel_api.models.schemas import (
    ActivistFeedItem,
    EarningsSnapshot,
    ForwardOutlook,
    FundamentalsSnapshot,
    InsiderSummary,
    Institutional13FChanges,
    MacroContextOverlay,
    NewsItem,
    SecFilingsFeed,
    Warning,
)


def build_forward_outlook(
    *,
    price: float | None,
    change_pct: float | None,
    earnings: EarningsSnapshot | None,
    fundamentals: FundamentalsSnapshot | None,
    news: list[NewsItem],
    sec_filings: SecFilingsFeed | None,
    insider_summary: InsiderSummary | None,
    warnings: list[Warning],
    macro_overlay: MacroContextOverlay | None = None,
    institutional_13f: Institutional13FChanges | None = None,
    activist_filing: ActivistFeedItem | None = None,
) -> ForwardOutlook:
    watch: list[str] = []

    if macro_overlay and macro_overlay.relevant_events:
        for ev in macro_overlay.relevant_events:
            if ev.impact not in ("high", "moderate"):
                continue
            sectors = ", ".join(ev.sectors[:3]) if ev.sectors else "Broad Market"
            line = f"Macro today: {ev.name} ({ev.impact}) — {sectors}"
            if ev.surprise_pct is not None and ev.beat_miss not in (None, "unavailable"):
                line += f"; surprise {ev.surprise_pct:+.1f}% ({ev.beat_miss})"
            watch.append(line)
            if len(watch) >= 2:
                break

    if earnings and earnings.next_report_date:
        days = earnings.days_until
        if days is not None and days >= 0:
            watch.append(f"Earnings in {days} day(s) on {earnings.next_report_date}")
        else:
            watch.append(f"Upcoming earnings: {earnings.next_report_date}")

    for item in news[:2]:
        if item.title:
            watch.append(f"News: {item.title}")

    if sec_filings and sec_filings.filings:
        f0 = sec_filings.filings[0]
        line = f"SEC {f0.form} ({f0.filing_date}): {f0.title or f0.form}"
        if f0.excerpt_available and f0.excerpt:
            snippet = f0.excerpt.split("\n")[0][:120]
            line += f" — {snippet}"
        watch.append(line)

    if insider_summary and insider_summary.data_available:
        watch.append(
            f"Insider signal (90d): {insider_summary.sentiment} "
            f"({insider_summary.buy_count} buys / {insider_summary.sell_count} sells)"
        )

    if institutional_13f and institutional_13f.data_available and institutional_13f.changes:
        ch = institutional_13f.changes[0]
        pct = (
            f" ({ch.pct_change:+.0f}% QoQ)"
            if ch.pct_change is not None
            else ""
        )
        note = f" — {ch.quarter_note}" if ch.quarter_note else " (quarterly, delayed)"
        watch.append(f"13F: {ch.filer_name} {ch.change_type}{pct}{note}")

    if activist_filing:
        pct = (
            f" at {activist_filing.percent_owned:.1f}%"
            if activist_filing.percent_owned is not None
            else ""
        )
        filer = activist_filing.filer_name or "Unknown filer"
        watch.append(f"Activist 13D ({activist_filing.filing_date}): {filer}{pct}")

    for w in warnings:
        sev = w.severity.value if hasattr(w.severity, "value") else str(w.severity)
        if sev in ("high", "medium") and len(watch) < 5:
            watch.append(f"Technical: {w.code}")

    watch = watch[:5]

    bullets: list[str] = []
    if fundamentals and fundamentals.target_upside_pct is not None:
        bullets.append(
            f"Analyst target ${fundamentals.target_price or 0:.2f} "
            f"({fundamentals.target_upside_pct:+.1f}% vs current price)."
        )
    if earnings and earnings.next_report_date:
        bullets.append(f"Next earnings date: {earnings.next_report_date}.")
    if fundamentals and fundamentals.revenue_growth is not None:
        bullets.append(
            f"Reported revenue growth: {fundamentals.revenue_growth * 100:.1f}%."
        )
    if change_pct is not None and price is not None:
        bullets.append(f"Recent price move: {change_pct:+.2f}% (last ${price:.2f}).")

    data_available = bool(bullets or watch)

    return ForwardOutlook(
        next_earnings_date=earnings.next_report_date if earnings else None,
        days_until_earnings=earnings.days_until if earnings else None,
        analyst_target=fundamentals.target_price if fundamentals else None,
        target_upside_pct=fundamentals.target_upside_pct if fundamentals else None,
        recommendation=fundamentals.recommendation if fundamentals else None,
        revenue_growth=fundamentals.revenue_growth if fundamentals else None,
        earnings_growth=fundamentals.earnings_growth if fundamentals else None,
        watch_items=watch,
        outlook_bullets=bullets[:3],
        data_available=data_available,
    )
