from __future__ import annotations

from pathlib import Path

from hunt.utils import HuntError, clean_text, ensure_existing_file


MAX_CV_CHARS = 12_000


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HuntError("PDF support requires pypdf. Install dependencies with: pip install -r requirements.txt") from exc

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise HuntError("DOCX support requires python-docx. Install dependencies with: pip install -r requirements.txt") from exc

    document = Document(str(path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(paragraphs)


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_cv(path: str) -> str:
    cv_path = ensure_existing_file(path)
    suffix = cv_path.suffix.lower()

    try:
        if suffix == ".pdf":
            text = _read_pdf(cv_path)
        elif suffix == ".docx":
            text = _read_docx(cv_path)
        elif suffix == ".txt":
            text = _read_txt(cv_path)
        else:
            raise HuntError("Unsupported CV format. Please use PDF, DOCX, or TXT.")
    except HuntError:
        raise
    except Exception as exc:
        raise HuntError(f"Could not read CV file '{cv_path}': {exc}") from exc

    cleaned = clean_text(text, MAX_CV_CHARS)
    if not cleaned:
        raise HuntError(f"No readable text found in CV file '{cv_path}'.")
    return cleaned
