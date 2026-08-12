from __future__ import annotations

import logging
from time import perf_counter

import requests

from .llm import LLMError


LOGGER = logging.getLogger("FORGE")

IMPLEMENTATION_NUM_CTX = 16384
IMPLEMENTATION_NUM_PREDICT = 6000
IMPLEMENTATION_RETRY_NUM_PREDICT = 7500
IMPLEMENTATION_TEMPERATURE = 0.0


def _backend_value(backend, name: str, default=None):
    value = getattr(backend, name, default)
    return default if value is None else value


def _endpoint(backend) -> str:
    host = str(
        _backend_value(
            backend,
            "host",
            "http://127.0.0.1:11434",
        )
    ).rstrip("/")

    return host + "/api/chat"


def _payload(
    backend,
    system_prompt: str,
    user_prompt: str,
    *,
    num_predict: int,
) -> dict:
    model = _backend_value(
        backend,
        "model",
        None,
    )

    if not model:
        raise LLMError(
            "FORGE LLM backend has no model configured."
        )

    return {
        "model": model,
        "stream": False,
        "keep_alive": "15m",
        "think": False,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "options": {
            "temperature": IMPLEMENTATION_TEMPERATURE,
            "num_ctx": IMPLEMENTATION_NUM_CTX,
            "num_predict": num_predict,
        },
    }


def _post(backend, payload: dict) -> dict:
    timeout = float(
        _backend_value(
            backend,
            "timeout",
            120,
        )
    )

    started = perf_counter()

    try:
        response = requests.post(
            _endpoint(backend),
            json=payload,
            timeout=(
                10,
                timeout,
            ),
        )
        response.raise_for_status()

    except requests.Timeout as exc:
        elapsed = perf_counter() - started

        raise LLMError(
            "FORGE bounded implementation generation "
            f"timed out after {elapsed:.1f}s. "
            "The proposal remains unapproved and "
            "no target files were modified."
        ) from exc

    except requests.RequestException as exc:
        body = ""
        response_obj = getattr(
            exc,
            "response",
            None,
        )

        if response_obj is not None:
            try:
                body = (
                    response_obj.text
                    or ""
                )[:500]
            except Exception:
                body = ""

        detail = (
            f" Response: {body}"
            if body
            else ""
        )

        raise LLMError(
            "FORGE bounded implementation generation "
            f"could not reach Ollama at {_endpoint(backend)}: "
            f"{exc}{detail}"
        ) from exc

    elapsed = perf_counter() - started

    LOGGER.info(
        "FORGE bounded Ollama response completed in %.2fs",
        elapsed,
    )

    try:
        return response.json()
    except ValueError as exc:
        raise LLMError(
            "Ollama returned a non-JSON HTTP response "
            "for FORGE implementation generation."
        ) from exc


def _extract(data: dict):
    message = data.get("message") or {}

    content = (
        message.get("content")
        or ""
    ).strip()

    thinking = (
        message.get("thinking")
        or data.get("thinking")
        or ""
    )

    done_reason = (
        data.get("done_reason")
        or message.get("done_reason")
    )

    eval_count = data.get("eval_count")

    return (
        content,
        len(thinking),
        done_reason,
        eval_count,
    )


def implementation_plan_chat(
    backend,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Bounded Ollama generation for FORGE implementation plans.

    Used for initial plans, pre-approval revisions, and the one
    syntax-only JSON repair pass.
    """

    LOGGER.info(
        "FORGE bounded plan prompt chars: %s",
        len(system_prompt) + len(user_prompt),
    )

    payload = _payload(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        num_predict=IMPLEMENTATION_NUM_PREDICT,
    )

    data = _post(
        backend,
        payload,
    )

    (
        content,
        thinking_chars,
        done_reason,
        eval_count,
    ) = _extract(data)

    if content and done_reason != "length":
        LOGGER.info(
            "FORGE bounded plan output chars: %s",
            len(content),
        )
        return content

    retry_reason = (
        "output-limit"
        if done_reason == "length"
        else "empty-content"
    )

    LOGGER.warning(
        "FORGE bounded plan retry: %s "
        "(thinking_chars=%s, done_reason=%r, eval_count=%r)",
        retry_reason,
        thinking_chars,
        done_reason,
        eval_count,
    )

    retry_payload = _payload(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=(
            "/no_think\n"
            + user_prompt
        ),
        num_predict=IMPLEMENTATION_RETRY_NUM_PREDICT,
    )

    retry_data = _post(
        backend,
        retry_payload,
    )

    (
        retry_content,
        retry_thinking_chars,
        retry_done_reason,
        retry_eval_count,
    ) = _extract(retry_data)

    if (
        retry_content
        and retry_done_reason != "length"
    ):
        LOGGER.info(
            "FORGE bounded plan output chars: %s",
            len(retry_content),
        )
        return retry_content

    raise LLMError(
        "Ollama did not return a complete bounded FORGE "
        "implementation-plan response after one retry. "
        f"First response: thinking_chars={thinking_chars}, "
        f"done_reason={done_reason!r}, eval_count={eval_count!r}. "
        f"Retry response: thinking_chars={retry_thinking_chars}, "
        f"done_reason={retry_done_reason!r}, "
        f"eval_count={retry_eval_count!r}."
    )
