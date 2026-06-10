from __future__ import annotations

from urllib.parse import urlparse

from hunt.utils import HuntError, clean_text


MAX_WEBSITE_CHARS = 10_000


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HuntError("Website URL must start with http:// or https:// and include a domain.")


def _fallback_extract(url: str) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise HuntError(
            "Website fallback parsing requires requests and beautifulsoup4. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "HUNT internship assistant/0.1"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()

    main = soup.find("main") or soup.body or soup
    return main.get_text(" ", strip=True)


def extract_website_text(url: str) -> str:
    _validate_url(url)
    text = ""

    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                favor_recall=True,
            ) or ""
    except ImportError:
        text = ""
    except Exception:
        text = ""

    if not text:
        try:
            text = _fallback_extract(url)
        except Exception as exc:
            if isinstance(exc, HuntError):
                raise
            raise HuntError(f"Could not read website '{url}': {exc}") from exc

    cleaned = clean_text(text, MAX_WEBSITE_CHARS)
    if len(cleaned) < 80:
        raise HuntError(f"Could not extract enough readable text from website '{url}'.")
    return cleaned
