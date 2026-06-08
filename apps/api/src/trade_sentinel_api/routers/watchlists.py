from fastapi import APIRouter

from trade_sentinel_api.models.schemas import Watchlist, WatchlistPatch, WatchlistUpdate
from trade_sentinel_api.services.watchlists import (
    get_watchlist,
    patch_watchlist_tickers,
    update_watchlist,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("/{name}", response_model=Watchlist)
async def read_watchlist(name: str = "default") -> Watchlist:
    return get_watchlist(name)


@router.put("/{name}", response_model=Watchlist)
async def put_watchlist(name: str, body: WatchlistUpdate) -> Watchlist:
    return update_watchlist(name, body)


@router.patch("/{name}/tickers", response_model=Watchlist)
async def patch_watchlist(name: str, body: WatchlistPatch) -> Watchlist:
    return patch_watchlist_tickers(name, body)
