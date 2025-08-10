import os
from typing import Optional

import requests
from app.core.config import Settings


def call_ollama(prompt: str, model: str = "llama3:8b", settings: Optional[Settings] = None) -> str:
    """Llama al endpoint de generación de Ollama con el prompt indicado."""
    base_url = os.environ.get("OLLAMA_URL")
    if not base_url:
        if settings is None:
            settings = Settings()
        base_url = getattr(settings, "ollama_url", "http://localhost:11434")

    response = requests.post(
        base_url.rstrip("/") + "/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    return result.get("response", "")
