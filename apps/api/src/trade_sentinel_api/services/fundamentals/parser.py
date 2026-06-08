"""yfinance / Finnhub fundamental parsing."""

from __future__ import annotations

import asyncio

import httpx

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    BalanceSheetQuarter,
    CashFlowQuarter,
    FundamentalsSnapshot,
    IncomeStatementQuarter,
    QuarterlyMetric,
)
from trade_sentinel_api.services.currency import (
    currencies_differ,
    fcf_mcap_ratio_suspicious,
    financial_currency_is_usd,
    fx_rate_financial_to_usd,
    normalize_ccy,
)
from trade_sentinel_api.services.fundamentals.benchmark import (
    _build_benchmark,
    _build_flags,
    _valuation_label,
)
from trade_sentinel_api.services.fundamentals.helpers import (
    _CAPEX_ROWS,
    _CASH_ROWS,
    _CURRENT_ASSETS_ROWS,
    _CURRENT_LIAB_ROWS,
    _DEBT_ROWS,
    _EPS_ROWS,
    _EQUITY_ROWS,
    _FCF_ROWS,
    _GROSS_PROFIT_ROWS,
    _NET_INCOME_ROWS,
    _OCF_ROWS,
    _OP_INCOME_ROWS,
    _REVENUE_ROWS,
    _period_label,
    _row_value,
    _safe_float,
    _scale_amount,
    _ttm_revenue_from_income,
)
from trade_sentinel_api.services.valuation import fetch_fund_valuation_sync

async def _fetch_finnhub_enrichment(ticker: str) -> dict | None:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return None
    symbol = ticker.upper().strip()
    headers = {"X-Finnhub-Token": settings.finnhub_api_key}
    base = "https://finnhub.io/api/v1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            rec_resp, metric_resp, pt_resp = await asyncio.gather(
                client.get(f"{base}/stock/recommendation", params={"symbol": symbol}),
                client.get(f"{base}/stock/metric", params={"symbol": symbol, "metric": "all"}),
                client.get(f"{base}/stock/price-target", params={"symbol": symbol}),
            )
            rec_data = rec_resp.json() if rec_resp.status_code == 200 else []
            metric_data = metric_resp.json() if metric_resp.status_code == 200 else {}
            pt_data = pt_resp.json() if pt_resp.status_code == 200 else {}
        return {"recommendation": rec_data, "metric": metric_data, "price_target": pt_data}
    except (httpx.HTTPError, ValueError):
        return None


def _merge_finnhub(snapshot: FundamentalsSnapshot, finnhub: dict) -> FundamentalsSnapshot:
    recs = finnhub.get("recommendation") or []
    if isinstance(recs, list) and recs:
        latest = recs[0]
        snapshot.analyst_buy = int(latest.get("buy", 0) or 0) + int(latest.get("strongBuy", 0) or 0)
        snapshot.analyst_sell = int(latest.get("sell", 0) or 0) + int(latest.get("strongSell", 0) or 0)
    metric = finnhub.get("metric") or {}
    series = metric.get("metric") or metric
    if isinstance(series, dict):
        if snapshot.roe is None:
            snapshot.roe = _safe_float(series.get("roeTTM") or series.get("roe"))
        if snapshot.pe_trailing is None:
            snapshot.pe_trailing = _safe_float(series.get("peTTM") or series.get("peBasicExclExtraTTM"))

    pt = finnhub.get("price_target") or {}
    if isinstance(pt, dict):
        mean = _safe_float(pt.get("targetMean"))
        if mean and mean > 0:
            snapshot.target_price = mean
            snapshot.target_price_low = _safe_float(pt.get("targetLow"))
            snapshot.target_price_high = _safe_float(pt.get("targetHigh"))
            snapshot.target_source = "finnhub"
    return snapshot


def _fetch_yfinance_fundamentals_sync(ticker: str, current_price: float | None) -> FundamentalsSnapshot:
    from trade_sentinel_api.services.yfinance_bundle import (
        fundamentals_from_bundle,
        load_ticker_bundle_sync,
    )

    bundle = load_ticker_bundle_sync(ticker)
    return fundamentals_from_bundle(bundle, current_price)


