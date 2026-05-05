"""AI Advisor service — pure logic; views just call this.

Two entry points:
    - generate(session, user_message)              → str (full reply)
    - stream(session, user_message)                → Iterator[str] (token chunks)

Both:
    1. Persist the user message
    2. Build RAG context
    3. Build full prompt history (truncated)
    4. Call OpenAI (or fall back to a deterministic local responder if no key)
    5. Persist the assistant message + context_property_ids snapshot
"""

from __future__ import annotations

import logging
from typing import Iterator

from django.conf import settings

from apps.ai_advisor.models import AIConversationSession, ChatMessage, Role
from apps.ai_advisor.services.prompts import build_system_prompt
from apps.ai_advisor.services.retriever import (
    context_property_ids,
    render_context,
    retrieve_context,
)

logger = logging.getLogger("vivalty.ai")

MAX_HISTORY_TURNS = 10  # last N user/assistant exchanges sent to the LLM


def _history_messages(session: AIConversationSession) -> list[dict]:
    qs = session.messages.exclude(role=Role.SYSTEM).order_by("-created_at")[: MAX_HISTORY_TURNS * 2]
    return [{"role": m.role, "content": m.content} for m in reversed(list(qs))]


def _openai_client():
    """Return an OpenAI SDK client or None if no key is configured."""
    if not settings.OPENAI_API_KEY:
        return None
    from openai import OpenAI

    kwargs = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    return OpenAI(**kwargs)


def _fallback_response(user_message: str, context: str) -> str:
    """Deterministic structured response when no OpenAI key is configured.

    Useful for local dev / CI so the chat UI never breaks. We DO surface this
    as 'estimated' — it satisfies our anti-hallucination contract.
    """
    return (
        "**Quick Answer**\n"
        "I'm running in offline (no-LLM) mode, so this is a structured response built only "
        "from the platform data I can see. Configure `OPENAI_API_KEY` to enable the full advisor.\n\n"
        "**Analysis**\n"
        f"- Your question: _{user_message[:200]}_\n"
        "- I retrieved the following platform context (estimated where flagged):\n"
        f"```\n{context[:1200]}\n```\n\n"
        "**Comparison**\n"
        "Comparison requires the LLM provider. Re-ask once `OPENAI_API_KEY` is set.\n\n"
        "**Recommendation**\n"
        "Browse the highest-scored listings shown above in the marketplace, and use filters "
        "(country, ROI ≥ 5%, score ≥ 70) to narrow down."
    )


def _build_messages(session: AIConversationSession, user_message: str) -> tuple[list[dict], list[int]]:
    docs = retrieve_context(
        user_message,
        pinned_property=session.pinned_property,
        pinned_country=session.pinned_country,
    )
    context_block = render_context(docs)
    system = build_system_prompt(extra_context=context_block)

    msgs: list[dict] = [{"role": "system", "content": system}]
    msgs.extend(_history_messages(session))
    msgs.append({"role": "user", "content": user_message})
    return msgs, context_property_ids(docs)


def _persist_user(session: AIConversationSession, user_message: str, ctx_ids: list[int]) -> ChatMessage:
    msg = ChatMessage.objects.create(
        session=session,
        role=Role.USER,
        content=user_message,
        context_property_ids=ctx_ids,
    )
    if not session.title:
        session.title = (user_message.strip().splitlines()[0] or "New chat")[:80]
        session.save(update_fields=["title", "updated_at"])
    else:
        session.save(update_fields=["updated_at"])
    return msg


def _persist_assistant(session: AIConversationSession, content: str, ctx_ids: list[int]) -> ChatMessage:
    return ChatMessage.objects.create(
        session=session,
        role=Role.ASSISTANT,
        content=content,
        context_property_ids=ctx_ids,
    )


def generate(session: AIConversationSession, user_message: str) -> ChatMessage:
    """Non-streaming reply. Returns the persisted assistant ChatMessage."""
    messages, ctx_ids = _build_messages(session, user_message)
    _persist_user(session, user_message, ctx_ids)

    client = _openai_client()
    if client is None:
        text = _fallback_response(user_message, messages[0]["content"])
    else:
        try:
            resp = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.3,
            )
            text = resp.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI generate() failed; using fallback")
            text = _fallback_response(user_message, messages[0]["content"])

    return _persist_assistant(session, text, ctx_ids)


def stream(session: AIConversationSession, user_message: str) -> Iterator[str]:
    """Generator yielding plain-text chunks. Persists the full reply at the end.

    The view wraps each yielded chunk in a Server-Sent-Event frame.
    """
    messages, ctx_ids = _build_messages(session, user_message)
    _persist_user(session, user_message, ctx_ids)

    client = _openai_client()
    full = ""

    if client is None:
        text = _fallback_response(user_message, messages[0]["content"])
        for line in text.splitlines(keepends=True):
            full += line
            yield line
        _persist_assistant(session, full, ctx_ids)
        return

    try:
        stream_resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            stream=True,
        )
        for chunk in stream_resp:
            try:
                delta = chunk.choices[0].delta.content or ""
            except (AttributeError, IndexError):
                delta = ""
            if delta:
                full += delta
                yield delta
    except Exception:
        logger.exception("OpenAI stream() failed; using fallback")
        text = _fallback_response(user_message, messages[0]["content"])
        for line in text.splitlines(keepends=True):
            full += line
            yield line

    _persist_assistant(session, full, ctx_ids)
