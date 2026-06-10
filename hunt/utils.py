from __future__ import annotations

import re
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


class HuntError(Exception):
    """Base exception for user-facing HUNT errors."""


def clean_text(text: str, limit: int | None = None) -> str:
    """Normalize whitespace and optionally trim text to a maximum length."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(normalized) > limit:
        return normalized[:limit].rsplit(" ", 1)[0].strip()
    return normalized


def ensure_existing_file(path: str) -> Path:
    file_path = Path(path).expanduser()
    if not file_path.exists():
        raise HuntError(f"CV file not found: {file_path}")
    if not file_path.is_file():
        raise HuntError(f"CV path is not a file: {file_path}")
    return file_path
