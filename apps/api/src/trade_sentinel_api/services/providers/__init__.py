"""Smart-money vendor provider registry."""

from __future__ import annotations

from trade_sentinel_api.config import get_settings
from trade_sentinel_api.services.providers.base import (
    CongressionalTradesProvider,
    DarkPoolProvider,
    GammaExposureProvider,
    NullProvider,
    OptionsTickProvider,
)

_PROVIDERS: dict[str, object] = {}


def _options_ticks_provider() -> OptionsTickProvider:
    settings = get_settings()
    if settings.polygon_api_key.strip() and settings.polygon_options_ticks_enabled:
        from trade_sentinel_api.services.providers.polygon_options_ticks import (
            PolygonOptionsTickProvider,
        )

        return PolygonOptionsTickProvider()
    return NullProvider(name="null", kind="options_ticks")  # type: ignore[return-value]


def _gamma_provider() -> GammaExposureProvider:
    settings = get_settings()
    if settings.squeezemetrics_api_key.strip():
        from trade_sentinel_api.services.providers.squeezemetrics import SqueezeMetricsProvider

        return SqueezeMetricsProvider()
    if settings.gex_compute_enabled:
        from trade_sentinel_api.services.gex_compute import ComputedGammaProvider

        return ComputedGammaProvider()
    return NullProvider(name="null", kind="gamma")  # type: ignore[return-value]


def _dark_pool_provider() -> DarkPoolProvider:
    settings = get_settings()
    if settings.unusual_whales_api_key.strip():
        from trade_sentinel_api.services.providers.unusual_whales import (
            UnusualWhalesDarkPoolProvider,
        )

        return UnusualWhalesDarkPoolProvider()
    from trade_sentinel_api.services.dark_pool_flow import FinraDarkPoolProxyProvider

    return FinraDarkPoolProxyProvider()


def _congressional_provider() -> CongressionalTradesProvider:
    settings = get_settings()
    provider = settings.congressional_trades_provider.strip().lower() or "capitol_trades"
    if provider == "capitol_trades":
        from trade_sentinel_api.services.providers.congressional import CapitolTradesProvider

        return CapitolTradesProvider()
    if provider == "house_senate_scrape":
        from trade_sentinel_api.services.providers.congressional import HouseSenateScrapeProvider

        return HouseSenateScrapeProvider()
    return NullProvider(name="null", kind="congressional")  # type: ignore[return-value]


_REGISTRY = {
    "options_ticks": _options_ticks_provider,
    "gamma": _gamma_provider,
    "dark_pool": _dark_pool_provider,
    "congressional": _congressional_provider,
}


def get_provider(kind: str) -> object:
    if kind in _PROVIDERS:
        return _PROVIDERS[kind]
    factory = _REGISTRY.get(kind)
    if factory is None:
        return NullProvider(name="null", kind=kind)
    inst = factory()
    _PROVIDERS[kind] = inst
    return inst
