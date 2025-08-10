import logging
import os
from typing import Optional

import requests
from app.core.config import Settings


logger = logging.getLogger(__name__)


def call_ollama(prompt: str, model: str = "llama3:8b", settings: Optional[Settings] = None) -> str:
    """Llama al endpoint de generación de Ollama con el prompt indicado."""
    base_url = os.environ.get("OLLAMA_URL")
    if not base_url:
        if settings is None:
            settings = Settings()
        base_url = getattr(settings, "ollama_url", "http://localhost:11434")

    try:
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
    except requests.RequestException as exc:
        content = getattr(exc.response, "text", "")
        if content:
            logger.error("Ollama request failed: %s", content)
        else:
            logger.error("Ollama request failed: %s", exc)
        raise RuntimeError(
            f"Error calling Ollama at {base_url}: {content or exc}"
        ) from exc

    result = response.json()
    return result.get("response", "")
