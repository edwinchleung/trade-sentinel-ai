"""Guard tests for context prompt version registry."""

import logging

from trade_sentinel_api.services.context_prompt_registry import (
    LATEST_CONTEXT_PROMPT_VERSION,
    resolve_prompt_spec,
    validate_prompt_registry,
)


def test_every_prompt_file_has_registry_entry():
    validate_prompt_registry()


def test_latest_prompt_not_capped_to_three_bullets():
    spec = resolve_prompt_spec(LATEST_CONTEXT_PROMPT_VERSION)
    assert spec.max_bullets is not None
    assert spec.max_bullets >= 6


def test_v9_inherits_v8_capabilities():
    spec = resolve_prompt_spec("v9")
    assert spec.min_bullets == 6
    assert spec.max_bullets == 9
    assert spec.qualitative is True
    assert spec.technical is True
    assert spec.fundamental is True


def test_v10_keyed_sections_nine_bullets():
    spec = resolve_prompt_spec("v10")
    assert spec.min_bullets == 9
    assert spec.max_bullets == 9
    assert spec.keyed_sections is True
    assert spec.qualitative is True
    assert spec.technical is True
    assert spec.fundamental is True


def test_latest_prompt_is_v10():
    spec = resolve_prompt_spec(LATEST_CONTEXT_PROMPT_VERSION)
    assert LATEST_CONTEXT_PROMPT_VERSION == "v10"
    assert spec.keyed_sections is True


def test_unknown_version_logs_and_falls_back(caplog):
    with caplog.at_level(logging.WARNING):
        spec = resolve_prompt_spec("v99")
    assert spec.min_bullets == 3
    assert spec.max_bullets == 3
    assert any("v99" in r.message for r in caplog.records)
