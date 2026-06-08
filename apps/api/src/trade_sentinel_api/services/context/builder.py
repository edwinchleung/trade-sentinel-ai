import asyncio
from datetime import UTC, datetime

from trade_sentinel_api.models.schemas import (
    TickerContext,
)
from trade_sentinel_api.services.cache import clear_cached
from trade_sentinel_api.services.context.facts import _build_facts
from trade_sentinel_api.services.context.visuals import attach_context_visuals
from trade_sentinel_api.services.data_gaps import sanitize_context_data_gaps
from trade_sentinel_api.services.sec.edgar import summarize_insider_activity
from trade_sentinel_api.services.forward_outlook import build_forward_outlook
from trade_sentinel_api.services.fundamental_assessment import build_fundamental_assessment
from trade_sentinel_api.services.sec.insider_filings import (
    build_metadata_highlights,
    compute_insider_data_quality,
    enrich_insider_filings,
)
from trade_sentinel_api.services.macro.context import macro_overlay_for_ticker
from trade_sentinel_api.services.reality_check import build_reality_check
from trade_sentinel_api.services.sector_context import (
    build_sector_context,
    get_sector_universe_stats,
)
from trade_sentinel_api.services.smart_money.assessment import build_smart_money_assessment
from trade_sentinel_api.services.technical_assessment import build_technical_assessment
from trade_sentinel_api.services.volume import build_volume_footprint
from trade_sentinel_api.services.warnings import (
    build_fundamental_warnings,
    build_technical_warnings,
)


def _ctx():
    """Lazy access so tests can patch trade_sentinel_api.services.context.*."""
    import trade_sentinel_api.services.context as context_api

    return context_api


def _finalize_summary_gaps(
    ctx: TickerContext,
    *,
    insider_data_quality: dict | None,
) -> TickerContext:
    if not ctx.summary:
        return ctx
    overlay = ctx.macro_overlay
    macro_signals = overlay.macro_signals if overlay else None
    cpi_yoy = (
        any(o.series_id == "CPI_YOY" for o in macro_signals.official)
        if macro_signals
        else False
    )
    sanitized = sanitize_context_data_gaps(
        ctx.summary.data_gaps,
        overlay.data_gaps if overlay else [],
        yield_curve_available=macro_signals.yield_curve_10y_3m_bps is not None
        if macro_signals
        else False,
        cpi_yoy_available=cpi_yoy,
        insider_quality=insider_data_quality,
    )
    return ctx.model_copy(
        update={"summary": ctx.summary.model_copy(update={"data_gaps": sanitized})}
    )


