import requests

def call_ollama(prompt: str, model: str = "llama3:8b") -> str:
    """
    Llama al endpoint de generación de Ollama con el prompt indicado.
    """
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        },
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    return result.get("response", "")
