"""Unit tests for LLM provider factory (no live API calls)."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from trade_sentinel_api.config import Settings, get_settings
from trade_sentinel_api.services import llm


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings(**kwargs) -> Settings:
    defaults = {
        "openai_api_key": "",
        "anthropic_api_key": "",
        "llm_api_key": "",
        "llm_base_url": "",
        "ollama_base_url": "http://localhost:11434",
        "dashscope_api_key": "",
        "llm_provider": "openrouter",
        "llm_model": "",
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def test_openrouter_returns_chat_openai_with_default_base():
    s = _settings(llm_provider="openrouter", llm_api_key="sk-test")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        model = llm._get_chat_model()
    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.model_name == "openai/gpt-4o-mini"


def test_openrouter_missing_key_returns_none():
    s = _settings(llm_provider="openrouter", llm_api_key="")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        assert llm._get_chat_model() is None


def test_openrouter_falls_back_to_openai_api_key():
    s = _settings(llm_provider="openrouter", openai_api_key="sk-legacy")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        model = llm._get_chat_model()
    assert isinstance(model, ChatOpenAI)


def test_openai_compatible_custom_base_url():
    s = _settings(
        llm_provider="openai_compatible",
        llm_api_key="sk-test",
        llm_base_url="https://api.deepseek.com",
        llm_model="deepseek-chat",
    )
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        model = llm._get_chat_model()
    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "https://api.deepseek.com"
    assert model.model_name == "deepseek-chat"


def test_ollama_returns_chat_ollama_without_api_key():
    s = _settings(llm_provider="ollama", llm_model="mistral")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        model = llm._get_chat_model()
    assert isinstance(model, ChatOllama)
    assert model.model == "mistral"


def test_dashscope_returns_chat_openai_compatible():
    s = _settings(llm_provider="dashscope", dashscope_api_key="sk-ds")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        model = llm._get_chat_model()
    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert model.model_name == "qwen-plus"


def test_dashscope_missing_key_returns_none():
    s = _settings(llm_provider="dashscope", dashscope_api_key="")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        assert llm._get_chat_model() is None


def test_anthropic_requires_anthropic_key():
    s = _settings(llm_provider="anthropic", anthropic_api_key="sk-ant")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        model = llm._get_chat_model()
    assert isinstance(model, ChatAnthropic)


def test_openai_does_not_use_anthropic_key_when_provider_openai():
    s = _settings(llm_provider="openai", openai_api_key="", anthropic_api_key="sk-ant")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        assert llm._get_chat_model() is None


def test_effective_base_url_openrouter_default():
    s = _settings(llm_provider="openrouter")
    assert s.effective_base_url() == "https://openrouter.ai/api/v1"


def test_effective_base_url_respects_override():
    s = _settings(llm_base_url="https://custom.example/v1")
    assert s.effective_base_url("openrouter") == "https://custom.example/v1"


def test_is_stale_llm_summary_legacy_bullets():
    assert llm.is_stale_llm_summary(
        {"bullets": ["LLM API key not configured — enable OPENAI_API_KEY or ANTHROPIC_API_KEY."]}
    )


def test_is_stale_llm_summary_unconfigured_when_now_configured():
    s = _settings(llm_provider="openrouter", llm_api_key="sk-test")
    with patch("trade_sentinel_api.services.llm.get_settings", return_value=s):
        assert llm.is_stale_llm_summary(
            {"bullets": ["a", "b", "c"], "data_gaps": ["llm_unconfigured"]}
        )


def test_is_stale_llm_summary_fresh_summary_not_stale():
    assert not llm.is_stale_llm_summary({"bullets": ["a", "b", "c"], "model": "openrouter:x"})


@pytest.mark.asyncio
async def test_summarize_context_v5_parses_section_labels():
    labels = [
        {"stance": "caution", "headline": "Rich vs model fair band"},
        {"stance": "neutral", "headline": "Mixed macro backdrop"},
    ]
    bullets = [f"Bullet {i}" for i in range(1, 7)]
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Growth story with valuation risk.",
                    "section_labels": labels,
                    "bullets": bullets,
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v5")

    assert summary is not None
    assert len(summary.section_labels) == 6
    assert summary.section_labels[0].stance == "caution"
    assert summary.section_labels[0].headline == "Rich vs model fair band"
    assert summary.section_labels[1].headline == "Mixed macro backdrop"
    assert summary.section_labels[5].stance == "unavailable"
    assert summary.section_labels[5].headline == "Data Unavailable"


@pytest.mark.asyncio
async def test_summarize_context_v5_parses_qualitative_analysis():
    qual = "As a semiconductor leader, growth remains the core narrative with elevated valuation risk."
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": qual,
                    "bullets": [f"Bullet {i}" for i in range(1, 7)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v5")

    assert summary is not None
    assert summary.qualitative_analysis == qual


@pytest.mark.asyncio
async def test_summarize_context_v5_fallback_qualitative_when_missing():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=({"bullets": [f"Bullet {i}" for i in range(1, 7)], "data_gaps": []}, "test-model", None),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v5")

    assert summary is not None
    assert summary.qualitative_analysis == "Data Unavailable for qualitative narrative."


@pytest.mark.asyncio
async def test_summarize_context_v5_keeps_up_to_eight_bullets():
    eight_bullets = [f"Bullet {i}" for i in range(1, 9)]
    mock_model = object()
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=mock_model),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=({"bullets": eight_bullets, "data_gaps": []}, "test-model", None),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v5")

    assert summary is not None
    assert len(summary.bullets) == 8
    assert summary.bullets == eight_bullets


@pytest.mark.asyncio
async def test_summarize_context_v5_pads_to_six_bullets_minimum():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=({"bullets": ["Only one"], "data_gaps": []}, "test-model", None),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v5")

    assert summary is not None
    assert len(summary.bullets) == 6
    assert summary.bullets[0] == "Only one"
    assert summary.bullets[-1] == "Data Unavailable"


def test_plain_text_bullet_strips_markdown():
    assert llm._plain_text_bullet("**Valuation** — rich vs mid") == "Valuation — rich vs mid"
    assert llm._plain_text_bullet("use `code` here") == "use code here"


@pytest.mark.asyncio
async def test_summarize_context_strips_markdown_from_bullets():
    bullets_with_md = ["**Valuation & fair-value band** — Technology sector."]
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=({"bullets": bullets_with_md, "data_gaps": []}, "test-model", None),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v5")

    assert summary is not None
    assert "**" not in summary.bullets[0]
    assert summary.bullets[0].startswith("Valuation & fair-value band")


@pytest.mark.asyncio
async def test_summarize_context_v6_parses_technical_interpretation():
    tech = "Price holds above moving averages with bullish trend but bearish divergence warns of fading momentum."
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Growth story with valuation risk.",
                    "technical_interpretation": tech,
                    "section_labels": [{"stance": "favorable", "headline": "Bullish trend intact"}],
                    "bullets": [f"Bullet {i}" for i in range(1, 7)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v6")

    assert summary is not None
    assert summary.technical_interpretation == tech
    assert summary.qualitative_analysis is not None


@pytest.mark.asyncio
async def test_summarize_context_v6_fallback_technical_when_missing():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Story.",
                    "bullets": [f"Bullet {i}" for i in range(1, 7)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v6")

    assert summary is not None
    assert summary.technical_interpretation == "Data Unavailable for technical narrative."


@pytest.mark.asyncio
async def test_summarize_context_v7_parses_extended_fields():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Story.",
                    "technical_interpretation": "Tape is mixed.",
                    "fundamental_interpretation": "Quality is strong.",
                    "reality_check_narrative": "Constructive bias with risks.",
                    "scenario_bullets": ["Bull: holds support", "Base: range bound", "Bear: breaks support"],
                    "section_labels": [{"stance": "neutral", "headline": "Mixed signals"}],
                    "bullets": [f"Bullet {i}" for i in range(1, 7)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context(
            {"ticker": "NVDA", "reality_check": {"headline": "Fallback headline"}},
            prompt_version="v7",
        )

    assert summary is not None
    assert summary.fundamental_interpretation == "Quality is strong."
    assert summary.reality_check_narrative == "Constructive bias with risks."
    assert len(summary.scenario_bullets) == 3


def test_load_system_prompt_v8():
    text = llm._load_system_prompt("v8")
    assert "sector_context" in text
    assert "benchmark_quantiles" in text


@pytest.mark.asyncio
async def test_summarize_context_v8_keeps_up_to_nine_bullets():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Story.",
                    "technical_interpretation": "Tape.",
                    "fundamental_interpretation": "Fundamentals.",
                    "reality_check_narrative": "Reality.",
                    "scenario_bullets": ["Bull: up", "Base: flat", "Bear: down"],
                    "section_labels": [{"stance": "neutral", "headline": "Mixed"}] * 9,
                    "bullets": [f"Bullet {i}" for i in range(1, 10)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v8")

    assert summary is not None
    assert len(summary.bullets) == 9
    assert summary.fundamental_interpretation == "Fundamentals."


@pytest.mark.asyncio
async def test_summarize_context_v8_not_capped_to_three_bullets():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "bullets": [f"B{i}" for i in range(8)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "X"}, prompt_version="v8")

    assert summary is not None
    assert len(summary.bullets) == 8


@pytest.mark.asyncio
async def test_summarize_context_v9_keeps_up_to_nine_bullets():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Story.",
                    "technical_interpretation": "Tape.",
                    "fundamental_interpretation": "Fundamentals.",
                    "reality_check_narrative": "Reality.",
                    "scenario_bullets": ["Bull: up", "Base: flat", "Bear: down"],
                    "section_labels": [{"stance": "neutral", "headline": "Mixed"}] * 9,
                    "bullets": [f"Bullet {i}" for i in range(1, 10)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v9")

    assert summary is not None
    assert len(summary.bullets) == 9
    assert summary.fundamental_interpretation == "Fundamentals."
    assert summary.qualitative_analysis == "Story."


@pytest.mark.asyncio
async def test_summarize_context_v9_not_capped_to_three_bullets():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "bullets": [f"B{i}" for i in range(8)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "X"}, prompt_version="v9")

    assert summary is not None
    assert len(summary.bullets) == 8


@pytest.mark.asyncio
async def test_summarize_context_v9_parses_extended_fields():
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Qual narrative.",
                    "technical_interpretation": "Tech narrative.",
                    "fundamental_interpretation": "Fund narrative.",
                    "reality_check_narrative": "RC narrative.",
                    "scenario_bullets": ["Bull: a", "Base: b", "Bear: c"],
                    "section_labels": [{"stance": "favorable", "headline": "Strong growth"}] * 6,
                    "bullets": [f"Bullet {i}" for i in range(1, 7)],
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v9")

    assert summary is not None
    assert summary.qualitative_analysis == "Qual narrative."
    assert summary.technical_interpretation == "Tech narrative."
    assert len(summary.scenario_bullets) == 3
    assert len(summary.section_labels) == 6


def _v10_section_bullets(**overrides: str) -> dict[str, str]:
    base = {key: f"{key} narrative" for key in llm.SECTION_ORDER}
    base.update(overrides)
    return base


def _v10_section_labels() -> dict[str, dict[str, str]]:
    return {
        key: {"stance": "neutral", "headline": f"{key} headline"}
        for key in llm.SECTION_ORDER
    }


@pytest.mark.asyncio
async def test_summarize_context_v10_parses_keyed_section_bullets():
    section_bullets = _v10_section_bullets(sector="Sector peer narrative")
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Qual narrative.",
                    "technical_interpretation": "Tech narrative.",
                    "fundamental_interpretation": "Fund narrative.",
                    "reality_check_narrative": "RC narrative.",
                    "scenario_bullets": ["Bull: a", "Base: b", "Bear: c"],
                    "section_bullets": section_bullets,
                    "section_labels": _v10_section_labels(),
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v10")

    assert summary is not None
    assert summary.section_bullets is not None
    assert summary.section_bullets["sector"] == "Sector peer narrative"
    assert len(summary.bullets) == 9
    assert summary.bullets[2] == "Sector peer narrative"
    assert len(summary.section_labels) == 9
    assert summary.section_labels[2].headline == "sector headline"


@pytest.mark.asyncio
async def test_summarize_context_v10_fills_missing_section_keys():
    partial = _v10_section_bullets()
    del partial["forward"]
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Qual.",
                    "technical_interpretation": "Tech.",
                    "fundamental_interpretation": "Fund.",
                    "reality_check_narrative": "RC.",
                    "scenario_bullets": ["Bull: a", "Base: b", "Bear: c"],
                    "section_bullets": partial,
                    "section_labels": _v10_section_labels(),
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v10")

    assert summary is not None
    assert summary.section_bullets is not None
    assert summary.section_bullets["forward"] == llm._SECTION_UNAVAILABLE


@pytest.mark.asyncio
async def test_summarize_context_v10_legacy_bullets_fallback():
    legacy = [f"Legacy {i}" for i in range(8)]
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=object()),
        patch(
            "trade_sentinel_api.services.llm._invoke_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "qualitative_analysis": "Qual.",
                    "technical_interpretation": "Tech.",
                    "fundamental_interpretation": "Fund.",
                    "reality_check_narrative": "RC.",
                    "scenario_bullets": ["Bull: a", "Base: b", "Bear: c"],
                    "bullets": legacy,
                    "section_labels": [{"stance": "neutral", "headline": "H"}] * 8,
                    "data_gaps": [],
                },
                "test-model",
                None,
            ),
        ),
    ):
        summary = await llm.summarize_context({"ticker": "NVDA"}, prompt_version="v10")

    assert summary is not None
    assert summary.section_bullets is not None
    assert summary.section_bullets["sector"] == "Legacy 2"
    assert summary.section_bullets["growth"] == "Legacy 3"
    assert summary.section_bullets["forward"] == llm._SECTION_UNAVAILABLE


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_classify_llm_error_openrouter_502_dict_message():
    exc = Exception("{'message': 'Provider returned error', 'code': 502}")
    assert llm._classify_llm_error(exc) == "llm_provider_down"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, "llm_bad_request"),
        (401, "llm_auth_error"),
        (402, "llm_insufficient_credits"),
        (403, "llm_forbidden"),
        (408, "llm_timeout"),
        (429, "llm_rate_limited"),
        (502, "llm_provider_down"),
        (503, "llm_no_provider"),
        (504, "llm_timeout"),
    ],
)
def test_classify_llm_error_by_http_status(status, expected):
    exc = Exception("upstream failure")
    exc.status_code = status  # type: ignore[attr-defined]
    assert llm._classify_llm_error(exc) == expected


def test_error_bullets_provider_down_mentions_502():
    bullets = llm._error_bullets("llm_provider_down")
    assert any("502" in b for b in bullets)


@pytest.mark.asyncio
async def test_invoke_llm_retries_on_502_then_succeeds():
    from langchain_core.messages import AIMessage

    class FakeModel:
        def __init__(self):
            self.call_count = 0

        async def ainvoke(self, _messages):
            self.call_count += 1
            if self.call_count < 2:
                raise Exception("{'message': 'Provider returned error', 'code': 502}")
            return AIMessage(content='{"bullets": ["a", "b", "c"], "data_gaps": []}')

    fake = FakeModel()
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=fake),
        patch("trade_sentinel_api.services.llm.get_settings", return_value=_settings()),
        patch("trade_sentinel_api.services.llm.asyncio.sleep", new_callable=AsyncMock),
    ):
        parsed, _model, err = await llm._invoke_llm("system", {"ticker": "X"})

    assert err is None
    assert parsed is not None
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_invoke_llm_does_not_retry_auth_errors():
    class FakeModel:
        def __init__(self):
            self.call_count = 0

        async def ainvoke(self, _messages):
            self.call_count += 1
            exc = Exception("Unauthorized")
            exc.status_code = 401  # type: ignore[attr-defined]
            raise exc

    fake = FakeModel()
    with (
        patch("trade_sentinel_api.services.llm._get_chat_model", return_value=fake),
        patch("trade_sentinel_api.services.llm.get_settings", return_value=_settings()),
        patch("trade_sentinel_api.services.llm.asyncio.sleep", new_callable=AsyncMock),
    ):
        parsed, _model, err = await llm._invoke_llm("system", {"ticker": "X"})

    assert parsed is None
    assert err == "llm_auth_error"
    assert fake.call_count == 1
