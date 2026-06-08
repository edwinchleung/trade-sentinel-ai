"""Registry for context LLM prompt versions — caps, field parsing, and file paths."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_PROMPT_FILE_PATTERN = re.compile(r"^context_(v\d+)\.txt$")

LATEST_CONTEXT_PROMPT_VERSION = "v10"


@dataclass(frozen=True)
class ContextPromptSpec:
    version: str
    min_bullets: int | None = None
    max_bullets: int | None = None
    qualitative: bool = False
    technical: bool = False
    fundamental: bool = False
    keyed_sections: bool = False
    extends: str | None = None

    @property
    def path(self) -> Path:
        return _PROMPTS_DIR / f"context_{self.version}.txt"


_CONTEXT_PROMPT_REGISTRY: dict[str, ContextPromptSpec] = {
    "v1": ContextPromptSpec(version="v1", min_bullets=3, max_bullets=3),
    "v2": ContextPromptSpec(version="v2", min_bullets=3, max_bullets=5),
    "v3": ContextPromptSpec(version="v3", min_bullets=5, max_bullets=7),
    "v4": ContextPromptSpec(version="v4", min_bullets=6, max_bullets=8),
    "v5": ContextPromptSpec(
        version="v5", min_bullets=6, max_bullets=8, qualitative=True
    ),
    "v6": ContextPromptSpec(
        version="v6", min_bullets=6, max_bullets=8, qualitative=True, technical=True
    ),
    "v7": ContextPromptSpec(
        version="v7",
        min_bullets=6,
        max_bullets=8,
        qualitative=True,
        technical=True,
        fundamental=True,
    ),
    "v8": ContextPromptSpec(
        version="v8",
        min_bullets=6,
        max_bullets=9,
        qualitative=True,
        technical=True,
        fundamental=True,
    ),
    "v9": ContextPromptSpec(version="v9", extends="v8"),
    "v10": ContextPromptSpec(
        version="v10",
        extends="v9",
        min_bullets=9,
        max_bullets=9,
        keyed_sections=True,
    ),
}


def _resolve_chain(version: str, seen: set[str] | None = None) -> ContextPromptSpec:
    seen = seen or set()
    if version in seen:
        raise ValueError(f"Cycle in context prompt inheritance: {version}")
    seen.add(version)

    raw = _CONTEXT_PROMPT_REGISTRY.get(version)
    if raw is None:
        logger.warning(
            "Unknown context prompt version %r — falling back to v1 post-processing",
            version,
        )
        return _resolve_chain("v1", seen)

    if not raw.extends:
        if raw.min_bullets is None or raw.max_bullets is None:
            raise ValueError(f"Prompt spec {version} must set min_bullets and max_bullets")
        return ContextPromptSpec(
            version=raw.version,
            min_bullets=raw.min_bullets,
            max_bullets=raw.max_bullets,
            qualitative=raw.qualitative,
            technical=raw.technical,
            fundamental=raw.fundamental,
            keyed_sections=raw.keyed_sections,
            extends=None,
        )

    parent = _resolve_chain(raw.extends, seen)
    return ContextPromptSpec(
        version=raw.version,
        min_bullets=raw.min_bullets if raw.min_bullets is not None else parent.min_bullets,
        max_bullets=raw.max_bullets if raw.max_bullets is not None else parent.max_bullets,
        qualitative=raw.qualitative or parent.qualitative,
        technical=raw.technical or parent.technical,
        fundamental=raw.fundamental or parent.fundamental,
        keyed_sections=raw.keyed_sections or parent.keyed_sections,
        extends=None,
    )


def resolve_prompt_spec(version: str) -> ContextPromptSpec:
    """Return fully resolved post-processing spec for a prompt version."""
    return _resolve_chain(version)


def prompt_path(version: str) -> Path:
    """Path to the prompt text file for a version."""
    return _PROMPTS_DIR / f"context_{version}.txt"


def list_prompt_files() -> list[str]:
    """Return versions found as context_vN.txt on disk."""
    versions: list[str] = []
    for path in sorted(_PROMPTS_DIR.glob("context_v*.txt")):
        match = _PROMPT_FILE_PATTERN.match(path.name)
        if match:
            versions.append(match.group(1))
    return versions


def validate_prompt_registry() -> None:
    """Raise ValueError if any on-disk prompt file lacks a registry entry."""
    missing = [v for v in list_prompt_files() if v not in _CONTEXT_PROMPT_REGISTRY]
    if missing:
        raise ValueError(
            "Context prompt files without registry entries: "
            + ", ".join(sorted(missing))
            + ". Add them to context_prompt_registry.py."
        )