def _fundamentals_from_yf_data(
    symbol: str,
    stock,
    info: dict,
    q_inc,
    q_bal,
    q_cf,
    annual,
    hist,
    current_price: float | None,
) -> FundamentalsSnapshot:
    price = current_price or _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    pe_fwd = _safe_float(info.get("forwardPE"))
    pe_trail = _safe_float(info.get("trailingPE"))
    trading_ccy = normalize_ccy(info.get("currency"))
    financial_ccy = normalize_ccy(info.get("financialCurrency")) or trading_ccy
    usd_rate = fx_rate_financial_to_usd(financial_ccy)

    quarterly_trends = _build_quarterly_trends(q_inc, limit=4, usd_rate=usd_rate)
    balance_sheet_trends = _build_balance_sheet_trends(q_bal, limit=4, usd_rate=usd_rate)
    income_statement_trends = _build_income_statement_trends(q_inc, limit=4, usd_rate=usd_rate)
    ttm_revenue = _ttm_revenue_from_income(income_statement_trends)
    cash_flow_trends = _build_cash_flow_trends(q_cf, q_inc, limit=4, usd_rate=usd_rate)
    hist_quarters = _build_quarterly_trends(q_inc, limit=12, usd_rate=usd_rate)
    benchmark = _build_benchmark(
        hist_quarters,
        q_inc,
        q_bal,
        annual,
        hist,
        price,
        pe_fwd,
        pe_trail,
        usd_rate=usd_rate,
    )

    flags = _build_flags(info, price, quarterly_trends, benchmark)

    target = _safe_float(info.get("targetMeanPrice"))
    target_low = _safe_float(info.get("targetLowPrice"))
    target_high = _safe_float(info.get("targetHighPrice"))
    target_upside = None
    if target and price and price > 0:
        target_upside = round((target - price) / price * 100, 2)

    shares = _safe_float(info.get("sharesOutstanding"))

    fcf = _scale_amount(_row_value(q_cf, _FCF_ROWS, 0), usd_rate)
    analyst_buy, analyst_sell = _analyst_counts_from_yfinance(stock)

    quote_type = (info.get("quoteType") or "").upper() or None
    fund_val = None
    if quote_type in ("ETF", "MUTUALFUND", "INDEX"):
        fund_val = fetch_fund_valuation_sync(symbol)

    trailing_eps_quote = _safe_float(info.get("trailingEps"))
    forward_eps_quote = _safe_float(info.get("forwardEps"))

    snapshot = FundamentalsSnapshot(
        sector=info.get("sector"),
        industry=info.get("industry"),
        quote_type=quote_type,
        trading_currency=trading_ccy,
        financial_currency=financial_ccy,
        trailing_eps_quote=trailing_eps_quote,
        forward_eps_quote=forward_eps_quote,
        market_cap=_safe_float(info.get("marketCap")),
        pe_trailing=pe_trail,
        pe_forward=pe_fwd,
        price_to_sales=_safe_float(info.get("priceToSalesTrailing12Months")),
        price_to_book=_safe_float(info.get("priceToBook")),
        profit_margin=_safe_float(info.get("profitMargins")),
        operating_margin=_safe_float(info.get("operatingMargins")),
        revenue_growth=_safe_float(info.get("revenueGrowth")),
        earnings_growth=_safe_float(info.get("earningsGrowth")),
        roe=_safe_float(info.get("returnOnEquity")),
        debt_to_equity=_safe_float(info.get("debtToEquity")),
        current_ratio=_safe_float(info.get("currentRatio")),
        total_cash=_scale_amount(_safe_float(info.get("totalCash")), usd_rate),
        total_debt=_scale_amount(_safe_float(info.get("totalDebt")), usd_rate),
        free_cash_flow=fcf,
        ebitda=_scale_amount(_safe_float(info.get("ebitda")), usd_rate),
        enterprise_value=_safe_float(info.get("enterpriseValue")),
        payout_ratio=_safe_float(info.get("payoutRatio")),
        recommendation=info.get("recommendationKey"),
        analyst_buy=analyst_buy,
        analyst_sell=analyst_sell,
        target_price=target,
        target_price_low=target_low,
        target_price_high=target_high,
        target_source="yfinance" if target else None,
        target_upside_pct=target_upside,
        shares_outstanding=shares,
        ttm_revenue=ttm_revenue,
        fifty_two_week_high=_safe_float(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_safe_float(info.get("fiftyTwoWeekLow")),
        quarterly_trends=quarterly_trends,
        balance_sheet_trends=balance_sheet_trends,
        income_statement_trends=income_statement_trends,
        cash_flow_trends=cash_flow_trends,
        benchmark=benchmark,
        fundamental_flags=flags,
        valuation_label=_valuation_label(pe_fwd),
        fund_valuation=fund_val,
        data_available=bool(
            info.get("sector") or pe_trail or quarterly_trends or (fund_val and fund_val.data_available)
        ),
        message=None if (info.get("sector") or quarterly_trends or fund_val) else "Limited fundamental data.",
    )
    return _apply_currency_normalization(snapshot)


def _apply_currency_normalization(snapshot: FundamentalsSnapshot) -> FundamentalsSnapshot:
    """Finalize USD normalization flags (amounts scaled at fetch when FX available)."""
    from trade_sentinel_api.services import fundamentals as fund_api

    financial = snapshot.financial_currency
    trading = snapshot.trading_currency
    flags = list(snapshot.fundamental_flags)

    if financial_currency_is_usd(financial):
        return snapshot.model_copy(
            update={
                "monetary_values_normalized": True,
                "amounts_currency": "USD",
            }
        )

    rate = fund_api.fx_rate_financial_to_usd(financial)
    if rate is None:
        if "currency_mismatch_unresolved" not in flags:
            flags.append("currency_mismatch_unresolved")
        note = (
            f"Financials reported in {financial}; could not fetch FX to USD. "
            "Statement amounts may not be USD-comparable."
        )
        msg = snapshot.message or note
        if note not in (msg or ""):
            msg = f"{msg} {note}".strip() if msg else note
        return snapshot.model_copy(
            update={
                "fundamental_flags": flags,
                "monetary_values_normalized": False,
                "message": msg,
            }
        )

    if fcf_mcap_ratio_suspicious(snapshot.free_cash_flow, snapshot.market_cap):
        if "currency_mismatch_unresolved" not in flags:
            flags.append("currency_mismatch_unresolved")
        return snapshot.model_copy(
            update={
                "fundamental_flags": flags,
                "fx_rate_financial_to_trading": rate,
                "monetary_values_normalized": False,
                "message": (
                    snapshot.message
                    or f"FX conversion {financial}→USD failed sanity check — valuation restricted."
                ),
            }
        )

    if "currency_converted" not in flags:
        flags.append("currency_converted")
    fx_note = None
    if currencies_differ(trading, financial) and rate is not None:
        fx_note = (
            f"Statement amounts shown in USD ({financial}→USD @ {rate:.4f}). "
            "Quarterly EPS is USD per local share; ADR EPS uses quote trailing/forward."
        )
    msg = snapshot.message
    if fx_note and fx_note not in (msg or ""):
        msg = f"{msg} {fx_note}".strip() if msg else fx_note

    return snapshot.model_copy(
        update={
            "fx_rate_financial_to_trading": rate,
            "amounts_currency": "USD",
            "monetary_values_normalized": True,
            "fundamental_flags": flags,
            "message": msg,
        }
    )


def _build_balance_sheet_trends(
    q_bal, limit: int = 4, *, usd_rate: float | None = None
) -> list[BalanceSheetQuarter]:
    if q_bal is None or q_bal.empty:
        return []
    cols = list(q_bal.columns)[:limit]
    metrics: list[BalanceSheetQuarter] = []
    for col in cols:
        col_idx = list(q_bal.columns).index(col)
        debt = _scale_amount(_row_value(q_bal, _DEBT_ROWS, col_idx), usd_rate)
        equity = _scale_amount(_row_value(q_bal, _EQUITY_ROWS, col_idx), usd_rate)
        cash = _scale_amount(_row_value(q_bal, _CASH_ROWS, col_idx), usd_rate)
        cur_assets = _scale_amount(_row_value(q_bal, _CURRENT_ASSETS_ROWS, col_idx), usd_rate)
        cur_liab = _scale_amount(_row_value(q_bal, _CURRENT_LIAB_ROWS, col_idx), usd_rate)

        de_ratio = None
        if debt is not None and equity and equity != 0:
            de_ratio = round(debt / equity * 100, 2)

        net_debt = None
        if debt is not None and cash is not None:
            net_debt = round(debt - cash, 2)

        current_ratio = None
        if cur_assets is not None and cur_liab and cur_liab != 0:
            current_ratio = round(cur_assets / cur_liab, 2)

        if any(v is not None for v in (debt, equity, cash, de_ratio, net_debt, current_ratio)):
            metrics.append(
                BalanceSheetQuarter(
                    period=_period_label(col),
                    total_debt=debt,
                    total_equity=equity,
                    cash=cash,
                    debt_to_equity=de_ratio,
                    net_debt=net_debt,
                    current_ratio=current_ratio,
                )
            )
    return metrics


def _margin_pct(numerator: float | None, revenue: float | None) -> float | None:
    if numerator is None or revenue is None or revenue == 0:
        return None
    return round(numerator / revenue * 100, 2)


def _build_income_statement_trends(
    q_inc, limit: int = 4, *, usd_rate: float | None = None
) -> list[IncomeStatementQuarter]:
    if q_inc is None or q_inc.empty:
        return []
    cols = list(q_inc.columns)[:limit]
    metrics: list[IncomeStatementQuarter] = []
    for col in cols:
        col_idx = list(q_inc.columns).index(col)
        revenue = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, col_idx), usd_rate)
        gross = _scale_amount(_row_value(q_inc, _GROSS_PROFIT_ROWS, col_idx), usd_rate)
        op = _scale_amount(_row_value(q_inc, _OP_INCOME_ROWS, col_idx), usd_rate)
        net = _scale_amount(_row_value(q_inc, _NET_INCOME_ROWS, col_idx), usd_rate)
        gross_margin = _margin_pct(gross, revenue)
        op_margin = _margin_pct(op, revenue)
        net_margin = _margin_pct(net, revenue)
        if any(v is not None for v in (revenue, gross, op, net, gross_margin, op_margin, net_margin)):
            metrics.append(
                IncomeStatementQuarter(
                    period=_period_label(col),
                    revenue=revenue,
                    gross_profit=gross,
                    operating_income=op,
                    net_income=net,
                    gross_margin_pct=gross_margin,
                    operating_margin_pct=op_margin,
                    net_margin_pct=net_margin,
                )
            )
    return metrics


