from fastapi import APIRouter

from trade_sentinel_api.models.schemas import TradeJournalCreate, TradeJournalEntry
from trade_sentinel_api.services.journal import create_journal_entry, list_journal_entries

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("", response_model=list[TradeJournalEntry])
async def get_journal() -> list[TradeJournalEntry]:
    return list_journal_entries()


@router.post("", response_model=TradeJournalEntry)
async def post_journal(body: TradeJournalCreate) -> TradeJournalEntry:
    return create_journal_entry(body)