async def build_ticker_context(
    ticker: str,
    *,
    summarize: bool = False,
    include_insider: bool = False,
    include_options: bool = False,
) -> TickerContext:
    symbol = ticker.upper().strip()
    cache_key = f"{symbol}:{'sum' if summarize else 'raw'}:v23"
    if not include_insider and not include_options:
        cached = _ctx().get_cached("context", cache_key)
        if cached:
            summary = cached.get("summary")
            if summarize and _ctx().is_stale_llm_summary(summary):
                clear_cached("context", cache_key)
            else:
                return _finalize_summary_gaps(
                    attach_context_visuals(TickerContext(**cached)),
                    insider_data_quality=None,
                )

    market_task = _ctx().aggregate_market_context(symbol)
    earnings_task = _ctx().fetch_earnings_snapshot(symbol)
    sec_filings_task = _ctx().fetch_sec_filings(symbol)
    macro_bundle_task = _ctx().get_daily_macro_bundle()
    insider_task = _ctx().fetch_insider_timeline(symbol) if include_insider else None
    options_task = _ctx().analyze_options_flow(symbol) if include_options else None

    gather_tasks: list = [market_task, earnings_task, sec_filings_task, macro_bundle_task]
    if insider_task:
        gather_tasks.append(insider_task)
    if options_task:
        gather_tasks.append(options_task)

    results = await asyncio.gather(*gather_tasks)
    market = results[0]
    earnings = results[1]
    sec_filings = results[2]
    macro_bundle = results[3]
    idx = 4
    insider = results[idx] if insider_task else None
    if insider_task:
        idx += 1
    options_result = results[idx] if options_task else None

    fundamentals, valuation = await _ctx().resolve_ticker_valuation(
        symbol, price=market.get("price")
    )
    fundamental_assessment = build_fundamental_assessment(fundamentals)

    sector_stats = get_sector_universe_stats("sp500")
    sector_context = build_sector_context(
        symbol,
        fundamentals,
        valuation,
        universe="sp500",
        stats=sector_stats,
    )

    sector = fundamentals.sector if fundamentals else None
    macro_overlay = macro_overlay_for_ticker(symbol, sector, macro_bundle)

    hist = market.pop("_hist", None)
    week52 = market.pop("week52", {})
    technical_assessment = build_technical_assessment(
        hist,
        price=market.get("price") or 0.0,
        week52=week52,
    ) if hist is not None and market.get("price") is not None else None

    news = market.pop("news", [])
    news_digest = market.pop("news_digest", None)
    warnings = build_technical_warnings(
        market.get("rsi"),
        market.get("volume_ratio"),
        market.get("macd"),
        technical_assessment=technical_assessment,
    )
    fundamental_warnings = build_fundamental_warnings(fundamentals, earnings, valuation)

    insider_summary = None
    insider_filings = []
    insider_data_quality: dict | None = None
    if insider:
        insider_summary = summarize_insider_activity(insider.transactions)
        insider_summary, insider_filings = await enrich_insider_filings(
            insider_summary,
            insider.transactions,
        )
        if not insider_filings and insider.transactions:
            insider_filings = build_metadata_highlights(insider.transactions)
        insider_data_quality = compute_insider_data_quality(
            insider_filings,
            insider_requested=include_insider,
            timeline_count=len(insider.transactions),
        )
        insider_data_quality["feed_unavailable"] = not insider.transactions
    elif include_insider:
        insider_data_quality = compute_insider_data_quality(
            [],
            insider_requested=True,
            timeline_count=0,
        )
        insider_data_quality["feed_unavailable"] = True

    options_flow = None
    if options_result:
        options_flow, opt_warnings = options_result
        warnings = [*warnings, *opt_warnings]

    volume_footprint = None
    if hist is not None and market.get("price") is not None and (include_insider or include_options):
        volume_footprint = build_volume_footprint(
            hist,
            price=market.get("price") or 0,
            volume_ratio=market.get("volume_ratio"),
        )

    smart_money_assessment = None
    institutional_13f = None
    activist_filing = None
    if include_insider or include_options:
        changes_13f, activist_filing = await asyncio.gather(
            _ctx().fetch_13f_changes(symbol),
            _ctx().resolve_activist_filing(symbol),
        )
        institutional_13f = changes_13f
        activist_alert = activist_filing is not None
        smart_money_assessment = build_smart_money_assessment(
            ticker=symbol,
            insider_summary=insider_summary,
            options_flow=options_flow,
            volume_footprint=volume_footprint,
            institutional_conviction=changes_13f.conviction_buy,
            activist_alert=activist_alert,
            crowding_risk=changes_13f.crowding_risk,
        )

    forward_outlook = build_forward_outlook(
        price=market.get("price"),
        change_pct=market.get("change_pct"),
        earnings=earnings,
        fundamentals=fundamentals,
        news=news,
        sec_filings=sec_filings,
        insider_summary=insider_summary,
        warnings=warnings,
        macro_overlay=macro_overlay,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
    )

    reality_check = build_reality_check(
        valuation=valuation,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        news_digest=news_digest,
        warnings=warnings,
        forward_watch=forward_outlook.watch_items if forward_outlook else None,
    )

    bench = fundamentals.benchmark if fundamentals else None
    use_v10 = (
        summarize
        and (include_insider or include_options)
        and (
            (institutional_13f is not None and institutional_13f.data_available)
            or (smart_money_assessment is not None and smart_money_assessment.data_available)
            or activist_filing is not None
        )
    )
    use_v8 = (
        summarize
        and valuation.data_available
        and technical_assessment is not None
        and technical_assessment.data_available
        and fundamental_assessment.data_available
        and news_digest is not None
        and news_digest.data_available
        and sector_context.data_available
        and bench is not None
        and bench.pe_percentiles is not None
        and not use_v10
    )
    use_v7 = (
        summarize
        and valuation.data_available
        and technical_assessment is not None
        and technical_assessment.data_available
        and fundamental_assessment.data_available
        and news_digest is not None
        and news_digest.data_available
        and not use_v8
    )
    use_v6 = (
        summarize
        and valuation.data_available
        and technical_assessment is not None
        and technical_assessment.data_available
        and not use_v7
        and not use_v8
    )
    use_v5 = (
        summarize
        and valuation.data_available
        and not use_v6
        and not use_v7
        and not use_v8
    )
    use_v3 = (
        summarize
        and fundamentals is not None
        and fundamentals.data_available
        and not use_v5
        and not use_v6
        and not use_v7
        and not use_v8
    )
    use_v2 = (
        summarize
        and not use_v3
        and not use_v5
        and not use_v6
        and not use_v7
        and not use_v8
        and (
            include_insider
            or include_options
            or (earnings and earnings.data_available)
        )
    )
    use_v4 = (
        summarize
        and macro_overlay.has_content
        and not use_v5
        and not use_v6
        and not use_v7
        and not use_v8
    )
    prompt_version = (
        "v10"
        if use_v10
        else (
            "v8"
            if use_v8
            else (
                "v7"
                if use_v7
                else (
                    "v6"
                    if use_v6
                    else (
                        "v5"
                        if use_v5
                        else ("v4" if use_v4 else ("v3" if use_v3 else ("v2" if use_v2 else "v1")))
                    )
                )
            )
        )
    )

    facts = _build_facts(
        symbol,
        market,
        news,
        earnings,
        fundamentals,
        valuation,
        sec_filings,
        insider_summary,
        insider_filings,
        options_flow,
        forward_outlook,
        macro_overlay=macro_overlay,
        include_insider=include_insider,
        insider_data_quality=insider_data_quality,
        warnings=warnings,
        fundamental_warnings=fundamental_warnings,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        news_digest=news_digest,
        reality_check=reality_check,
        sector_context=sector_context,
        smart_money_assessment=smart_money_assessment,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
        volume_footprint=volume_footprint,
    )

    summary = None
    if summarize:
        summary = await _ctx().summarize_context(facts, prompt_version=prompt_version)

    ctx = TickerContext(
        ticker=symbol,
        as_of=datetime.now(UTC),
        price=market.get("price"),
        change_pct=market.get("change_pct"),
        market_state=market.get("market_state"),
        price_source=market.get("price_source"),
        previous_close=market.get("previous_close"),
        regular_market_price=market.get("regular_market_price"),
        extended_price=market.get("extended_price"),
        is_extended_hours=market.get("is_extended_hours") or False,
        quote_as_of=market.get("quote_as_of"),
        volume=market.get("volume"),
        volume_avg_30d=market.get("volume_avg_30d"),
        volume_ratio=market.get("volume_ratio"),
        rsi=market.get("rsi"),
        macd=market.get("macd"),
        news=news,
        news_digest=news_digest,
        warnings=warnings,
        fundamental_warnings=fundamental_warnings,
        summary=summary,
        price_history=market.get("price_history", []),
        fundamentals=fundamentals,
        sec_filings=sec_filings,
        insider=insider,
        insider_summary=insider_summary,
        insider_filings=insider_filings,
        forward_outlook=forward_outlook,
        earnings=earnings,
        options_flow=options_flow,
        macro_overlay=macro_overlay,
        valuation=valuation,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        reality_check=reality_check,
        sector_context=sector_context,
        volume_footprint=volume_footprint,
        smart_money_assessment=smart_money_assessment,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
    )

    ctx = _finalize_summary_gaps(ctx, insider_data_quality=insider_data_quality)
    ctx = attach_context_visuals(ctx)

    if market.get("price") is not None and not include_insider and not include_options:
        _ctx().set_cached("context", cache_key, ctx.model_dump(mode="json"))
    return ctx


