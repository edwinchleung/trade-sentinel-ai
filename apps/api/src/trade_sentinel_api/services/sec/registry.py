"""Registry of SEC form types supported via edgartools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProductTier = Literal[
    "insider_feed",
    "institutional",
    "activist",
    "events",
    "registry_only",
]


@dataclass(frozen=True)
class FilingSpec:
    key: str
    current_forms: tuple[str, ...]
    category: str
    product: ProductTier
    supports_obj: bool = True
    background_warm: bool = False


FILING_REGISTRY: dict[str, FilingSpec] = {
    "4": FilingSpec(
        key="4",
        current_forms=("4",),
        category="Insider Trades (Form 4)",
        product="insider_feed",
        background_warm=True,
    ),
    "8-K": FilingSpec(
        key="8-K",
        current_forms=("8-K", "8-K/A"),
        category="Current Events (8-K)",
        product="events",
    ),
    "6-K": FilingSpec(
        key="6-K",
        current_forms=("6-K", "6-K/A"),
        category="Foreign Issuer Reports (6-K)",
        product="events",
    ),
    "SC 13D": FilingSpec(
        key="SC 13D",
        current_forms=("SC 13D", "SC 13D/A"),
        category="Beneficial Ownership (13D)",
        product="activist",
        background_warm=True,
    ),
    "SC 13G": FilingSpec(
        key="SC 13G",
        current_forms=("SC 13G", "SC 13G/A"),
        category="Beneficial Ownership (13G)",
        product="activist",
        background_warm=True,
    ),
    "13F-HR": FilingSpec(
        key="13F-HR",
        current_forms=("13F-HR", "13F-HR/A"),
        category="Institutional Holdings (13F)",
        product="institutional",
    ),
    "NPORT-P": FilingSpec(
        key="NPORT-P",
        current_forms=("NPORT-P",),
        category="Fund Portfolios (N-PORT)",
        product="registry_only",
    ),
    "N-MFP": FilingSpec(
        key="N-MFP",
        current_forms=("N-MFP", "N-MFP1", "N-MFP2"),
        category="Money Market Funds (N-MFP)",
        product="registry_only",
    ),
    "N-CEN": FilingSpec(
        key="N-CEN",
        current_forms=("N-CEN",),
        category="Fund Census (N-CEN)",
        product="registry_only",
    ),
    "N-CSR": FilingSpec(
        key="N-CSR",
        current_forms=("N-CSR", "N-CSR/A"),
        category="Fund Shareholder Reports (N-CSR)",
        product="registry_only",
    ),
    "24F-2NT": FilingSpec(
        key="24F-2NT",
        current_forms=("24F-2NT",),
        category="Fund Fee Notices (24F-2NT)",
        product="registry_only",
    ),
    "DEF 14A": FilingSpec(
        key="DEF 14A",
        current_forms=("DEF 14A", "DEFA14A"),
        category="Proxy Statements (DEF 14A)",
        product="registry_only",
    ),
    "D": FilingSpec(
        key="D",
        current_forms=("D", "D/A"),
        category="Private Offerings (Form D)",
        product="registry_only",
    ),
    "C": FilingSpec(
        key="C",
        current_forms=("C", "C-U", "C-AR", "C-TR"),
        category="Crowdfunding (Form C)",
        product="registry_only",
    ),
    "144": FilingSpec(
        key="144",
        current_forms=("144", "144/A"),
        category="Sale Notices (Form 144)",
        product="registry_only",
    ),
    "N-PX": FilingSpec(
        key="N-PX",
        current_forms=("N-PX",),
        category="Fund Voting (N-PX)",
        product="registry_only",
    ),
    "10-D": FilingSpec(
        key="10-D",
        current_forms=("10-D",),
        category="ABS Distribution (10-D)",
        product="registry_only",
    ),
    "424B": FilingSpec(
        key="424B",
        current_forms=("424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8"),
        category="Prospectus Supplements (424B)",
        product="registry_only",
        supports_obj=False,
    ),
    "S-3": FilingSpec(
        key="S-3",
        current_forms=("S-3", "S-3/A", "S-3ASR", "S-3MEF"),
        category="Shelf Registrations (S-3)",
        product="registry_only",
        supports_obj=False,
    ),
    "MA-I": FilingSpec(
        key="MA-I",
        current_forms=("MA-I", "MA-I/A"),
        category="Municipal Advisors (MA-I)",
        product="registry_only",
    ),
    "CORRESP": FilingSpec(
        key="CORRESP",
        current_forms=("CORRESP",),
        category="SEC Correspondence (CORRESP)",
        product="registry_only",
        supports_obj=False,
    ),
}


def get_filing_spec(form: str) -> FilingSpec | None:
    normalized = form.strip().upper()
    if normalized in FILING_REGISTRY:
        return FILING_REGISTRY[normalized]
    for spec in FILING_REGISTRY.values():
        if normalized in spec.current_forms:
            return spec

    best: FilingSpec | None = None
    best_len = -1
    for spec in FILING_REGISTRY.values():
        for cf in spec.current_forms:
            prefix = cf.split("/")[0].upper()
            if normalized == prefix or normalized.startswith(prefix):
                if len(prefix) > best_len:
                    best = spec
                    best_len = len(prefix)
    return best


def list_registry_forms() -> list[str]:
    return list(FILING_REGISTRY.keys())


def resolve_edgar_enabled_forms(raw: str) -> list[str]:
    """Parse comma-separated form keys; default to full registry when empty."""
    forms = [part.strip() for part in raw.split(",") if part.strip()]
    return forms or list_registry_forms()
