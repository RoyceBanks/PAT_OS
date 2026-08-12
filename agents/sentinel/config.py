from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class SentinelConfig:
    model: str = os.getenv("SENTINEL_MODEL", "pat")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    temperature: float = float(os.getenv("SENTINEL_TEMPERATURE", "0.05"))
    timeout: int = int(os.getenv("SENTINEL_TIMEOUT", "120"))
    max_context_files: int = int(os.getenv("SENTINEL_MAX_CONTEXT_FILES", "30"))


CONFIG = SentinelConfig()
