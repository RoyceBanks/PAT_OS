from __future__ import annotations

import logging
from time import perf_counter

import requests


LOGGER = logging.getLogger(
    "SENTINEL"
)

REVIEW_NUM_CTX = 8192
REVIEW_NUM_PREDICT = 1400
REVIEW_TEMPERATURE = 0.0


class SentinelReviewLLMError(
    RuntimeError
):
    pass


def _backend_value(
    backend,
    name: str,
    default=None,
):
    value = getattr(
        backend,
        name,
        default,
    )

    if value is None:
        return default

    return value


def _endpoint(
    backend,
) -> str:
    host = str(
        _backend_value(
            backend,
            "host",
            "http://127.0.0.1:11434",
        )
    ).rstrip("/")

    return (
        host
        + "/api/chat"
    )


def _post(
    backend,
    payload: dict,
) -> dict:
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
            _endpoint(
                backend
            ),
            json=payload,
            timeout=(
                10,
                timeout,
            ),
        )

        response.raise_for_status()

    except requests.Timeout as exc:
        elapsed = (
            perf_counter()
            - started
        )

        raise SentinelReviewLLMError(
            "SENTINEL bounded review timed out "
            f"after {elapsed:.1f}s. "
            "The proposal remains unapproved and "
            "no safety gate was bypassed."
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

        raise SentinelReviewLLMError(
            "SENTINEL bounded review could not "
            f"reach Ollama at "
            f"{_endpoint(backend)}: "
            f"{exc}{detail}"
        ) from exc

    elapsed = (
        perf_counter()
        - started
    )

    LOGGER.info(
        "SENTINEL bounded Ollama response "
        "completed in %.2fs",
        elapsed,
    )

    try:
        return response.json()
    except ValueError as exc:
        raise SentinelReviewLLMError(
            "Ollama returned a non-JSON "
            "SENTINEL review response."
        ) from exc


def _extract(
    data: dict,
) -> tuple[
    str,
    int,
    str | None,
    int | None,
]:
    message = (
        data.get(
            "message"
        )
        or {}
    )

    content = (
        message.get(
            "content"
        )
        or ""
    ).strip()

    thinking = (
        message.get(
            "thinking"
        )
        or data.get(
            "thinking"
        )
        or ""
    )

    done_reason = (
        data.get(
            "done_reason"
        )
        or message.get(
            "done_reason"
        )
    )

    eval_count = (
        data.get(
            "eval_count"
        )
    )

    return (
        content,
        len(
            thinking
        ),
        done_reason,
        eval_count,
    )


def sentinel_review_chat(
    backend,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Bounded Ollama generation for SENTINEL reviews only.

    This does not change:
    - PAT review policy
    - severity mapping
    - consistency reconciliation
    - approval behavior
    - FORGE generation

    The model must still return a normal SENTINEL review.
    """

    model = _backend_value(
        backend,
        "model",
        None,
    )

    if not model:
        raise SentinelReviewLLMError(
            "SENTINEL LLM backend has no model configured."
        )

    LOGGER.info(
        "SENTINEL bounded review prompt chars: %s",
        len(
            system_prompt
        )
        + len(
            user_prompt
        ),
    )

    payload = {
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
            "temperature": REVIEW_TEMPERATURE,
            "num_ctx": REVIEW_NUM_CTX,
            "num_predict": REVIEW_NUM_PREDICT,
        },
    }

    data = _post(
        backend,
        payload,
    )

    (
        content,
        thinking_chars,
        done_reason,
        eval_count,
    ) = _extract(
        data
    )

    if content:
        LOGGER.info(
            "SENTINEL bounded review output chars: %s",
            len(
                content
            ),
        )

        return content

    # Compatibility retry for model templates that still
    # consume generation in a thinking phase despite think=False.
    retry_payload = dict(
        payload
    )

    retry_payload[
        "messages"
    ] = [
        payload[
            "messages"
        ][0],
        {
            "role": "user",
            "content": (
                "/no_think\n"
                + user_prompt
            ),
        },
    ]

    retry_payload[
        "options"
    ] = dict(
        payload[
            "options"
        ]
    )

    retry_payload[
        "options"
    ][
        "num_predict"
    ] = 1800

    LOGGER.info(
        "SENTINEL bounded review retrying "
        "with /no_think"
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
    ) = _extract(
        retry_data
    )

    if retry_content:
        LOGGER.info(
            "SENTINEL bounded review output chars: %s",
            len(
                retry_content
            ),
        )

        return retry_content

    raise SentinelReviewLLMError(
        "Ollama returned no SENTINEL review content "
        "after a thinking-disabled retry. "
        f"First: thinking_chars={thinking_chars}, "
        f"done_reason={done_reason!r}, "
        f"eval_count={eval_count!r}. "
        f"Retry: thinking_chars={retry_thinking_chars}, "
        f"done_reason={retry_done_reason!r}, "
        f"eval_count={retry_eval_count!r}."
    )
