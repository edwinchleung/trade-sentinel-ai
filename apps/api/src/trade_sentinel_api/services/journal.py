import json
import uuid
from datetime import UTC, datetime

from trade_sentinel_api.db import journal_insert, journal_list
from trade_sentinel_api.models.schemas import TradeJournalCreate, TradeJournalEntry


def _parse_warnings(raw) -> list[str]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return []


def _parse_created(raw) -> datetime:
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def list_journal_entries() -> list[TradeJournalEntry]:
    rows = journal_list()
    entries = []
    for row in rows:
        entries.append(
            TradeJournalEntry(
                id=row[0],
                ticker=row[1],
                direction=row[2],
                quantity=row[3],
                entry_price=row[4],
                account_size=row[5],
                instrument_type=row[6],
                ai_warnings=_parse_warnings(row[7]),
                created_at=_parse_created(row[8]),
            )
        )
    return entries


def create_journal_entry(data: TradeJournalCreate) -> TradeJournalEntry:
    entry_id = str(uuid.uuid4())
    created = datetime.now(UTC)
    journal_insert(
        entry_id=entry_id,
        ticker=data.ticker.upper(),
        direction=data.direction,
        quantity=data.quantity,
        entry_price=data.entry_price,
        account_size=data.account_size,
        instrument_type=data.instrument_type,
        ai_warnings=data.ai_warnings,
        created_iso=created.isoformat(),
    )
    return TradeJournalEntry(
        id=entry_id,
        ticker=data.ticker.upper(),
        direction=data.direction,
        quantity=data.quantity,
        entry_price=data.entry_price,
        account_size=data.account_size,
        instrument_type=data.instrument_type,
        ai_warnings=data.ai_warnings,
        created_at=created,
    )
