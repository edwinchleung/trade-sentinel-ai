"""EdgarTools fetch/parse adapter mapped to Trade Sentinel schemas."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import (
    ActivistFeedItem,
    InsiderTransaction,
    SecFilingHighlight,
    SmartMoneyFeedItem,
)
from trade_sentinel_api.services.sec.bootstrap import bootstrap_edgartools
from trade_sentinel_api.services.sec.insider_classification import side_for_feed
from trade_sentinel_api.services.sec.registry import FilingSpec, get_filing_spec

logger = logging.getLogger(__name__)

_NOTABLE_NOTIONAL = 1_000_000
_TX_CODE_LABELS = {
    "P": "Purchase",
    "S": "Sale",
    "A": "Grant",
    "M": "Exercise",
    "G": "Gift",
    "F": "Tax payment",
}
_OPEN_MARKET_CODES = {"P", "S"}
_ACCESSION_RE = re.compile(r"(\d{10}-\d{2}-\d{6})")


def _ensure_edgar() -> None:
    bootstrap_edgartools()


def _filing_url(filing: Any) -> str | None:
    for attr in ("filing_url", "homepage_url", "url"):
        val = getattr(filing, attr, None)
        if val:
            return str(val)
    return None


def _filing_date_str(filing: Any) -> str:
    fd = getattr(filing, "filing_date", None)
    if fd is None:
        return date.today().isoformat()
    if hasattr(fd, "isoformat"):
        return str(fd.isoformat())[:10]
    return str(fd)[:10]


def _issuer_ticker(filing: Any, form4_obj: Any | None = None) -> str | None:
    if form4_obj is not None:
        issuer = getattr(form4_obj, "issuer", None)
        ticker = getattr(issuer, "ticker", None) if issuer is not None else None
        if ticker:
            return str(ticker).upper().strip()
        try:
            df = form4_obj.to_dataframe()
            if len(df) and "Ticker" in df.columns:
                val = df["Ticker"].iloc[0]
                if val and str(val) != "nan":
                    return str(val).upper().strip()
        except Exception:
            pass
    ticker = getattr(filing, "ticker", None)
    if ticker:
        return str(ticker).upper().strip()
    cik = getattr(filing, "cik", None)
    if cik:
        from trade_sentinel_api.services.sec.edgar import get_ticker_for_cik

        mapped = get_ticker_for_cik(str(cik).zfill(10))
        if mapped:
            return mapped
    return None


def _company_name(filing: Any, form4_obj: Any | None = None) -> str | None:
    if form4_obj is not None:
        issuer = getattr(form4_obj, "issuer", None)
        name = getattr(issuer, "name", None) if issuer is not None else None
        if name:
            return str(name)
    company = getattr(filing, "company", None)
    return str(company) if company else None


def parse_filing(filing: Any) -> tuple[Any | None, str | None]:
    """Safe filing.obj() wrapper."""
    try:
        obj = filing.obj()
        if obj is None:
            return None, "obj() returned None"
        return obj, None
    except Exception as exc:
        logger.debug("EdgarTools parse failed for %s: %s", getattr(filing, "form", "?"), exc)
        return None, str(exc)


SCHEDULE13_REGISTRY_TO_EDGAR: dict[str, str] = {
    "SC 13D": "SCHEDULE 13D",
    "SC 13G": "SCHEDULE 13G",
}


def schedule13_edgar_form(registry_key: str) -> str:
    return SCHEDULE13_REGISTRY_TO_EDGAR.get(registry_key, registry_key)


def _schedule13_allowed_forms(registry_form: str) -> set[str]:
    spec = get_filing_spec(registry_form)
    allowed = set(spec.current_forms) if spec else {registry_form}
    edgar_form = schedule13_edgar_form(registry_form)
    allowed.add(edgar_form)
    if edgar_form.startswith("SCHEDULE "):
        allowed.add(edgar_form.replace("SCHEDULE ", "SC ", 1))
        allowed.add(f"{edgar_form}/A")
        allowed.add(edgar_form.replace("SCHEDULE ", "SC ", 1) + "/A")
    return allowed


def fetch_current(form: str, *, max_entries: int | None = None) -> list[Any]:
    """Paginated current filings; filters to exact form match."""
    _ensure_edgar()
    from edgar import get_current_filings

    settings = get_settings()
    page_size = min(100, max(10, settings.edgar_current_page_size))
    cap = max_entries if max_entries is not None else settings.edgar_feed_max_entries
    spec = get_filing_spec(form)
    allowed: set[str] = set(spec.current_forms) if spec else {form}

    collected: list[Any] = []
    current = get_current_filings(page_size=page_size)
    if spec:
        if len(spec.current_forms) == 1:
            current = current.filter(form=spec.current_forms[0])
        else:
            current = current.filter(form=list(spec.current_forms))

    while current is not None and len(collected) < cap:
        for filing in current:
            if filing.form not in allowed:
                continue
            collected.append(filing)
            if len(collected) >= cap:
                break
        if len(collected) >= cap:
            break
        try:
            nxt = current.next()
        except Exception:
            break
        if nxt is None:
            break
        current = nxt
    return collected[:cap]


def fetch_form4_by_date_range(
    start: date,
    end: date,
    *,
    max_entries: int | None = None,
) -> list[Any]:
    """Fetch Form 4 filings for an inclusive filing_date range."""
    if start > end:
        start, end = end, start
    _ensure_edgar()
    from edgar import get_filings

    settings = get_settings()
    cap = max_entries if max_entries is not None else settings.edgar_feed_max_entries
    cap = min(cap, settings.edgar_feed_max_entries)
    date_filter = f"{start.isoformat()}:{end.isoformat()}"
    collected: list[Any] = []

    for year in range(start.year, end.year + 1):
        if len(collected) >= cap:
            break
        try:
            filings = get_filings(year, form="4", filing_date=date_filter)
        except Exception as exc:
            logger.debug("get_filings failed for %s form 4: %s", year, exc)
            continue
        if filings is None:
            continue
        try:
            batch = list(filings.head(cap - len(collected)))
        except Exception:
            try:
                batch = list(filings)[: cap - len(collected)]
            except Exception:
                batch = []
        for filing in batch:
            fd = _filing_date_str(filing)
            try:
                filing_day = date.fromisoformat(fd[:10])
            except ValueError:
                filing_day = None
            if filing_day is not None and (filing_day < start or filing_day > end):
                continue
            if getattr(filing, "form", "4") not in ("4", "4/A"):
                continue
            collected.append(filing)
            if len(collected) >= cap:
                break

    collected.sort(key=lambda f: _filing_date_str(f), reverse=True)
    return collected[:cap]


def _fetch_forms_by_date_range(
    form: str,
    start: date,
    end: date,
    *,
    allowed_forms: tuple[str, ...],
    max_entries: int | None = None,
) -> list[Any]:
    if start > end:
        start, end = end, start
    _ensure_edgar()
    from edgar import get_filings

    settings = get_settings()
    cap = max_entries if max_entries is not None else settings.edgar_feed_max_entries
    cap = min(cap, settings.edgar_feed_max_entries)
    date_filter = f"{start.isoformat()}:{end.isoformat()}"
    collected: list[Any] = []

    for year in range(start.year, end.year + 1):
        if len(collected) >= cap:
            break
        try:
            filings = get_filings(year, form=form, filing_date=date_filter)
        except Exception as exc:
            logger.debug("get_filings failed for %s form %s: %s", year, form, exc)
            continue
        if filings is None:
            continue
        try:
            batch = list(filings.head(cap - len(collected)))
        except Exception:
            batch = list(filings)[: cap - len(collected)] if filings else []
        for filing in batch:
            fform = getattr(filing, "form", form)
            if fform not in allowed_forms:
                continue
            fd = _filing_date_str(filing)
            try:
                filing_day = date.fromisoformat(fd[:10])
            except ValueError:
                filing_day = None
            if filing_day is not None and (filing_day < start or filing_day > end):
                continue
            collected.append(filing)
            if len(collected) >= cap:
                break
    collected.sort(key=lambda f: _filing_date_str(f), reverse=True)
    return collected[:cap]


def fetch_form3_by_date_range(
    start: date,
    end: date,
    *,
    max_entries: int | None = None,
) -> list[Any]:
    return _fetch_forms_by_date_range("3", start, end, allowed_forms=("3", "3/A"), max_entries=max_entries)


def fetch_form5_by_date_range(
    start: date,
    end: date,
    *,
    max_entries: int | None = None,
) -> list[Any]:
    return _fetch_forms_by_date_range("5", start, end, allowed_forms=("5", "5/A"), max_entries=max_entries)


def form3_to_baseline_dict(filing: Any, obj: Any) -> dict:
    insider_name = getattr(obj, "reporting_owner_name", None) or getattr(obj, "owner_name", None)
    if insider_name is None:
        try:
            df = obj.to_dataframe()
            if len(df) and "Owner" in df.columns:
                insider_name = df["Owner"].iloc[0]
        except Exception:
            insider_name = None
    title = getattr(obj, "officer_title", None) or getattr(obj, "title", None)
    shares = None
    try:
        df = obj.to_dataframe()
        if len(df) and "Shares" in df.columns:
            shares = float(df["Shares"].iloc[0])
    except Exception:
        pass
    return {
        "insider_name": str(insider_name) if insider_name else "Unknown insider",
        "title": str(title) if title else None,
        "shares": shares,
        "filing_date": _filing_date_str(filing),
        "source_form": "3",
    }


def form5_to_parsed_dict(filing: Any, obj: Any) -> dict:
    parsed = form4_to_parsed_dict(filing, obj)
    parsed["source_form"] = "5"
    return parsed


def filing_to_form3_feed_item(filing: Any) -> SmartMoneyFeedItem | None:
    link = _filing_url(filing)
    obj, _ = parse_filing(filing)
    if obj is None:
        return None
    baseline = form3_to_baseline_dict(filing, obj)
    return SmartMoneyFeedItem(
        ticker=_issuer_ticker(filing, obj),
        company_name=_company_name(filing, obj),
        filing_date=baseline["filing_date"],
        insider_name=baseline["insider_name"],
        title=baseline.get("title"),
        transaction_type="Initial insider statement (Form 3)",
        side="other",
        shares=baseline.get("shares"),
        filing_url=link,
        source_form="3",
        signal_type="insider_appointment",
    )


def fetch_schedule13_by_date_range(
    start: date,
    end: date,
    *,
    registry_form: str,
    max_entries: int | None = None,
) -> list[Any]:
    """Fetch Schedule 13D/G filings for an inclusive filing_date range."""
    if start > end:
        start, end = end, start
    _ensure_edgar()
    from edgar import get_filings

    settings = get_settings()
    cap = max_entries if max_entries is not None else settings.edgar_feed_max_entries
    cap = min(cap, settings.edgar_feed_max_entries)
    date_filter = f"{start.isoformat()}:{end.isoformat()}"
    allowed = _schedule13_allowed_forms(registry_form)
    edgar_form = schedule13_edgar_form(registry_form)
    collected: list[Any] = []

    for year in range(start.year, end.year + 1):
        if len(collected) >= cap:
            break
        try:
            filings = get_filings(year, form=edgar_form, filing_date=date_filter)
        except Exception as exc:
            logger.debug("get_filings failed for %s form %s: %s", year, edgar_form, exc)
            continue
        if filings is None:
            continue
        try:
            batch = list(filings.head(cap - len(collected)))
        except Exception:
            try:
                batch = list(filings)[: cap - len(collected)]
            except Exception:
                batch = []
        for filing in batch:
            fd = _filing_date_str(filing)
            try:
                filing_day = date.fromisoformat(fd[:10])
            except ValueError:
                filing_day = None
            if filing_day is not None and (filing_day < start or filing_day > end):
                continue
            form = getattr(filing, "form", "") or ""
            if form not in allowed:
                upper = form.upper()
                if registry_form == "SC 13D" and "13D" not in upper:
                    continue
                if registry_form == "SC 13G" and "13G" not in upper:
                    continue
            collected.append(filing)
            if len(collected) >= cap:
                break

    collected.sort(key=lambda f: _filing_date_str(f), reverse=True)
    return collected[:cap]


def fetch_company_filings(ticker: str, form: str | list[str], limit: int) -> list[Any]:
    _ensure_edgar()
    from edgar import Company

    company = Company(ticker.upper().strip())
    filings = company.get_filings(form=form)
    return list(filings.head(limit))


def filing_from_url(url: str) -> Any | None:
    _ensure_edgar()
    from edgar import get_by_accession_number

    match = _ACCESSION_RE.search(url)
    if not match:
        return None
    try:
        return get_by_accession_number(match.group(1))
    except Exception as exc:
        logger.debug("filing_from_url failed for %s: %s", url, exc)
        return None


def _tx_label(code: str | None) -> str:
    if not code:
        return "Form 4 filing"
    return _TX_CODE_LABELS.get(code.upper()[:1], f"Transaction ({code})")


def _tx_open_market(code: str | None) -> bool:
    return (code or "").upper()[:1] in _OPEN_MARKET_CODES


def _parse_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, str):
        val = val.strip().rstrip("%")
    try:
        f = float(val)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def form4_to_parsed_dict(filing: Any, obj: Any) -> dict:
    """Legacy dict shape for insider_filings excerpts."""
    insider_name = getattr(obj, "insider_name", None) or "Unknown insider"
    title = getattr(obj, "position", None)
    issuer = getattr(obj, "issuer", None)
    issuer_name = getattr(issuer, "name", None) if issuer else None
    issuer_symbol = _issuer_ticker(filing, obj)
    filing_date = _filing_date_str(filing)

    transactions: list[dict] = []
    derivative_transactions: list[dict] = []

    for tx in obj.get_transaction_activities():
        code = (getattr(tx, "code", None) or "").upper()[:1] or None
        is_deriv = bool(getattr(tx, "is_derivative", False))
        row = {
            "transaction_type": getattr(tx, "code_description", None)
            or _tx_label(code),
            "transaction_code": code,
            "shares": _parse_float(getattr(tx, "shares", None)),
            "price": _parse_float(
                getattr(tx, "price_per_share", None) or getattr(tx, "price_numeric", None)
            ),
            "filing_date": filing_date,
            "acquired_disposed": "A" if code == "P" else ("D" if code == "S" else None),
            "is_open_market": _tx_open_market(code),
            "is_derivative": is_deriv,
        }
        if is_deriv:
            derivative_transactions.append(row)
        else:
            transactions.append(row)

    if not transactions and not derivative_transactions:
        transactions.append(
            {
                "transaction_type": "Form 4 filing",
                "transaction_code": None,
                "shares": None,
                "price": None,
                "filing_date": filing_date,
                "is_open_market": False,
            }
        )

    first = transactions[0] if transactions else derivative_transactions[0]
    return {
        "insider_name": insider_name,
        "title": title,
        "issuer_name": issuer_name,
        "issuer_trading_symbol": issuer_symbol,
        "transactions": transactions,
        "derivative_transactions": derivative_transactions,
        "transaction_type": first.get("transaction_type"),
        "transaction_code": first.get("transaction_code"),
        "shares": first.get("shares"),
        "price": first.get("price"),
        "filing_date": filing_date,
        "is_open_market": first.get("is_open_market", False),
    }


def _items_from_parsed_dict(
    parsed: dict,
    *,
    ticker: str | None,
    company_name: str | None,
    link: str | None,
    default_filing_date: str,
) -> list[SmartMoneyFeedItem]:
    insider_name = parsed.get("insider_name") or "Unknown insider"
    insider_title = parsed.get("title")
    if not company_name:
        company_name = parsed.get("issuer_name")
    resolved_ticker = ticker or parsed.get("issuer_trading_symbol")
    if resolved_ticker:
        resolved_ticker = str(resolved_ticker).upper().strip()

    tx_rows = list(parsed.get("transactions") or [])
    tx_rows.extend(parsed.get("derivative_transactions") or [])
    if not tx_rows:
        tx_rows = [
            {
                "transaction_type": parsed.get("transaction_type") or "Form 4 filing",
                "transaction_code": parsed.get("transaction_code"),
                "shares": parsed.get("shares"),
                "price": parsed.get("price"),
                "filing_date": parsed.get("filing_date") or default_filing_date,
                "acquired_disposed": parsed.get("acquired_disposed"),
                "is_open_market": parsed.get("is_open_market", False),
            }
        ]

    items: list[SmartMoneyFeedItem] = []
    for tx in tx_rows:
        filing_date = tx.get("filing_date") or default_filing_date
        transaction_type = tx.get("transaction_type") or "Form 4 filing"
        transaction_code = tx.get("transaction_code")
        shares = tx.get("shares")
        price = tx.get("price")
        is_open_market = bool(tx.get("is_open_market"))
        side_val = side_for_feed(
            transaction_code=transaction_code,
            acquired_disposed=tx.get("acquired_disposed"),
            transaction_type=transaction_type,
            is_open_market=is_open_market,
        )
        notional = round(shares * price, 2) if shares and price else None
        is_notable = notional is not None and notional >= _NOTABLE_NOTIONAL
        items.append(
            SmartMoneyFeedItem(
                ticker=resolved_ticker,
                company_name=company_name,
                filing_date=str(filing_date)[:10],
                insider_name=insider_name,
                title=insider_title,
                transaction_type=transaction_type,
                transaction_code=transaction_code,
                shares=shares,
                price=price,
                notional=notional,
                side=side_val,
                filing_url=link,
                is_notable=is_notable,
                excerpt_available=True,
                is_open_market=is_open_market,
            )
        )
    return items


def filing_to_feed_items(filing: Any) -> tuple[list[SmartMoneyFeedItem], int, int]:
    """Returns (items, enriched_delta, parse_failed_delta)."""
    link = _filing_url(filing)
    default_date = _filing_date_str(filing)
    ticker = _issuer_ticker(filing)
    company_name = _company_name(filing)

    obj, err = parse_filing(filing)
    if obj is None:
        if err:
            return (
                [
                    SmartMoneyFeedItem(
                        ticker=ticker,
                        company_name=company_name,
                        filing_date=default_date,
                        insider_name="Unknown insider",
                        transaction_type="Form 4 filing",
                        side="other",
                        filing_url=link,
                        excerpt_available=False,
                        is_open_market=False,
                    )
                ],
                0,
                1,
            )
        return ([], 0, 0)

    parsed = form4_to_parsed_dict(filing, obj)
    resolved_ticker = _issuer_ticker(filing, obj) or ticker
    return (
        _items_from_parsed_dict(
            parsed,
            ticker=resolved_ticker,
            company_name=company_name or parsed.get("issuer_name"),
            link=link,
            default_filing_date=default_date,
        ),
        1,
        0,
    )


def filing_to_insider_transactions(
    filing: Any,
    *,
    limit: int = 10,
) -> list[InsiderTransaction]:
    link = _filing_url(filing)
    default_date = _filing_date_str(filing)
    obj, _ = parse_filing(filing)
    if obj is None:
        return [
            InsiderTransaction(
                filing_date=default_date,
                insider_name="Unknown insider",
                transaction_type="Form 4 filing",
                filing_url=link,
                is_open_market=False,
            )
        ]

    parsed = form4_to_parsed_dict(filing, obj)
    insider_name = parsed.get("insider_name") or "Unknown insider"
    title = parsed.get("title")
    rows = list(parsed.get("transactions") or [])
    rows.extend(parsed.get("derivative_transactions") or [])
    if not rows:
        rows = [parsed]

    results: list[InsiderTransaction] = []
    for tx in rows:
        results.append(
            InsiderTransaction(
                filing_date=str(tx.get("filing_date") or default_date)[:10],
                insider_name=insider_name,
                title=title,
                transaction_type=tx.get("transaction_type") or "Form 4 filing",
                shares=tx.get("shares"),
                price=tx.get("price"),
                filing_url=link,
                acquired_disposed=tx.get("acquired_disposed"),
                transaction_code=tx.get("transaction_code"),
                is_open_market=bool(tx.get("is_open_market")),
                is_derivative=bool(tx.get("is_derivative")),
                source_form=tx.get("source_form") or parsed.get("source_form") or "4",  # type: ignore[arg-type]
            )
        )
        if len(results) >= limit:
            break
    return results


def parse_form4_from_filing_url(url: str) -> dict | None:
    filing = filing_from_url(url)
    if filing is None:
        return None
    obj, _ = parse_filing(filing)
    if obj is None:
        return None
    return form4_to_parsed_dict(filing, obj)


def thirteenf_to_holdings(obj: Any) -> tuple[list[dict], str | None]:
    """Map ThirteenF object to internal holdings row dicts."""
    quarter_end = None
    for attr in ("report_period", "period_of_report", "quarter_end"):
        val = getattr(obj, attr, None)
        if val:
            quarter_end = str(val)[:10]
            break

    df = None
    for attr in ("infotable", "holdings"):
        val = getattr(obj, attr, None)
        if val is not None and hasattr(val, "empty") and not val.empty:
            df = val
            break

    if df is None:
        return [], quarter_end

    holdings: list[dict] = []
    for _, row in df.iterrows():
        cusip = row.get("Cusip") or row.get("CUSIP") or row.get("cusip")
        name = row.get("Issuer") or row.get("nameOfIssuer") or row.get("name")
        shares = row.get("SharesPrnAmount") or row.get("sshPrnamt") or row.get("shares")
        value = row.get("Value") or row.get("value")
        parsed_value = _parse_float(value)
        if parsed_value is not None:
            parsed_value *= 1000  # SEC 13F reports value in thousands of USD
        holdings.append(
            {
                "cusip": str(cusip).strip() if cusip is not None else None,
                "name": str(name).strip() if name is not None else None,
                "shares": _parse_float(shares),
                "value": parsed_value,
            }
        )
    return holdings, quarter_end


def schedule13_to_activist_fields(
    filing: Any,
    obj: Any,
    *,
    form_type: str,
) -> tuple[str | None, float | None]:
    filer_name = None
    percent_owned = None

    persons = getattr(obj, "reporting_persons", None)
    if persons:
        first = persons[0]
        if hasattr(first, "name") and getattr(first, "name", None):
            filer_name = str(first.name)
        elif isinstance(first, str):
            filer_name = first
        else:
            filer_name = str(first)

    if filer_name is None:
        for attr in ("reporting_person", "filer_name", "name"):
            val = getattr(obj, attr, None)
            if val:
                if isinstance(val, (list, tuple)) and val:
                    first = val[0]
                    filer_name = str(getattr(first, "name", first))
                else:
                    filer_name = str(val)
                break

    total_pct = getattr(obj, "total_percent", None)
    if total_pct is not None:
        percent_owned = _parse_float(total_pct)

    if percent_owned is None:
        for attr in (
            "percent_of_class",
            "percent_of_class_owned",
            "ownership_percent",
            "percent_ownership",
        ):
            val = getattr(obj, attr, None)
            if val is not None:
                percent_owned = _parse_float(val)
                if percent_owned is not None:
                    break

    if filer_name is None:
        filer_name = getattr(filing, "company", None)
        filer_name = str(filer_name) if filer_name else None

    return filer_name, percent_owned


def _schedule13_issuer_fields(obj: Any) -> tuple[str | None, str | None]:
    issuer = getattr(obj, "issuer_info", None)
    if issuer is None:
        return None, None
    company_name = getattr(issuer, "name", None)
    company_name = str(company_name) if company_name else None
    ticker = None
    for attr in ("ticker", "symbol"):
        val = getattr(issuer, attr, None)
        if val:
            ticker = str(val).upper().strip()
            break
    if not ticker:
        cik = getattr(issuer, "cik", None)
        if cik:
            from trade_sentinel_api.services.sec.edgar import get_ticker_for_cik

            ticker = get_ticker_for_cik(str(cik).zfill(10))
    return ticker, company_name


def filing_to_activist_item(filing: Any, *, form_type: str) -> ActivistFeedItem:
    default_date = _filing_date_str(filing)
    ticker = _issuer_ticker(filing)
    company_name = _company_name(filing)
    link = _filing_url(filing)

    filer_name = None
    percent_owned = None
    import trade_sentinel_api.services.sec.adapter as _edgartools

    obj, _ = _edgartools.parse_filing(filing)
    if obj is not None:
        filer_name, percent_owned = schedule13_to_activist_fields(
            filing, obj, form_type=form_type
        )
        issuer_ticker, issuer_name = _schedule13_issuer_fields(obj)
        if not ticker and issuer_ticker:
            ticker = issuer_ticker
        if not company_name and issuer_name:
            company_name = issuer_name

    is_13d = form_type.upper().startswith("13D") or "13D" in (filing.form or "")
    return ActivistFeedItem(
        ticker=ticker,
        company_name=company_name,
        filing_date=default_date,
        form_type="13D" if is_13d else "13G",
        filer_name=filer_name,
        percent_owned=percent_owned,
        is_activist=is_13d,
        filing_url=link,
        signal="new_activist_stake" if is_13d else "passive_large_stake",
    )


def eightk_to_highlight(filing: Any, obj: Any, *, form: str) -> SecFilingHighlight:
    link = _filing_url(filing)
    default_date = _filing_date_str(filing)
    event_items: list[str] = list(getattr(obj, "items", None) or [])

    excerpt_parts: list[str] = []
    for item_key in event_items[:5]:
        excerpt_parts.append(item_key)
        try:
            if hasattr(obj, "__getitem__"):
                body = obj[item_key]
                if body:
                    excerpt_parts.append(str(body)[:800])
        except Exception:
            pass

    if not excerpt_parts and hasattr(obj, "sections"):
        try:
            for section in list(obj.sections)[:3]:
                name = getattr(section, "name", str(section))
                event_items.append(name)
                if hasattr(obj, "__getitem__"):
                    body = obj.get(name) if hasattr(obj, "get") else obj[name]
                    if body:
                        excerpt_parts.append(str(body)[:800])
        except Exception:
            pass

    excerpt = "\n\n".join(excerpt_parts) if excerpt_parts else None
    cap = get_settings().edgar_generic_text_cap
    if excerpt and len(excerpt) > cap:
        excerpt = excerpt[: cap - 3] + "..."

    return SecFilingHighlight(
        form=form,
        filing_date=default_date,
        title=", ".join(event_items[:3]) if event_items else form,
        url=link,
        accession=getattr(filing, "accession_no", None) or getattr(filing, "accession_number", None),
        excerpt=excerpt,
        excerpt_available=bool(excerpt),
        excerpt_chars=len(excerpt) if excerpt else None,
        event_items=event_items or None,
    )


def normalize_generic(filing: Any, spec: FilingSpec) -> dict:
    """Best-effort normalized dict for registry/API responses."""
    obj, err = parse_filing(filing) if spec.supports_obj else (None, None)
    link = _filing_url(filing)
    payload: dict[str, Any] = {
        "form": filing.form,
        "category": spec.category,
        "company": getattr(filing, "company", None),
        "cik": getattr(filing, "cik", None),
        "ticker": _issuer_ticker(filing),
        "filing_date": _filing_date_str(filing),
        "filing_url": link,
        "accession": getattr(filing, "accession_no", None),
        "parse_error": err,
    }

    if obj is not None:
        payload["object_type"] = type(obj).__name__
        if hasattr(obj, "to_dataframe"):
            try:
                df = obj.to_dataframe()
                payload["rows"] = df.head(25).to_dict(orient="records")
            except Exception:
                pass
        for attr in ("infotable", "holdings"):
            val = getattr(obj, attr, None)
            if val is not None and hasattr(val, "head"):
                try:
                    payload["rows"] = val.head(25).to_dict(orient="records")
                    break
                except Exception:
                    pass

    cap = get_settings().edgar_generic_text_cap
    try:
        text = filing.text()
        if text:
            payload["text_excerpt"] = text[:cap]
    except Exception:
        pass

    return payload
