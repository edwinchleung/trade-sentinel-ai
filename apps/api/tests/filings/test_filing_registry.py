"""Filing registry coverage tests."""

from trade_sentinel_api.services.sec.registry import FILING_REGISTRY, get_filing_spec


def test_registry_has_expected_product_forms():
    keys = set(FILING_REGISTRY)
    assert "4" in keys
    assert "13F-HR" in keys
    assert "SC 13D" in keys
    assert "8-K" in keys
    assert "NPORT-P" in keys


def test_get_filing_spec_resolves_aliases():
    spec = get_filing_spec("4")
    assert spec is not None
    assert spec.key == "4"
    assert spec.product == "insider_feed"

    spec_424 = get_filing_spec("424B2")
    assert spec_424 is not None
    assert spec_424.key == "424B"


def test_all_registry_specs_have_current_forms():
    for key, spec in FILING_REGISTRY.items():
        assert spec.key == key
        assert spec.current_forms
        assert spec.category
        assert spec.product in {
            "insider_feed",
            "institutional",
            "activist",
            "events",
            "registry_only",
        }


def test_resolve_edgar_enabled_forms_defaults_to_registry():
    from trade_sentinel_api.services.sec.registry import resolve_edgar_enabled_forms

    forms = resolve_edgar_enabled_forms("")
    assert "4" in forms
    assert "NPORT-P" in forms


def test_resolve_edgar_enabled_forms_parses_csv():
    from trade_sentinel_api.services.sec.registry import resolve_edgar_enabled_forms

    forms = resolve_edgar_enabled_forms("8-K, NPORT-P")
    assert forms == ["8-K", "NPORT-P"]