def _build_cash_flow_trends(
    q_cf, q_inc, limit: int = 4, *, usd_rate: float | None = None
) -> list[CashFlowQuarter]:
    if q_cf is None or q_cf.empty:
        return []
    cols = list(q_cf.columns)[:limit]
    metrics: list[CashFlowQuarter] = []
    for col in cols:
        col_idx = list(q_cf.columns).index(col)
        ocf = _scale_amount(_row_value(q_cf, _OCF_ROWS, col_idx), usd_rate)
        capex = _scale_amount(_row_value(q_cf, _CAPEX_ROWS, col_idx), usd_rate)
        fcf = _scale_amount(_row_value(q_cf, _FCF_ROWS, col_idx), usd_rate)
        revenue = None
        if q_inc is not None and not q_inc.empty:
            rev_idx = list(q_inc.columns).index(col) if col in q_inc.columns else col_idx
            if rev_idx < q_inc.shape[1]:
                revenue = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, rev_idx), usd_rate)
        fcf_margin = _margin_pct(fcf, revenue)
        if any(v is not None for v in (ocf, capex, fcf, fcf_margin)):
            metrics.append(
                CashFlowQuarter(
                    period=_period_label(col),
                    operating_cash_flow=ocf,
                    capital_expenditure=capex,
                    free_cash_flow=fcf,
                    fcf_margin_pct=fcf_margin,
                )
            )
    return metrics


