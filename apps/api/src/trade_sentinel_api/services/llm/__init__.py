import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from trade_sentinel_api.config import Settings, get_settings
from trade_sentinel_api.models.schemas import ContextSectionLabel, ContextSummary, MacroSummary
from trade_sentinel_api.services.context_prompt_registry import (
    prompt_path,
    resolve_prompt_spec,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts" / "context_v1.txt"
_MACRO_PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts" / "macro_v2.txt"
_MACRO_PROMPT_V1_PATH = Path(__file__).resolve().parents[4] / "prompts" / "macro_v1.txt"
_OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini"
_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
_ANTHROPIC_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_OLLAMA_DEFAULT_MODEL = "llama3.2"
_DASHSCOPE_DEFAULT_MODEL = "qwen-plus"

_UNCONFIGURED_BULLETS = [
    "LLM not configured — set credentials in .env for your provider.",
    "Hong Kong: use LLM_PROVIDER=openrouter with LLM_API_KEY, or ollama / dashscope.",
    "Raw market data is still available below.",
]


def _load_system_prompt(version: str = "v1") -> str:
    path = prompt_path(version)
    if path.exists():
        return path.read_text(encoding="utf-8")
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return "Summarize ticker context in 3 bullets using only provided JSON."


def _load_macro_prompt() -> str:
    if _MACRO_PROMPT_PATH.exists():
        return _MACRO_PROMPT_PATH.read_text(encoding="utf-8")
    if _MACRO_PROMPT_V1_PATH.exists():
        return _MACRO_PROMPT_V1_PATH.read_text(encoding="utf-8")
    return "Summarize macro events using only provided JSON."


def _normalize_content(content) -> str:
    """Coerce LangChain message content (str or block list) to plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(block, "text", None) or getattr(block, "content", None)
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip()


def _plain_text_bullet(text: str) -> str:
    s = text.strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.strip()


_VALID_STANCES = frozenset({"favorable", "neutral", "caution", "unavailable"})

SECTION_ORDER = (
    "valuation",
    "macro",
    "sector",
    "growth",
    "balance_sheet",
    "catalysts",
    "insider_options",
    "technical",
    "forward",
)
_SECTION_UNAVAILABLE = "Data unavailable for this section."


def _parse_section_labels(raw: object, *, bullet_count: int) -> list[ContextSectionLabel]:
    labels: list[ContextSectionLabel] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            stance = str(item.get("stance", "unavailable")).lower().strip()
            if stance not in _VALID_STANCES:
                stance = "unavailable"
            headline = _plain_text_bullet(str(item.get("headline", "")))
            if not headline:
                headline = "Data Unavailable"
            labels.append(
                ContextSectionLabel(
                    stance=cast(Literal["favorable", "neutral", "caution", "unavailable"], stance),
                    headline=headline,
                )
            )
    while len(labels) < bullet_count:
        labels.append(
            ContextSectionLabel(stance="unavailable", headline="Data Unavailable")
        )
    return labels[:bullet_count]


def _missing_section_keys(raw: object) -> list[str]:
    if not isinstance(raw, dict):
        return list(SECTION_ORDER)
    missing: list[str] = []
    for key in SECTION_ORDER:
        val = raw.get(key)
        if val is None or not str(val).strip():
            missing.append(key)
    return missing


def _parse_section_bullets(raw_keyed: object, raw_legacy: object) -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(raw_keyed, dict):
        for key in SECTION_ORDER:
            val = raw_keyed.get(key)
            if val is not None and str(val).strip():
                result[key] = _plain_text_bullet(str(val))
            else:
                result[key] = _SECTION_UNAVAILABLE
        return result

    if isinstance(raw_legacy, list) and raw_legacy:
        logger.warning("LLM returned legacy bullets array — mapping positionally to section ids")
        for idx, key in enumerate(SECTION_ORDER):
            if idx < len(raw_legacy) and raw_legacy[idx] is not None:
                result[key] = _plain_text_bullet(str(raw_legacy[idx]))
            else:
                result[key] = _SECTION_UNAVAILABLE
        return result

    return {key: _SECTION_UNAVAILABLE for key in SECTION_ORDER}


def _bullets_from_section_dict(section_bullets: dict[str, str]) -> list[str]:
    return [section_bullets.get(key, _SECTION_UNAVAILABLE) for key in SECTION_ORDER]


def _parse_section_labels_keyed(
    raw: object,
    section_bullets: dict[str, str],
) -> dict[str, ContextSectionLabel]:
    labels: dict[str, ContextSectionLabel] = {}
    if isinstance(raw, dict):
        for key in SECTION_ORDER:
            item = raw.get(key)
            if isinstance(item, dict):
                stance = str(item.get("stance", "unavailable")).lower().strip()
                if stance not in _VALID_STANCES:
                    stance = "unavailable"
                headline = _plain_text_bullet(str(item.get("headline", "")))
                if not headline:
                    headline = "Data unavailable"
                labels[key] = ContextSectionLabel(
                    stance=cast(Literal["favorable", "neutral", "caution", "unavailable"], stance),
                    headline=headline,
                )
            else:
                labels[key] = ContextSectionLabel(stance="unavailable", headline="Data unavailable")
        return labels

    return {
        key: ContextSectionLabel(
            stance="unavailable",
            headline="Data unavailable"
            if section_bullets.get(key) == _SECTION_UNAVAILABLE
            else "Section summary",
        )
        for key in SECTION_ORDER
    }


def _section_labels_list_from_keyed(labels: dict[str, ContextSectionLabel]) -> list[ContextSectionLabel]:
    return [labels.get(key, ContextSectionLabel(stance="unavailable", headline="Data unavailable")) for key in SECTION_ORDER]


def _extract_json_from_text(text: str) -> dict:
    """Parse JSON from LLM output, tolerating markdown fences and leading prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned.split("\n", 1)[-1].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # First {...} block in the response
    start = cleaned.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start : i + 1])

    # Fallback: bullets array only
    match = re.search(r'"bullets"\s*:\s*(\[[\s\S]*?\])', cleaned)
    if match:
        bullets = json.loads(match.group(1))
        gaps_match = re.search(r'"data_gaps"\s*:\s*(\[[\s\S]*?\])', cleaned)
        data_gaps = json.loads(gaps_match.group(1)) if gaps_match else []
        return {"bullets": bullets, "data_gaps": data_gaps}

    raise json.JSONDecodeError("No JSON object found", cleaned, 0)


