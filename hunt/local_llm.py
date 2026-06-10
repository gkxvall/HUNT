from __future__ import annotations

from typing import Any

import requests

from hunt.utils import HuntError


OLLAMA_URL = "http://localhost:11434"

class OllamaConnectionError(HuntError):
    pass


class OllamaModelError(HuntError):
    pass


def _response_error_message(response: requests.Response) -> str:
    try:
        detail: Any = response.json()
        return str(detail.get("error", detail))
    except ValueError:
        return response.text


def _raise_for_ollama_response(response: requests.Response, model: str) -> None:
    if response.ok:
        return

    message = _response_error_message(response)
    lowered = message.lower()
    if response.status_code == 404 or "not found" in lowered or "pull" in lowered:
        raise OllamaModelError(
            f"Ollama model '{model}' is not available. Pull it with:\n"
            f"  ollama pull {model}"
        )

    raise HuntError(f"Ollama returned an error: {message}")


def _json_mode_unsupported(response: requests.Response) -> bool:
    message = _response_error_message(response).lower()
    return (
        response.status_code in {400, 404, 422}
        and "format" in message
        and "json" in message
    )


def check_ollama_connection(model: str) -> tuple[bool, str]:
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


def generate_with_local_llm(
    prompt: str,
    model: str,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,
            "repeat_penalty": 1.1,
            "stop": [
                "<|im_start|>",
                "<|im_end|>",
                "<|assistant|>",
                "<|user|>",
                "<|system|>",
                "</s>",
            ],
        },
    }
    if json_mode:
        payload["format"] = "json"

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=180)
        if json_mode and not response.ok and _json_mode_unsupported(response):
            fallback_payload = dict(payload)
            fallback_payload.pop("format", None)
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=fallback_payload,
                timeout=180,
            )
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
