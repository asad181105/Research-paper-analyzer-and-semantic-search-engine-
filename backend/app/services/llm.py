"""LLM provider abstraction: Gemini (recommended), Anthropic, OpenAI-compatible."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from flask import current_app

logger = logging.getLogger(__name__)


def _provider() -> str:
    return (current_app.config.get("LLM_PROVIDER") or "gemini").strip().lower()


def llm_configured() -> bool:
    provider = _provider()
    if provider == "gemini":
        return bool(current_app.config.get("GEMINI_API_KEY"))
    if provider == "openai":
        return bool(current_app.config.get("OPENAI_API_KEY")) or bool(
            current_app.config.get("OPENAI_BASE_URL")
        )
    if provider == "anthropic":
        return bool(current_app.config.get("ANTHROPIC_API_KEY"))
    return False


def llm_status() -> dict:
    provider = _provider()
    return {
        "provider": provider,
        "configured": llm_configured(),
        "model": _model_name(provider),
        "features": {
            "summarize": llm_configured(),
            "qa_stream": llm_configured(),
            "compare": llm_configured(),
            "fallback": "extractive summarization + retrieved chunks when LLM is off",
        },
    }


def _model_name(provider: str) -> str:
    if provider == "gemini":
        return current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash")
    if provider == "openai":
        return current_app.config.get("OPENAI_MODEL", "llama3.1")
    return current_app.config.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")


def complete(system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> str:
    if not llm_configured():
        raise RuntimeError("LLM is not configured")
    provider = _provider()
    if provider == "gemini":
        return _gemini_complete(system, user, max_tokens, temperature)
    if provider == "openai":
        return _openai_complete(system, user, max_tokens, temperature)
    return _anthropic_complete(system, user, max_tokens, temperature)


def stream_complete(system: str, user: str, max_tokens: int = 1200) -> Iterator[str]:
    if not llm_configured():
        raise RuntimeError("LLM is not configured")
    provider = _provider()
    if provider == "gemini":
        yield from _gemini_stream(system, user, max_tokens, temperature=0.2)
        return
    if provider == "openai":
        yield from _openai_stream(system, user, max_tokens)
        return
    yield from _anthropic_stream(system, user, max_tokens)


def _gemini_complete(system: str, user: str, max_tokens: int, temperature: float) -> str:
    import google.generativeai as genai

    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash"),
        system_instruction=system,
    )
    resp = model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    return (resp.text or "").strip()


def _gemini_stream(
    system: str, user: str, max_tokens: int, temperature: float = 0.2
) -> Iterator[str]:
    import google.generativeai as genai

    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash"),
        system_instruction=system,
    )
    stream = model.generate_content(
        user,
        stream=True,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def _anthropic_complete(system: str, user: str, max_tokens: int, temperature: float) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=current_app.config.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in msg.content:
        if getattr(block, "type", "") == "text":
            parts.append(block.text)
        elif hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


def _anthropic_stream(system: str, user: str, max_tokens: int) -> Iterator[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])
    with client.messages.stream(
        model=current_app.config.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def _openai_client():
    from openai import OpenAI

    return OpenAI(
        api_key=current_app.config.get("OPENAI_API_KEY") or "ollama",
        base_url=current_app.config.get("OPENAI_BASE_URL") or "http://localhost:11434/v1",
        timeout=120.0,
    )


def _openai_complete(system: str, user: str, max_tokens: int, temperature: float) -> str:
    client = _openai_client()
    resp = client.chat.completions.create(
        model=current_app.config.get("OPENAI_MODEL", "llama3.1"),
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _openai_stream(system: str, user: str, max_tokens: int) -> Iterator[str]:
    client = _openai_client()
    stream = client.chat.completions.create(
        model=current_app.config.get("OPENAI_MODEL", "llama3.1"),
        max_tokens=max_tokens,
        stream=True,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