async def build_ticker_context(
    ticker: str,
    *,
    summarize: bool = False,
    include_insider: bool = False,
    include_options: bool = False,
) -> TickerContext:
    symbol = ticker.upper().strip()
    cache_key = f"{symbol}:{'sum' if summarize else 'raw'}:v23"
    if not include_insider and not include_options:
        cached = _ctx().get_cached("context", cache_key)
        if cached:
            summary = cached.get("summary")
            if summarize and _ctx().is_stale_llm_summary(summary):
                clear_cached("context", cache_key)
            else:
                return _finalize_summary_gaps(
                    attach_context_visuals(TickerContext(**cached)),
                    insider_data_quality=None,
                )

    market_task = _ctx().aggregate_market_context(symbol)
    earnings_task = _ctx().fetch_earnings_snapshot(symbol)
    sec_filings_task = _ctx().fetch_sec_filings(symbol)
    macro_bundle_task = _ctx().get_daily_macro_bundle()
    insider_task = _ctx().fetch_insider_timeline(symbol) if include_insider else None
    options_task = _ctx().analyze_options_flow(symbol) if include_options else None

    gather_tasks: list = [market_task, earnings_task, sec_filings_task, macro_bundle_task]
    if insider_task:
        gather_tasks.append(insider_task)
    if options_task:
        gather_tasks.append(options_task)

    results = await asyncio.gather(*gather_tasks)
    market = results[0]
    earnings = results[1]
    sec_filings = results[2]
    macro_bundle = results[3]
    idx = 4
    insider = results[idx] if insider_task else None
    if insider_task:
        idx += 1
    options_result = results[idx] if options_task else None

    fundamentals, valuation = await _ctx().resolve_ticker_valuation(
        symbol, price=market.get("price")
    )
    fundamental_assessment = build_fundamental_assessment(fundamentals)

    sector_stats = get_sector_universe_stats("sp500")
    sector_context = build_sector_context(
        symbol,
        fundamentals,
        valuation,
        universe="sp500",
        stats=sector_stats,
    )

    sector = fundamentals.sector if fundamentals else None
    macro_overlay = macro_overlay_for_ticker(symbol, sector, macro_bundle)

    hist = market.pop("_hist", None)
    week52 = market.pop("week52", {})
    technical_assessment = build_technical_assessment(
        hist,
        price=market.get("price") or 0.0,
        week52=week52,
    ) if hist is not None and market.get("price") is not None else None

    news = market.pop("news", [])
    news_digest = market.pop("news_digest", None)
    warnings = build_technical_warnings(
        market.get("rsi"),
        market.get("volume_ratio"),
        market.get("macd"),
        technical_assessment=technical_assessment,
    )
    fundamental_warnings = build_fundamental_warnings(fundamentals, earnings, valuation)

    insider_summary = None
    insider_filings = []
    insider_data_quality: dict | None = None
    if insider:
        insider_summary = summarize_insider_activity(insider.transactions)
        insider_summary, insider_filings = await enrich_insider_filings(
            insider_summary,
            insider.transactions,
        )
        if not insider_filings and insider.transactions:
            insider_filings = build_metadata_highlights(insider.transactions)
        insider_data_quality = compute_insider_data_quality(
            insider_filings,
            insider_requested=include_insider,
            timeline_count=len(insider.transactions),
        )
        insider_data_quality["feed_unavailable"] = not insider.transactions
    elif include_insider:
        insider_data_quality = compute_insider_data_quality(
            [],
            insider_requested=True,
            timeline_count=0,
        )
        insider_data_quality["feed_unavailable"] = True

    options_flow = None
    if options_result:
        options_flow, opt_warnings = options_result
        warnings = [*warnings, *opt_warnings]

    volume_footprint = None
    if hist is not None and market.get("price") is not None and (include_insider or include_options):
        volume_footprint = build_volume_footprint(
            hist,
            price=market.get("price") or 0,
            volume_ratio=market.get("volume_ratio"),
        )

    smart_money_assessment = None
    institutional_13f = None
    activist_filing = None
    if include_insider or include_options:
        changes_13f, activist_filing = await asyncio.gather(
            _ctx().fetch_13f_changes(symbol),
            _ctx().resolve_activist_filing(symbol),
        )
        institutional_13f = changes_13f
        activist_alert = activist_filing is not None
        smart_money_assessment = build_smart_money_assessment(
            ticker=symbol,
            insider_summary=insider_summary,
            options_flow=options_flow,
            volume_footprint=volume_footprint,
            institutional_conviction=changes_13f.conviction_buy,
            activist_alert=activist_alert,
            crowding_risk=changes_13f.crowding_risk,
        )

    forward_outlook = build_forward_outlook(
        price=market.get("price"),
        change_pct=market.get("change_pct"),
        earnings=earnings,
        fundamentals=fundamentals,
        news=news,
        sec_filings=sec_filings,
        insider_summary=insider_summary,
        warnings=warnings,
        macro_overlay=macro_overlay,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
    )

    reality_check = build_reality_check(
        valuation=valuation,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        news_digest=news_digest,
        warnings=warnings,
        forward_watch=forward_outlook.watch_items if forward_outlook else None,
    )

    bench = fundamentals.benchmark if fundamentals else None
    use_v10 = (
        summarize
        and (include_insider or include_options)
        and (
            (institutional_13f is not None and institutional_13f.data_available)
            or (smart_money_assessment is not None and smart_money_assessment.data_available)
            or activist_filing is not None
        )
    )
    use_v8 = (
        summarize
        and valuation.data_available
        and technical_assessment is not None
        and technical_assessment.data_available
        and fundamental_assessment.data_available
        and news_digest is not None
        and news_digest.data_available
        and sector_context.data_available
        and bench is not None
        and bench.pe_percentiles is not None
        and not use_v10
    )
    use_v7 = (
        summarize
        and valuation.data_available
        and technical_assessment is not None
        and technical_assessment.data_available
        and fundamental_assessment.data_available
        and news_digest is not None
        and news_digest.data_available
        and not use_v8
    )
    use_v6 = (
        summarize
        and valuation.data_available
        and technical_assessment is not None
        and technical_assessment.data_available
        and not use_v7
        and not use_v8
    )
    use_v5 = (
        summarize
        and valuation.data_available
        and not use_v6
        and not use_v7
        and not use_v8
    )
    use_v3 = (
        summarize
        and fundamentals is not None
        and fundamentals.data_available
        and not use_v5
        and not use_v6
        and not use_v7
        and not use_v8
    )
    use_v2 = (
        summarize
        and not use_v3
        and not use_v5
        and not use_v6
        and not use_v7
        and not use_v8
        and (
            include_insider
            or include_options
            or (earnings and earnings.data_available)
        )
    )
    use_v4 = (
        summarize
        and macro_overlay.has_content
        and not use_v5
        and not use_v6
        and not use_v7
        and not use_v8
    )
    prompt_version = (
        "v10"
        if use_v10
        else (
            "v8"
            if use_v8
            else (
                "v7"
                if use_v7
                else (
                    "v6"
                    if use_v6
                    else (
                        "v5"
                        if use_v5
                        else ("v4" if use_v4 else ("v3" if use_v3 else ("v2" if use_v2 else "v1")))
                    )
                )
            )
        )
    )

    facts = _build_facts(
        symbol,
        market,
        news,
        earnings,
        fundamentals,
        valuation,
        sec_filings,
        insider_summary,
        insider_filings,
        options_flow,
        forward_outlook,
        macro_overlay=macro_overlay,
        include_insider=include_insider,
        insider_data_quality=insider_data_quality,
        warnings=warnings,
        fundamental_warnings=fundamental_warnings,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        news_digest=news_digest,
        reality_check=reality_check,
        sector_context=sector_context,
        smart_money_assessment=smart_money_assessment,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
        volume_footprint=volume_footprint,
    )

    summary = None
    if summarize:
        summary = await _ctx().summarize_context(facts, prompt_version=prompt_version)

    ctx = TickerContext(
        ticker=symbol,
        as_of=datetime.now(UTC),
        price=market.get("price"),
        change_pct=market.get("change_pct"),
        market_state=market.get("market_state"),
        price_source=market.get("price_source"),
        previous_close=market.get("previous_close"),
        regular_market_price=market.get("regular_market_price"),
        extended_price=market.get("extended_price"),
        is_extended_hours=market.get("is_extended_hours") or False,
        quote_as_of=market.get("quote_as_of"),
        volume=market.get("volume"),
        volume_avg_30d=market.get("volume_avg_30d"),
        volume_ratio=market.get("volume_ratio"),
        rsi=market.get("rsi"),
        macd=market.get("macd"),
        news=news,
        news_digest=news_digest,
        warnings=warnings,
        fundamental_warnings=fundamental_warnings,
        summary=summary,
        price_history=market.get("price_history", []),
        fundamentals=fundamentals,
        sec_filings=sec_filings,
        insider=insider,
        insider_summary=insider_summary,
        insider_filings=insider_filings,
        forward_outlook=forward_outlook,
        earnings=earnings,
        options_flow=options_flow,
        macro_overlay=macro_overlay,
        valuation=valuation,
        technical_assessment=technical_assessment,
        fundamental_assessment=fundamental_assessment,
        reality_check=reality_check,
        sector_context=sector_context,
        volume_footprint=volume_footprint,
        smart_money_assessment=smart_money_assessment,
        institutional_13f=institutional_13f,
        activist_filing=activist_filing,
    )

    ctx = _finalize_summary_gaps(ctx, insider_data_quality=insider_data_quality)
    ctx = attach_context_visuals(ctx)

    if market.get("price") is not None and not include_insider and not include_options:
        _ctx().set_cached("context", cache_key, ctx.model_dump(mode="json"))
    return ctx


