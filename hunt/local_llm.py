from __future__ import annotations

import os
from typing import Any

import requests

from hunt.utils import HuntError


OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"


class OllamaConnectionError(HuntError):
    pass


class OllamaModelError(HuntError):
    pass


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


def _raise_for_ollama_response(response: requests.Response, model: str) -> None:
    if response.ok:
        return

    try:
        detail: Any = response.json()
        message = str(detail.get("error", detail))
    except ValueError:
        message = response.text

    lowered = message.lower()
    if response.status_code == 404 or "not found" in lowered or "pull" in lowered:
        raise OllamaModelError(
            f"Ollama model '{model}' is not available. Pull it with:\n"
            f"  ollama pull {model}"
        )

    raise HuntError(f"Ollama returned an error: {message}")


def check_ollama_connection() -> tuple[bool, str]:
    model = get_ollama_model()
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    except requests.ConnectionError as exc:
        raise OllamaConnectionError(
            "Could not connect to the local Ollama server at http://localhost:11434.\n"
            "Start it with:\n"
            "  ollama serve"
        ) from exc
    except requests.RequestException as exc:
        raise HuntError(f"Could not check Ollama: {exc}") from exc

    _raise_for_ollama_response(response, model)
    models = response.json().get("models", [])
    names = {item.get("name") for item in models}
    if model not in names:
        raise OllamaModelError(
            f"Ollama is running, but model '{model}' was not found.\n"
            f"Install it with:\n"
            f"  ollama pull {model}"
        )
    return True, model


def generate_with_local_llm(prompt: str, temperature: float = 0.3) -> str:
    model = get_ollama_model()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,
        },
    }

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=180)
    except requests.ConnectionError as exc:
        raise OllamaConnectionError(
            "Could not connect to the local Ollama server at http://localhost:11434.\n"
            "Start it with:\n"
            "  ollama serve"
        ) from exc
    except requests.RequestException as exc:
        raise HuntError(f"Ollama request failed: {exc}") from exc

    _raise_for_ollama_response(response, model)
    data = response.json()
    output = data.get("response", "").strip()
    if not output:
        raise HuntError("Ollama returned an empty response.")
    return output
