from __future__ import annotations

import requests

from .llm import LLMError


STRUCTURAL_NUM_CTX = 4096
STRUCTURAL_NUM_PREDICT = 512
STRUCTURAL_TEMPERATURE = 0.0


def _payload(
    backend,
    system_prompt: str,
    user_prompt: str,
    *,
    think,
    num_predict: int,
) -> dict:
    return {
        "model": backend.model,
        "stream": False,
        "keep_alive": "15m",
        "think": think,
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
            "temperature": STRUCTURAL_TEMPERATURE,
            "num_ctx": STRUCTURAL_NUM_CTX,
            "num_predict": num_predict,
        },
    }


def _post(
    backend,
    payload: dict,
) -> dict:
    url = (
        f"{backend.host.rstrip('/')}"
        "/api/chat"
    )

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=(
                10,
                backend.timeout,
            ),
        )

        response.raise_for_status()

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
            "FORGE structural generation could not "
            f"reach Ollama at {backend.host}: {exc}"
            f"{detail}"
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise LLMError(
            "Ollama returned a non-JSON structural response."
        ) from exc


def _extract_content(
    data: dict,
) -> tuple[str, int, str | None, int | None]:
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

    eval_count = data.get(
        "eval_count"
    )

    return (
        content,
        len(thinking),
        done_reason,
        eval_count,
    )


def structural_chat(
    backend,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Bounded Ollama call used only by FORGE structural editing.

    First attempt:
      - explicitly disables thinking at the top-level Ollama chat API
      - allows 512 generated tokens, enough for a small handler block

    Compatibility retry:
      - only when Ollama returned no final content
      - adds /no_think for model templates that honor the directive
      - raises the output ceiling modestly to 768

    Normal FORGE/SENTINEL calls are unaffected.
    """

    first_payload = _payload(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        think=False,
        num_predict=STRUCTURAL_NUM_PREDICT,
    )

    data = _post(
        backend,
        first_payload,
    )

    (
        content,
        thinking_chars,
        done_reason,
        eval_count,
    ) = _extract_content(
        data
    )

    if content:
        return content

    # Some thinking-capable model templates have historically
    # ignored/smoothed over the API flag. Retry once with the
    # explicit template directive rather than increasing PAT's
    # global timeout.
    retry_prompt = (
        "/no_think\n"
        + user_prompt
    )

    retry_payload = _payload(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=retry_prompt,
        think=False,
        num_predict=768,
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
    ) = _extract_content(
        retry_data
    )

    if retry_content:
        return retry_content

    raise LLMError(
        "Ollama returned no structural FORGE message content "
        "after thinking-disabled retry. "
        f"First response: thinking_chars={thinking_chars}, "
        f"done_reason={done_reason!r}, "
        f"eval_count={eval_count!r}. "
        f"Retry response: thinking_chars={retry_thinking_chars}, "
        f"done_reason={retry_done_reason!r}, "
        f"eval_count={retry_eval_count!r}."
    )
