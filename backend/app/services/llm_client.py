"""OpenAI chat client for ResumeIQ (parse, ATS structure, tailor, jobs AI)."""
from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator, Sequence
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

log = logging.getLogger(__name__)

_JSON_TAIL = (
    "\n\nRespond with valid JSON only. Do not wrap in markdown code fences. "
    "Do not include commentary before or after the JSON object."
)

_DEFAULT_MODEL = "gpt-4o-mini"


def llm_configured() -> bool:
    return bool((settings.openai_api_key or "").strip())


def openai_base_url() -> str:
    raw = (settings.openai_base_url or "").strip().rstrip("/")
    return raw or "https://api.openai.com/v1"


def llm_key_diagnosis() -> dict[str, Any]:
    key = (settings.openai_api_key or "").strip()
    base = openai_base_url()
    if not key:
        return {
            "ok": False,
            "code": "missing_key",
            "message": "OPENAI_API_KEY is empty. Set it in backend/.env or the repo-root .env.",
        }
    if not key.startswith("sk-"):
        return {
            "ok": False,
            "code": "unexpected_key_prefix",
            "message": "OPENAI_API_KEY should start with sk- (OpenAI secret key).",
        }
    return {
        "ok": True,
        "code": "ok",
        "message": "Key looks usable.",
        "base_url": base,
        "model": (settings.openai_model or _DEFAULT_MODEL).strip(),
        "provider": "openai",
    }


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key.strip(),
        base_url=openai_base_url(),
        timeout=float(settings.openai_timeout or 120.0),
    )


def _to_openai_messages(messages: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        role = str(m.get("role") or "user").lower()
        if role not in {"system", "user", "assistant"}:
            role = "user"
        content = m.get("content")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text") or ""))
            content = "\n".join(text_parts) if text_parts else json.dumps(content)
        out.append({"role": role, "content": str(content or "")})
    return out


def _strip_json_fences(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _effective_max_tokens(max_tokens: int | None) -> int:
    configured = int(settings.openai_max_tokens or 4096)
    if max_tokens is None:
        return max(512, configured)
    return max(256, int(max_tokens))


async def chat_complete(
    messages: Sequence[dict[str, Any]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = 4096,
    json_mode: bool = False,
) -> str:
    if not llm_configured():
        raise RuntimeError("OPENAI_API_KEY is not configured")
    diag = llm_key_diagnosis()
    if not diag.get("ok"):
        raise RuntimeError(str(diag.get("message") or "OpenAI API key is not usable"))

    msgs = list(messages)
    if json_mode and msgs:
        last = dict(msgs[-1])
        content = str(last.get("content") or "")
        if "json" not in content.lower():
            last["content"] = content + _JSON_TAIL
            msgs[-1] = last

    openai_messages = _to_openai_messages(msgs)
    model = (settings.openai_model or _DEFAULT_MODEL).strip()
    temp = float(settings.openai_temperature if temperature is None else temperature)
    tokens = _effective_max_tokens(max_tokens)
    if json_mode:
        tokens = min(tokens, 8192)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": openai_messages,
        "temperature": temp,
        "max_tokens": tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await _client().chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAI chat failed (%s): %s", model, exc)
        raise RuntimeError(f"OpenAI chat failed for {model}: {exc}") from exc

    choice = (response.choices or [None])[0]
    if choice is None:
        raise RuntimeError("OpenAI returned no choices")
    text = (choice.message.content or "").strip()
    if not text:
        raise RuntimeError("OpenAI returned empty content")
    return text


async def chat_json(
    messages: Sequence[dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = 4096,
) -> dict[str, Any]:
    raw = await chat_complete(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    text = _strip_json_fences(raw)
    if not text.startswith("{"):
        match = re.search(r"\{[\s\S]*\}\s*$", text)
        if match:
            text = match.group(0)
    data = json.loads(text or "{}")
    if not isinstance(data, dict):
        raise ValueError("LLM JSON response was not an object")
    return data


async def chat_stream(
    messages: Sequence[dict[str, Any]],
    *,
    temperature: float = 0.4,
    max_tokens: int | None = 4096,
) -> AsyncIterator[str]:
    text = await chat_complete(messages, temperature=temperature, max_tokens=max_tokens)
    if text:
        yield text
