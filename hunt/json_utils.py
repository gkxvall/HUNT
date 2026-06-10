from __future__ import annotations

import ast
import json
import re
from typing import Any


COMPANY_SUMMARY_SCHEMA: dict[str, Any] = {
    "company_name": "",
    "team_name": "",
    "what_company_does": "",
    "products_or_services": [],
    "technologies_or_domains": [],
    "internship_relevant_areas": [],
    "specific_company_detail": "",
    "remote_or_hiring_info": "",
}

CANDIDATE_SUMMARY_SCHEMA: dict[str, Any] = {
    "full_name": "",
    "education": "",
    "university": "",
    "department": "",
    "year_level": "",
    "location": "",
    "technical_skills": [],
    "main_interests": [],
    "projects": [],
    "experience": [],
    "languages": [],
}

EMAIL_OUTPUT_SCHEMA: dict[str, Any] = {
    "subject": "",
    "body": "",
}

LIST_FIELDS = {
    "products_or_services",
    "technologies_or_domains",
    "internship_relevant_areas",
    "technical_skills",
    "main_interests",
    "projects",
    "experience",
    "languages",
}


class LLMJsonParseError(ValueError):
    def __init__(self, message: str, raw_output: str):
        preview = raw_output[:1000]
        super().__init__(
            f"{message}\n\n"
            f"Raw output preview:\n{preview}\n\n"
            "Tip: rerun with --debug-prompt or --debug-llm-output to inspect the prompt and raw model output."
        )
        self.raw_output = raw_output


def parse_llm_json(raw: str, required_keys: list[str] | None = None) -> dict[str, Any]:
    cleaned = strip_markdown_fences(raw.strip())
    candidates = [cleaned]
    extracted = extract_first_balanced_json_object(cleaned)
    if extracted and extracted not in candidates:
        candidates.append(extracted)

    repaired_candidates: list[str] = []
    for candidate in candidates:
        repaired_candidates.append(repair_common_json(candidate))

    for candidate in candidates + repaired_candidates:
        parsed = _try_json_loads(candidate)
        if isinstance(parsed, dict):
            return _with_required_defaults(parsed, required_keys)

    for candidate in candidates + repaired_candidates:
        parsed = _try_literal_eval(candidate)
        if isinstance(parsed, dict):
            return _with_required_defaults(parsed, required_keys)

    raise LLMJsonParseError("Could not parse local LLM output as a JSON object.", raw)


def parse_company_summary(raw: str) -> dict[str, Any]:
    return _apply_schema(parse_llm_json(raw, list(COMPANY_SUMMARY_SCHEMA)), COMPANY_SUMMARY_SCHEMA)


def parse_candidate_summary(raw: str) -> dict[str, Any]:
    return _apply_schema(parse_llm_json(raw, list(CANDIDATE_SUMMARY_SCHEMA)), CANDIDATE_SUMMARY_SCHEMA)


def parse_email_output(raw: str) -> dict[str, str]:
    try:
        parsed = parse_llm_json(raw, list(EMAIL_OUTPUT_SCHEMA))
        output = _apply_schema(parsed, EMAIL_OUTPUT_SCHEMA)
    except LLMJsonParseError:
        output = _parse_email_text_fallback(raw)

    subject = str(output.get("subject") or "Internship Application").strip()
    body = clean_email_body(str(output.get("body") or ""))
    if not body:
        raise LLMJsonParseError("Parsed email output did not contain a usable email body.", raw)
    return {"subject": subject or "Internship Application", "body": body}


def strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    fence_match = re.fullmatch(r"```(?:[A-Za-z0-9_-]+)?\s*([\s\S]*?)\s*```", stripped)
    if fence_match:
        return fence_match.group(1).strip()
    stripped = re.sub(r"^\s*```(?:[A-Za-z0-9_-]+)?\s*", "", stripped)
    stripped = re.sub(r"\s*```\s*$", "", stripped)
    return stripped.strip()