def _build_quarterly_trends(
    q_inc, limit: int = 4, *, usd_rate: float | None = None
) -> list[QuarterlyMetric]:
    if q_inc is None or q_inc.empty:
        return []
    all_cols = list(q_inc.columns)
    cols = all_cols[:limit]
    metrics: list[QuarterlyMetric] = []
    for col in cols:
        full_i = all_cols.index(col)
        rev = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, full_i), usd_rate)
        eps = _scale_amount(_row_value(q_inc, _EPS_ROWS, full_i), usd_rate)
        qoq = None
        yoy = None
        if full_i + 1 < len(all_cols):
            prev_rev = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, full_i + 1), usd_rate)
            if rev is not None and prev_rev and prev_rev != 0:
                qoq = round((rev - prev_rev) / abs(prev_rev) * 100, 2)
        if full_i + 4 < len(all_cols):
            yoy_rev = _scale_amount(_row_value(q_inc, _REVENUE_ROWS, full_i + 4), usd_rate)
            if rev is not None and yoy_rev and yoy_rev != 0:
                yoy = round((rev - yoy_rev) / abs(yoy_rev) * 100, 2)
        metrics.append(
            QuarterlyMetric(
                period=_period_label(col),
                revenue=rev,
                eps=eps,
                revenue_qoq_pct=qoq,
                revenue_yoy_pct=yoy,
            )
        )
    return metrics


def _analyst_counts_from_yfinance(stock) -> tuple[int | None, int | None]:
    """Latest analyst recommendation counts from yfinance recommendations table."""
    try:
        rec = stock.recommendations
    except Exception:
        return None, None
    if rec is None or getattr(rec, "empty", True):
        return None, None
    try:
        row = rec.iloc[-1]
    except (IndexError, AttributeError, TypeError):
        return None, None

    def _sum_cols(*names: str) -> int | None:
        total = 0
        found = False
        for name in names:
            for col in row.index:
                if str(col).lower() == name.lower():
                    val = row[col]
                    if val is not None and not (isinstance(val, float) and val != val):
                        total += int(val)
                        found = True
                    break
        return total if found else None

    buy = _sum_cols("strongBuy", "buy")
    sell = _sum_cols("strongSell", "sell")
    return buy, sell

