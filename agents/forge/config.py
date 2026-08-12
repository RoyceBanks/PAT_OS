from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ForgeConfig:
    model: str = os.getenv("FORGE_MODEL", "pat")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    temperature: float = float(os.getenv("FORGE_TEMPERATURE", "0.15"))
    timeout: int = int(os.getenv("FORGE_TIMEOUT", "120"))
    max_context_files: int = int(os.getenv("FORGE_MAX_CONTEXT_FILES", "20"))


CONFIG = ForgeConfig()