def extract_first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def repair_common_json(text: str) -> str:
    repaired = strip_markdown_fences(text.strip())
    if (
        len(repaired) >= 2
        and repaired[0] == repaired[-1]
        and repaired[0] in {"'", '"'}
        and "{" in repaired
    ):
        repaired = repaired[1:-1].strip()

    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
    }
    for old, new in replacements.items():
        repaired = repaired.replace(old, new)

    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = re.sub(r"\bTrue\b", "true", repaired)
    repaired = re.sub(r"\bFalse\b", "false", repaired)
    repaired = re.sub(r"\bNone\b", "null", repaired)
    return repaired


def clean_email_body(body: str) -> str:
    cleaned = strip_markdown_fences(body)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n").strip()
    cleaned = re.sub(r"^\s*(Subject|Subject line|Konu|Başlık)\s*:.*(?:\n|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(Email|Body|E-posta|Mesaj)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\[(?:your name|your full name|company name|portfolio|github|linkedin|phone|email)\]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"(?im)^\s*(N/A|None)\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def validate_email_output(subject: str, body: str, max_words: int | None = None) -> list[str]:
    warnings: list[str] = []
    if not subject.strip():
        warnings.append("Subject is empty.")
    if not body.strip():
        warnings.append("Body is empty.")
    if "```" in body:
        warnings.append("Body contains a markdown code fence.")
    if re.search(r"\[(?:your name|company name|portfolio|github|linkedin)\]", body, re.IGNORECASE):
        warnings.append("Body contains suspicious placeholders.")
    if body.strip().startswith("{") and body.strip().endswith("}"):
        warnings.append("Body looks like JSON instead of an email.")
    if max_words is not None:
        word_count = len(re.findall(r"\b\w+\b", body))
        if word_count > int(max_words * 1.2):
            warnings.append(f"Body is {word_count} words, more than 20% over EMAIL_MAX_WORDS={max_words}.")
    return warnings


def _parse_email_text_fallback(raw: str) -> dict[str, str]:
    cleaned = _remove_leading_explanations(strip_markdown_fences(raw))
    subject_match = re.search(
        r"^\s*(?:Subject|Subject line|Konu|Başlık)\s*:\s*(?P<subject>.+?)\s*$",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    body_match = re.search(
        r"^\s*(?:Email|Body|E-posta|Mesaj)\s*:\s*(?P<body>[\s\S]+)$",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if subject_match or body_match:
        subject = subject_match.group("subject").strip() if subject_match else "Internship Application"
        if body_match:
            body = body_match.group("body").strip()
        else:
            body = cleaned[subject_match.end() :].strip() if subject_match else cleaned
        return {"subject": subject or "Internship Application", "body": body}

    if _looks_like_email_body(cleaned):
        return {"subject": "Internship Application", "body": cleaned}

    raise LLMJsonParseError("Could not parse email output as JSON or email text.", raw)


def _remove_leading_explanations(text: str) -> str:
    cleaned = text.strip()
    patterns = (
        r"^\s*Here is (?:the )?(?:email|JSON)\s*:\s*",
        r"^\s*Sure,?\s+here is[\s\S]*?:\s*",
        r"^\s*Below is[\s\S]*?:\s*",
    )
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _looks_like_email_body(text: str) -> bool:
    lowered = text.lower()
    return bool(text.strip()) and (
        "\n" in text
        or lowered.startswith(("dear ", "hello ", "hi ", "merhaba", "sayın", "bonjour"))
        or "best regards" in lowered
        or "saygılarımla" in lowered
    )


def _try_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _try_literal_eval(text: str) -> Any:
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def _with_required_defaults(data: dict[str, Any], required_keys: list[str] | None) -> dict[str, Any]:
    if not required_keys:
        return data
    with_defaults = dict(data)
    for key in required_keys:
        if key in with_defaults:
            continue
        if key == "subject":
            with_defaults[key] = "Internship Application"
        elif key in LIST_FIELDS:
            with_defaults[key] = []
        else:
            with_defaults[key] = ""
    return with_defaults


def _apply_schema(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, default in schema.items():
        value = data.get(key, default)
        if isinstance(default, list) and not isinstance(value, list):
            value = [value] if value not in (None, "") else []
        elif isinstance(default, str) and value is None:
            value = ""
        output[key] = value
    return output