# OpenRouter / compatible gateway HTTP status → internal data_gaps code
_HTTP_STATUS_TO_LLM_CODE: dict[int, str] = {
    400: "llm_bad_request",
    401: "llm_auth_error",
    402: "llm_insufficient_credits",
    403: "llm_forbidden",
    408: "llm_timeout",
    429: "llm_rate_limited",
    502: "llm_provider_down",
    503: "llm_no_provider",
    504: "llm_timeout",
}

_RETRYABLE_LLM_CODES = frozenset(
    {"llm_rate_limited", "llm_provider_down", "llm_no_provider", "llm_timeout"}
)

_LLM_INVOKE_MAX_ATTEMPTS = 3

_STALE_LLM_GAP_CODES = frozenset(
    {
        "llm_parse_error",
        "llm_api_error",
        "llm_bad_request",
        "llm_auth_error",
        "llm_insufficient_credits",
        "llm_forbidden",
        "llm_rate_limited",
        "llm_timeout",
        "llm_provider_down",
        "llm_no_provider",
    }
)


def _iter_exception_chain(exc: BaseException):
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        cur = cur.__cause__ or cur.__context__


def _status_from_exception(exc: BaseException) -> int | None:
    for node in _iter_exception_chain(exc):
        for attr in ("status_code", "status"):
            val = getattr(node, attr, None)
            if isinstance(val, int) and 100 <= val < 600:
                return val
        response = getattr(node, "response", None)
        if response is not None:
            sc = getattr(response, "status_code", None)
            if isinstance(sc, int) and 100 <= sc < 600:
                return sc
        code = getattr(node, "code", None)
        if isinstance(code, int) and 100 <= code < 600:
            return code
    text = str(exc)
    m = re.search(r"""['"]code['"]\s*:\s*(\d{3})""", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\bstatus(?:_code)?\s*[=:]\s*(\d{3})\b", text, re.I)
    if m:
        return int(m.group(1))
    return None


def _provider_message_from_exception(exc: BaseException) -> str | None:
    text = str(exc)
    m = re.search(r"""['"]message['"]\s*:\s*['"]([^'"]+)['"]""", text)
    if m:
        return m.group(1).strip()
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        msg = body.get("message") or body.get("error")
        if msg:
            return str(msg).strip()
    return None


def _classify_llm_error(exc: Exception) -> str:
    status = _status_from_exception(exc)
    if status is not None:
        return _HTTP_STATUS_TO_LLM_CODE.get(status, "llm_api_error")

    msg = str(exc).lower()
    if "429" in msg or ("rate" in msg and "limit" in msg):
        return "llm_rate_limited"
    if "402" in msg or "insufficient credit" in msg or "insufficient quota" in msg:
        return "llm_insufficient_credits"
    if "401" in msg or "invalid api key" in msg or "unauthorized" in msg:
        return "llm_auth_error"
    if "403" in msg or "forbidden" in msg or "moderation" in msg:
        return "llm_forbidden"
    if "502" in msg or "provider returned error" in msg:
        return "llm_provider_down"
    if "503" in msg or "no available model provider" in msg:
        return "llm_no_provider"
    if "408" in msg or "timeout" in msg or "timed out" in msg:
        return "llm_timeout"
    if "400" in msg or "bad request" in msg:
        return "llm_bad_request"
    return "llm_api_error"


def _format_llm_invoke_log(exc: Exception, err_code: str) -> str:
    status = _status_from_exception(exc)
    detail = _provider_message_from_exception(exc)
    parts = [f"code={err_code}"]
    if status is not None:
        parts.append(f"http={status}")
    if detail:
        parts.append(f"message={detail!r}")
    else:
        parts.append(f"exc={exc!r}")
    return " ".join(parts)


def _error_bullets(err: str) -> list[str]:
    if err == "llm_rate_limited":
        return [
            "LLM rate limited (429) — too many requests to the provider.",
            "Wait a minute and retry, or switch to a paid model in LLM_MODEL.",
            "Raw market data below is still current.",
        ]
    if err == "llm_auth_error":
        return [
            "LLM authentication failed (401) — invalid or expired API key.",
            "Check LLM_API_KEY in .env and see docs/llm-providers.md.",
            "Refer to raw market data below.",
        ]
    if err == "llm_insufficient_credits":
        return [
            "LLM account has insufficient credits (402).",
            "Add credits at your provider dashboard, then retry.",
            "Refer to raw market data below.",
        ]
    if err == "llm_forbidden":
        return [
            "LLM request forbidden (403) — permissions, guardrail, or moderation block.",
            "Try a different model in LLM_MODEL or review provider account settings.",
            "Refer to raw market data below.",
        ]
    if err == "llm_timeout":
        return [
            "LLM request timed out (408/504) — model or gateway was too slow.",
            "Retry shortly or pick a faster model in LLM_MODEL.",
            "Refer to raw market data below.",
        ]
    if err == "llm_provider_down":
        return [
            "LLM provider error (502) — chosen model is down or returned an invalid response.",
            "Retry in a moment or set LLM_MODEL to a stable route (e.g. openai/gpt-4o-mini).",
            "Refer to raw market data below.",
        ]
    if err == "llm_no_provider":
        return [
            "No LLM provider available (503) — routing rules could not match a model.",
            "Change LLM_MODEL or provider settings in .env and retry.",
            "Refer to raw market data below.",
        ]
    if err == "llm_bad_request":
        return [
            "LLM bad request (400) — invalid parameters or CORS-related gateway rejection.",
            "Verify LLM_MODEL and base URL in .env match your provider docs.",
            "Refer to raw market data below.",
        ]
    if err == "llm_parse_error":
        return [
            "AI summary could not be parsed — refer to raw data below.",
            "Data Unavailable for automated narrative.",
            "Retry or try LLM_MODEL=openai/gpt-4o-mini in .env.",
        ]
    return [
        "LLM request failed — check API key, credits, and model availability.",
        "Refer to raw market data below.",
        "Retry in a moment or try a different LLM_MODEL in .env.",
    ]


async def _invoke_llm(
    system: str,
    facts: dict,
    *,
    follow_up: str | None = None,
) -> tuple[dict | None, str, str | None]:
    """Invoke LLM and return parsed JSON, model name, and optional error code."""
    model = _get_chat_model()
    if model is None:
        return None, "none", "llm_unconfigured"
    settings = get_settings()
    human = json.dumps(facts, indent=2, default=str)
    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    if follow_up:
        messages.append(HumanMessage(content=follow_up))

    last_err: str | None = None
    for attempt in range(_LLM_INVOKE_MAX_ATTEMPTS):
        try:
            response = await model.ainvoke(messages)
            text = _normalize_content(response.content)
            parsed = _extract_json_from_text(text)
            return parsed, _display_model(settings), None
        except json.JSONDecodeError as exc:
            logger.warning("LLM JSON parse failed: %s", exc)
            return None, _display_model(settings), "llm_parse_error"
        except Exception as exc:
            last_err = _classify_llm_error(exc)
            logger.warning(
                "LLM invoke failed (attempt %s/%s): %s",
                attempt + 1,
                _LLM_INVOKE_MAX_ATTEMPTS,
                _format_llm_invoke_log(exc, last_err),
            )
            if last_err in _RETRYABLE_LLM_CODES and attempt < _LLM_INVOKE_MAX_ATTEMPTS - 1:
                await asyncio.sleep(2**attempt)
                continue
            return None, _display_model(settings), last_err

    return None, _display_model(settings), last_err


async def summarize_context(facts: dict, *, prompt_version: str = "v1") -> ContextSummary | None:
    model = _get_chat_model()
    if model is None:
        return ContextSummary(
            bullets=_UNCONFIGURED_BULLETS,
            model="none",
            data_gaps=["llm_unconfigured"],
        )

    system = _load_system_prompt(prompt_version)
    spec = resolve_prompt_spec(prompt_version)
    parsed, model_name, err = await _invoke_llm(system, facts)

    if parsed is not None and spec.keyed_sections:
        raw_keyed = parsed.get("section_bullets")
        legacy_bullets = parsed.get("bullets")
        if isinstance(raw_keyed, dict):
            missing = _missing_section_keys(raw_keyed)
            if missing:
                correction = (
                    "Your response omitted required section_bullets keys: "
                    + ", ".join(missing)
                    + ". Return complete JSON per schema with all 9 section_bullets and section_labels keys."
                )
                parsed_retry, model_retry, err_retry = await _invoke_llm(
                    system, facts, follow_up=correction
                )
                if parsed_retry is not None:
                    parsed = parsed_retry
                    model_name = model_retry
                    err = err_retry
        elif not legacy_bullets:
            correction = (
                "Your response must include section_bullets with all 9 keys. "
                "Return complete JSON per schema."
            )
            parsed_retry, model_retry, err_retry = await _invoke_llm(
                system, facts, follow_up=correction
            )
            if parsed_retry is not None:
                parsed = parsed_retry
                model_name = model_retry
                err = err_retry

    if parsed is None:
        return ContextSummary(
            bullets=_error_bullets(err or "llm_parse_error"),
            model=model_name,
            data_gaps=[err or "llm_parse_error"],
        )

    section_bullets_dict: dict[str, str] | None = None
    if spec.keyed_sections:
        section_bullets_dict = _parse_section_bullets(
            parsed.get("section_bullets"),
            parsed.get("bullets"),
        )
        bullets = _bullets_from_section_dict(section_bullets_dict)
    else:
        bullets = parsed.get("bullets", [])
        bullets = [_plain_text_bullet(str(b)) for b in bullets if b is not None]
        min_bullets = spec.min_bullets or 3
        max_bullets = spec.max_bullets or 3
        if len(bullets) < min_bullets:
            while len(bullets) < min_bullets:
                bullets.append("Data Unavailable")
        bullets = bullets[:max_bullets]

    qualitative_analysis: str | None = None
    technical_interpretation: str | None = None
    fundamental_interpretation: str | None = None
    reality_check_narrative: str | None = None
    scenario_bullets: list[str] = []
    section_labels: list[ContextSectionLabel] = []
    if spec.qualitative:
        raw_qual = parsed.get("qualitative_analysis")
        if raw_qual is not None and str(raw_qual).strip():
            qualitative_analysis = _plain_text_bullet(str(raw_qual))
        else:
            qualitative_analysis = "Data Unavailable for qualitative narrative."
        if spec.keyed_sections and section_bullets_dict is not None:
            keyed_labels = _parse_section_labels_keyed(
                parsed.get("section_labels"),
                section_bullets_dict,
            )
            section_labels = _section_labels_list_from_keyed(keyed_labels)
        else:
            section_labels = _parse_section_labels(
                parsed.get("section_labels"), bullet_count=len(bullets)
            )
    if spec.technical:
        raw_tech = parsed.get("technical_interpretation")
        if raw_tech is not None and str(raw_tech).strip():
            technical_interpretation = _plain_text_bullet(str(raw_tech))
        else:
            technical_interpretation = "Data Unavailable for technical narrative."
    if spec.fundamental:
        raw_fund = parsed.get("fundamental_interpretation")
        if raw_fund is not None and str(raw_fund).strip():
            fundamental_interpretation = _plain_text_bullet(str(raw_fund))
        else:
            fundamental_interpretation = "Data Unavailable for fundamental narrative."
        raw_rc = parsed.get("reality_check_narrative")
        if raw_rc is not None and str(raw_rc).strip():
            reality_check_narrative = _plain_text_bullet(str(raw_rc))
        elif isinstance(facts.get("reality_check"), dict) and facts["reality_check"].get("headline"):
            reality_check_narrative = str(facts["reality_check"]["headline"])
        else:
            reality_check_narrative = "Data Unavailable for reality check narrative."
        raw_scenarios = parsed.get("scenario_bullets")
        if isinstance(raw_scenarios, list):
            scenario_bullets = [
                _plain_text_bullet(str(s)) for s in raw_scenarios[:3] if s is not None
            ]
        while len(scenario_bullets) < 3:
            scenario_bullets.append("Data Unavailable for scenario framing.")

    return ContextSummary(
        bullets=bullets,
        section_bullets=section_bullets_dict,
        qualitative_analysis=qualitative_analysis,
        technical_interpretation=technical_interpretation,
        fundamental_interpretation=fundamental_interpretation,
        reality_check_narrative=reality_check_narrative,
        scenario_bullets=scenario_bullets,
        section_labels=section_labels,
        model=model_name,
        cached_at=datetime.now(UTC),
        data_gaps=parsed.get("data_gaps", []),
    )


async def summarize_macro(facts: dict) -> tuple[MacroSummary | None, dict]:
    """Return MacroSummary and structured fields from LLM."""
    model = _get_chat_model()
    empty_structured = {
        "market_weather": None,
        "headline_events": [],
        "sector_watch": [],
        "watchlist_exposure": [],
        "event_playbooks": [],
        "signal_highlights": [],
    }
    if model is None:
        return (
            MacroSummary(
                bullets=_UNCONFIGURED_BULLETS,
                model="none",
                data_gaps=["llm_unconfigured"],
            ),
            empty_structured,
        )

    system = _load_macro_prompt()
    parsed, model_name, err = await _invoke_llm(system, facts)

    if parsed is None:
        return (
            MacroSummary(
                bullets=_error_bullets(err or "llm_parse_error"),
                model=model_name,
                data_gaps=[err or "llm_parse_error"],
            ),
            empty_structured,
        )

    bullets = parsed.get("bullets", [])
    if len(bullets) < 3:
        while len(bullets) < 3:
            bullets.append("Data Unavailable")
    bullets = bullets[:5]

    structured = {
        "market_weather": parsed.get("market_weather"),
        "headline_events": parsed.get("headline_events", [])[:5],
        "sector_watch": parsed.get("sector_watch", []),
        "watchlist_exposure": parsed.get("watchlist_exposure", []),
        "event_playbooks": parsed.get("event_playbooks", []),
        "signal_highlights": parsed.get("signal_highlights", [])[:5],
    }

    return (
        MacroSummary(
            bullets=bullets,
            model=model_name,
            cached_at=datetime.now(UTC),
            data_gaps=parsed.get("data_gaps", []),
        ),
        structured,
    )


def llm_is_configured() -> bool:
    return _get_chat_model() is not None


def is_stale_llm_summary(summary: dict | None) -> bool:
    if not summary:
        return False
    bullets = summary.get("bullets") or []
    if any("OPENAI_API_KEY" in b or "ANTHROPIC_API_KEY" in b for b in bullets):
        return True
    gaps = summary.get("data_gaps") or []
    if "llm_unconfigured" in gaps and llm_is_configured():
        return True
    if any(g in gaps for g in _STALE_LLM_GAP_CODES) and llm_is_configured():
        return True
    return False


def _chat_openai_compatible(
    settings: Settings,
    *,
    api_key: str,
    base_url: str,
    default_model: str,
) -> ChatOpenAI | None:
    if not api_key:
        return None
    model = settings.llm_model or default_model
    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": 0,
        "max_tokens": 1024,
    }
    if "openrouter.ai" in base_url:
        kwargs["default_headers"] = {
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "TradeSentinel AI",
        }
    return ChatOpenAI(**kwargs)


def _get_chat_model():
    settings = get_settings()
    provider = settings.llm_provider_normalized

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return None
        return ChatAnthropic(
            model=settings.llm_model or _ANTHROPIC_DEFAULT_MODEL,
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=1024,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            return None
        return ChatOpenAI(
            model=settings.llm_model or _OPENAI_DEFAULT_MODEL,
            api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=1024,
        )

    if provider in ("openrouter", "openai_compatible"):
        return _chat_openai_compatible(
            settings,
            api_key=settings.resolved_llm_api_key(),
            base_url=settings.effective_base_url(provider),
            default_model=_OPENROUTER_DEFAULT_MODEL,
        )

    if provider == "ollama":
        return ChatOllama(
            model=settings.llm_model or _OLLAMA_DEFAULT_MODEL,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_predict=1024,
        )

    if provider == "dashscope":
        return _chat_openai_compatible(
            settings,
            api_key=settings.dashscope_api_key,
            base_url=settings.effective_base_url("dashscope"),
            default_model=_DASHSCOPE_DEFAULT_MODEL,
        )

    return None


def _display_model(settings: Settings) -> str:
    model = settings.llm_model or "default"
    return f"{settings.llm_provider_normalized}:{model}"
