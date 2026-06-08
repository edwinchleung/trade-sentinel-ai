"""Generic SEC current filings API backed by EdgarTools."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.models.schemas import CurrentFilingsResponse, FilingSummary
from trade_sentinel_api.services.cache import get_cached, set_cached_ttl
from trade_sentinel_api.services.sec.adapter import fetch_current, normalize_generic
from trade_sentinel_api.services.sec.registry import get_filing_spec, list_registry_forms

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/forms")
async def list_forms() -> dict:
    return {"forms": list_registry_forms()}


@router.get("/current", response_model=CurrentFilingsResponse)
async def current_filings(
    form: str = Query(..., description="SEC form key, e.g. 4, 8-K, 13F-HR, NPORT-P"),
    limit: int = Query(50, ge=1, le=200),
) -> CurrentFilingsResponse:
    spec = get_filing_spec(form)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unsupported form: {form}")

    cache_key = f"{spec.key}:{limit}"
    cached = get_cached("edgar_current_filings", cache_key)
    if cached:
        return CurrentFilingsResponse(**cached)

    try:
        filings = await asyncio.to_thread(fetch_current, spec.key, max_entries=limit)
    except Exception as exc:
        return CurrentFilingsResponse(
            as_of=datetime.now(UTC),
            form=spec.key,
            data_available=False,
            message=f"Current filings unavailable: {exc}",
        )

    items: list[FilingSummary] = []
    for filing in filings:
        payload = normalize_generic(filing, spec)
        items.append(FilingSummary(**payload))

    response = CurrentFilingsResponse(
        as_of=datetime.now(UTC),
        form=spec.key,
        count=len(items),
        items=items,
        data_available=len(items) > 0,
        message=None if items else f"No current filings for {spec.key}.",
    )
    ttl = get_settings().edgar_registry_cache_minutes * 60
    set_cached_ttl("edgar_current_filings", cache_key, response.model_dump(mode="json"), ttl)
    return response


@router.get("/{accession}/summary", response_model=FilingSummary)
async def filing_summary(accession: str) -> FilingSummary:
    from trade_sentinel_api.services.sec.adapter import filing_from_url

    filing = await asyncio.to_thread(filing_from_url, accession)
    if filing is None:
        try:
            from edgar import get_by_accession_number

            filing = await asyncio.to_thread(get_by_accession_number, accession)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Filing not found: {exc}") from exc

    spec = get_filing_spec(filing.form)
    if spec is None:
        spec_key = filing.form
        from trade_sentinel_api.services.sec.registry import FilingSpec

        spec = FilingSpec(
            key=spec_key,
            current_forms=(filing.form,),
            category=filing.form,
            product="registry_only",
            supports_obj=True,
        )
    payload = normalize_generic(filing, spec)
    return FilingSummary(**payload)
