from __future__ import annotations

from dataclasses import dataclass
import requests

from .config import CONFIG


class LLMError(RuntimeError):
    pass


@dataclass
class OllamaBackend:
    model: str = CONFIG.model
    host: str = CONFIG.ollama_host
    timeout: int = CONFIG.timeout
    temperature: float = CONFIG.temperature

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.host.rstrip('/')}/api/chat"

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": self.temperature},
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                f"SENTINEL could not reach Ollama at {self.host}: {exc}"
            ) from exc

        data = response.json()
        content = data.get("message", {}).get("content")

        if not content:
            raise LLMError("Ollama returned no message content.")

        return content.strip()
