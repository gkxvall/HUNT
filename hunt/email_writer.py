from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from hunt.config import (
    ApplicantInternshipPreferences,
    ApplicantProfile,
    EmailStyleConfig,
)
from hunt.json_utils import (
    CANDIDATE_SUMMARY_SCHEMA,
    COMPANY_SUMMARY_SCHEMA,
    EMAIL_OUTPUT_SCHEMA,
    LLMJsonParseError,
    clean_email_body,
    parse_candidate_summary,
    parse_company_summary,
    parse_email_output,
    validate_email_output,
)
from hunt.local_llm import generate_with_local_llm


@dataclass(frozen=True)
class GeneratedEmail:
    subject: str
    body: str
    warnings: list[str] = field(default_factory=list)


JSON_SYSTEM_CONTRACT = """
SYSTEM CONTRACT:
You are a JSON generator. Return ONLY one valid JSON object.
No markdown. No code fences. No explanations. No text before or after JSON.
Use double quotes for all keys and string values.
Do not use trailing commas. Do not use comments.
If a value is unknown, use "" or [].
Your entire response must be parseable by Python json.loads.
""".strip()


def summarize_company(
    website_text: str,
    model: str,
    debug_outputs: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    prompt = f"""
{JSON_SYSTEM_CONTRACT}

Summarize the company using only the website text below.

Return ONLY valid JSON in this exact shape:
{json.dumps(COMPANY_SUMMARY_SCHEMA, ensure_ascii=False, indent=2)}

Rules:
- Use only facts visible in the website text.
- Use empty strings or empty lists for missing fields.
- Do not invent details.

Website text:
{website_text}

Return ONLY valid JSON matching this exact schema:
{json.dumps(COMPANY_SUMMARY_SCHEMA, ensure_ascii=False, indent=2)}
Do not write anything outside the JSON object.
""".strip()
    raw_output = generate_with_local_llm(prompt, model=model, temperature=0.1, json_mode=True)
    if debug_outputs is not None:
        debug_outputs["company_raw"] = raw_output
    try:
        parsed = parse_company_summary(raw_output)
    except LLMJsonParseError:
        try:
            repaired = repair_json_with_llm(raw_output, COMPANY_SUMMARY_SCHEMA, model)
            if debug_outputs is not None:
                debug_outputs["company_repair_raw"] = repaired
            parsed = parse_company_summary(repaired)
        except LLMJsonParseError as exc:
            if warnings is not None:
                warnings.append("Company summary JSON could not be parsed; using an empty safe summary.")
            parsed = dict(COMPANY_SUMMARY_SCHEMA)
            if debug_outputs is not None:
                debug_outputs["company_parse_error"] = str(exc)
    if debug_outputs is not None:
        debug_outputs["company_parsed"] = parsed
    return parsed


def summarize_candidate(
    cv_text: str,
    model: str,
    debug_outputs: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    prompt = f"""
{JSON_SYSTEM_CONTRACT}

Summarize the candidate using only the CV text below.

Return ONLY valid JSON in this exact shape:
{json.dumps(CANDIDATE_SUMMARY_SCHEMA, ensure_ascii=False, indent=2)}

Rules:
- Extract only factual CV details.
- Use empty strings or empty lists for missing fields.
- Do not invent details.
- Do not exaggerate.

CV text:
{cv_text}

Return ONLY valid JSON matching this exact schema:
{json.dumps(CANDIDATE_SUMMARY_SCHEMA, ensure_ascii=False, indent=2)}
Do not write anything outside the JSON object.
""".strip()
    raw_output = generate_with_local_llm(prompt, model=model, temperature=0.1, json_mode=True)
    if debug_outputs is not None:
        debug_outputs["candidate_raw"] = raw_output
    try:
        parsed = parse_candidate_summary(raw_output)
    except LLMJsonParseError:
        try:
            repaired = repair_json_with_llm(raw_output, CANDIDATE_SUMMARY_SCHEMA, model)
            if debug_outputs is not None:
                debug_outputs["candidate_repair_raw"] = repaired
            parsed = parse_candidate_summary(repaired)
        except LLMJsonParseError as exc:
            if warnings is not None:
                warnings.append("Candidate summary JSON could not be parsed; using an empty safe summary.")
            parsed = dict(CANDIDATE_SUMMARY_SCHEMA)
            if debug_outputs is not None:
                debug_outputs["candidate_parse_error"] = str(exc)
    if debug_outputs is not None:
        debug_outputs["candidate_parsed"] = parsed
    return parsed


def repair_json_with_llm(raw_output: str, target_schema: dict[str, Any], model: str) -> str:
    prompt = f"""
{JSON_SYSTEM_CONTRACT}

The previous output was invalid JSON. Convert it to valid JSON matching this schema.
Preserve the useful content. Return ONLY valid JSON. No markdown. No explanations.

Target schema:
{json.dumps(target_schema, ensure_ascii=False, indent=2)}

Invalid previous output:
{raw_output}

Return ONLY valid JSON matching the target schema.
""".strip()
    return generate_with_local_llm(prompt, model=model, temperature=0.1, json_mode=True)


def merge_candidate_context(
    candidate_summary: dict[str, Any],
    applicant_profile: ApplicantProfile,
    style_config: EmailStyleConfig,
) -> dict[str, Any]:
    profile_context = applicant_profile.to_prompt_dict(style_config)
    identity = profile_context.get("identity", {})
    education = profile_context.get("education", {})
    skills = profile_context.get("skills_and_interests", {})

    merged: dict[str, Any] = {
        "full_name": _first_present(
            identity.get("full_name"),
            identity.get("preferred_name"),
            candidate_summary.get("full_name"),
        ),
        "location": _first_present(
            identity.get("current_location") if style_config.include_location else None,
            candidate_summary.get("location") if style_config.include_location else None,
        ),
        "education": _first_present(
            _format_env_education(education),
            candidate_summary.get("education"),
        ),
        "university": _first_present(education.get("university"), candidate_summary.get("university")),
        "department": _first_present(education.get("department"), candidate_summary.get("department")),
        "degree": education.get("degree"),
        "year_level": _first_present(education.get("year_level"), candidate_summary.get("year_level")),
        "technical_skills": _dedupe_list(
            _as_list(candidate_summary.get("technical_skills"))
            + skills.get("technical_skills", [])
            + skills.get("programming_languages", [])
            + skills.get("frameworks", [])
            + skills.get("tools", [])
        ),
        "main_interests": _dedupe_list(
            _as_list(candidate_summary.get("main_interests"))
            + skills.get("main_interests", [])
            + skills.get("research_interests", [])
        ),
        "projects": _dedupe_rich_items(
            _as_list(candidate_summary.get("projects")) + profile_context.get("projects", [])
        ),
        "experience": _dedupe_rich_items(
            _as_list(candidate_summary.get("experience"))
            + profile_context.get("experience_highlights", [])
        ),
    }
    if style_config.include_gpa and education.get("gpa"):
        merged["gpa"] = education["gpa"]
        if education.get("gpa_scale"):
            merged["gpa_scale"] = education["gpa_scale"]
    if style_config.include_languages:
        merged["languages"] = _dedupe_list(
            _as_list(candidate_summary.get("languages")) + skills.get("languages", [])
        )
    return _omit_empty(merged)


def build_prompt_snapshot(
    company_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    email_style_config: EmailStyleConfig,
) -> dict[str, Any]:
    applicant_profile_prompt = applicant_profile.to_prompt_dict(email_style_config)
    internship_prompt = internship_preferences.to_prompt_dict(email_style_config)
    signature_dict = applicant_profile.to_signature_dict(email_style_config)
    merged_candidate_context = merge_candidate_context(
        candidate_summary,
        applicant_profile,
        email_style_config,
    )
    return {
        "company_summary": _omit_empty(company_summary),
        "candidate_summary_from_cv": _omit_empty(candidate_summary),
        "applicant_profile_prompt": applicant_profile_prompt,
        "merged_candidate_context": merged_candidate_context,
        "internship_preferences": internship_prompt,
        "signature": signature_dict,
        "email_style": email_style_config.to_prompt_dict(),
    }


def _academic_level_description(level: str) -> str:
    descriptions = {
        "A": "casual/simple student tone: direct, friendly, simple words, less formal, suitable for startups",
        "B": "balanced professional tone: professional but natural, not too academic, not too casual",
        "C": "highly academic/formal tone: more formal, more structured, suitable for research labs, universities, academic internships, and R&D departments",
    }
    return descriptions.get(level, descriptions["B"])


def _length_description(length: str) -> str:
    descriptions = {
        "short": "150-220 words",
        "medium": "250-400 words",
        "long": "400-650 words",
    }
    return descriptions.get(length, descriptions["medium"])


def _format_description(email_format: str) -> str:
    if email_format == "compact":
        return "4 to 5 short paragraphs; shorter email; focus on a quick internship request"
    return (
        "7 to 9 paragraphs; include introduction, company fit, interests, skills, projects, "
        "experience, contribution angle, enabled notes, CV attachment note if enabled, and signature"
    )


def build_email_prompt(
    company_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    recipient_email: str,
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    email_style_config: EmailStyleConfig,
) -> str:
    snapshot = build_prompt_snapshot(
        company_summary,
        candidate_summary,
        applicant_profile,
        internship_preferences,
        email_style_config,
    )

    return f"""
{JSON_SYSTEM_CONTRACT}

You are HUNT, a local privacy-first internship application assistant.
Write a tailored internship application email to {recipient_email}.

You MUST adapt the email using these settings:
- language: {email_style_config.language}
- academic level: {email_style_config.academic_level} ({_academic_level_description(email_style_config.academic_level)})
- tone: {email_style_config.tone}
- internship mode: {snapshot["internship_preferences"].get("mode", "not specified")}
- signature style: {email_style_config.signature_style}
- max words: {email_style_config.max_words}
- email format: {email_style_config.email_format} ({_format_description(email_style_config.email_format)})
- length target: {email_style_config.length} ({_length_description(email_style_config.length)})
- include CV attachment note: {email_style_config.include_cv_attachment_note}
- include university requirement note: {email_style_config.include_university_requirement}
- include insurance note: {email_style_config.include_insurance_note}
- include GPA only when enabled and present: {email_style_config.include_gpa}
- include languages only when enabled and present: {email_style_config.include_languages}
- include availability only when enabled and present: {email_style_config.include_availability}
- include links only when enabled and present: {email_style_config.include_links}
- include phone only when enabled and present: {email_style_config.include_phone}
- include location only when enabled and present: {email_style_config.include_location}

ENVIRONMENT PROFILE -- HIGH PRIORITY:
The following applicant profile fields came from .env.
When these fields are present, prefer them over extracted CV values for stable identity, contact, education, internship preference, and style.
Do not ignore these fields unless they are irrelevant or disabled.

Filtered applicant profile from .env:
{json.dumps(snapshot["applicant_profile_prompt"], ensure_ascii=False, indent=2)}

Merged candidate context:
{json.dumps(snapshot["merged_candidate_context"], ensure_ascii=False, indent=2)}

Company summary:
{json.dumps(snapshot["company_summary"], ensure_ascii=False, indent=2)}

Internship preferences:
{json.dumps(snapshot["internship_preferences"], ensure_ascii=False, indent=2)}

Signature dictionary:
{json.dumps(snapshot["signature"], ensure_ascii=False, indent=2)}

Email style configuration:
{json.dumps(snapshot["email_style"], ensure_ascii=False, indent=2)}

Strict rules:
- Use only the JSON information above.
- Do not invent details, links, phone numbers, location, GPA, languages, university data, availability, or company facts.
- Omit missing information naturally.
- Do not include empty labels or placeholders such as None, N/A, [your name], [portfolio], or similar text.
- Mention one specific company detail if present.
- Mention the university and department naturally when present.
- Mention internship mode naturally when present.
- Mention GPA only if it appears in merged candidate context.
- Mention languages only if they appear in merged candidate context.
- Mention availability only if it appears in internship preferences.
- Mention university requirement only if it appears in internship preferences.
- Mention insurance only if it appears in internship preferences.
- Mention remote reason only if it appears in internship preferences.
- Include links, phone, and location only if they appear in the signature dictionary or allowed profile fields.
- Sign off using only the signature dictionary.
- Body must stay under {email_style_config.max_words} words.

Format guidance:
- If EMAIL_FORMAT is compact: write 4 to 5 short paragraphs, keep it direct, and focus on a quick internship request.
- If EMAIL_FORMAT is full: write 7 to 9 paragraphs, closer to this flow without hardcoding exact text:
  1. Greeting.
  2. Name plus year/degree/department/university if available and internship request with mode.
  3. Why the company is interesting using one specific company detail.
  4. Main interests and relevant skills.
  5. One or two projects if available.
  6. Experience highlight if available.
  7. Contribution angle.
  8. Enabled university/insurance/remote/availability notes if present.
  9. CV attachment note if enabled and signature.

Subject rules:
- If include_subject_keywords is true, include exactly one relevant keyword in the subject, such as "AI Engineering", "Computer Vision", or "Machine Learning".
- If include_subject_keywords is false, use the simple subject "Internship Application".

Return ONLY valid JSON:
{json.dumps({"subject": "string", "body": "string"}, ensure_ascii=False, indent=2)}

The body value may contain newline characters escaped as \\n, but it must remain valid JSON.
Do not write anything outside the JSON object.
""".strip()


def write_email(
    company_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
    recipient_email: str,
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    email_style_config: EmailStyleConfig,
    model: str,
    debug_outputs: dict[str, Any] | None = None,
) -> tuple[str, str]:
    prompt = build_email_prompt(
        company_summary,
        candidate_summary,
        recipient_email,
        applicant_profile,
        internship_preferences,
        email_style_config,
    )
    raw_output = generate_with_local_llm(prompt, model=model, temperature=0.2, json_mode=True)
    if debug_outputs is not None:
        debug_outputs["email_raw"] = raw_output
    try:
        parsed = parse_email_output(raw_output)
    except LLMJsonParseError:
        repaired = repair_json_with_llm(raw_output, EMAIL_OUTPUT_SCHEMA, model)
        if debug_outputs is not None:
            debug_outputs["email_repair_raw"] = repaired
        parsed = parse_email_output(repaired)
    subject = parsed["subject"]
    body = clean_email_body(parsed["body"])
    if debug_outputs is not None:
        debug_outputs["email_parsed"] = {"subject": subject, "body": body}
    return subject, body


def build_generation_warnings(
    subject: str,
    body: str,
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    email_style_config: EmailStyleConfig,
) -> list[str]:
    generated = GeneratedEmail(subject=subject, body=body)
    warnings = validate_generated_email(
        generated,
        applicant_profile,
        internship_preferences,
        email_style_config,
    )
    warnings.extend(validate_email_output(subject, body, email_style_config.max_words))
    return warnings


def parse_generated_email(text: str) -> GeneratedEmail:
    parsed = parse_email_output(text)
    return GeneratedEmail(subject=parsed["subject"], body=parsed["body"])


def validate_generated_email(
    generated: GeneratedEmail,
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    style_config: EmailStyleConfig,
) -> list[str]:
    warnings: list[str] = []
    body = generated.body
    body_lower = body.lower()
    word_count = len(re.findall(r"\b\w+\b", body))
    if word_count > int(style_config.max_words * 1.2):
        warnings.append(
            f"Body is {word_count} words, more than 20% over EMAIL_MAX_WORDS={style_config.max_words}."
        )

    language_warning = _language_warning(style_config.language, body)
    if language_warning:
        warnings.append(language_warning)

    signature = applicant_profile.to_signature_dict(style_config)
    for key in ("name", "phone", "location", "email"):
        value = signature.get(key)
        if value and str(value).lower() not in body_lower:
            warnings.append(f"Enabled signature field '{key}' was provided but may be missing.")
    for value in signature.get("links", {}).values():
        if value and str(value).lower() not in body_lower:
            warnings.append("An enabled signature link was provided but may be missing.")

    if not style_config.include_phone and applicant_profile.contact.phone:
        _warn_if_value_present(warnings, body, applicant_profile.contact.phone, "Disabled phone")
    if not style_config.include_location and applicant_profile.identity.current_location:
        _warn_if_value_present(
            warnings,
            body,
            applicant_profile.identity.current_location,
            "Disabled location",
        )
    if applicant_profile.education.gpa:
        appears = applicant_profile.education.gpa.lower() in body_lower
        if appears and not style_config.include_gpa:
            warnings.append("GPA appears even though EMAIL_INCLUDE_GPA=false.")
        if style_config.include_gpa and not appears:
            warnings.append("GPA was enabled and provided but may be missing.")
    if not style_config.include_links:
        for value in applicant_profile.to_signature_dict(
            EmailStyleConfig(include_links=True)
        ).get("links", {}).values():
            _warn_if_value_present(warnings, body, str(value), "Disabled link")
    if not style_config.include_languages:
        for language in applicant_profile.skills.languages:
            _warn_if_value_present(warnings, body, language, "Disabled language")

    for value, label in (
        (applicant_profile.identity.full_name, "full name"),
        (applicant_profile.education.university, "university"),
    ):
        if value and value.lower() not in body_lower:
            warnings.append(f"Provided {label} may have been ignored.")
    if internship_preferences.mode and internship_preferences.mode.lower() not in body_lower:
        warnings.append("Internship mode may have been ignored.")

    return warnings


def _language_warning(language: str, body: str) -> str | None:
    normalized = language.strip().lower()
    body_lower = body.lower()
    if normalized == "english":
        return None
    if normalized == "turkish":
        markers = (" ve ", " bir ", " için ", " olarak ", "saygılarımla", "merhaba", "teşekkür")
        if not any(marker in body_lower for marker in markers):
            return "EMAIL_LANGUAGE=Turkish may not have been followed."
    elif normalized == "french":
        markers = (" je ", " vous ", " pour ", " cordialement", "bonjour")
        if not any(marker in body_lower for marker in markers):
            return "EMAIL_LANGUAGE=French may not have been followed."
    elif normalized == "arabic":
        if not re.search(r"[\u0600-\u06FF]", body):
            return "EMAIL_LANGUAGE=Arabic may not have been followed."
    return None


def _warn_if_value_present(warnings: list[str], body: str, value: str, label: str) -> None:
    if value.lower() in body.lower():
        warnings.append(f"{label} appears even though its include flag is disabled.")


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _as_list(value: Any) -> list[Any]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dedupe_list(items: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for item in items:
        if item in (None, "", [], {}):
            continue
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_rich_items(items: list[Any]) -> list[Any]:
    by_name: dict[str, Any] = {}
    no_name: list[Any] = []
    for item in items:
        if item in (None, "", [], {}):
            continue
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or "").strip().lower()
            if name:
                existing = by_name.get(name)
                if existing is None or len(str(item)) > len(str(existing)):
                    by_name[name] = item
            else:
                no_name.append(item)
        else:
            key = str(item).strip().lower()
            if key and key not in by_name:
                by_name[key] = item
    return list(by_name.values()) + _dedupe_list(no_name)


def _format_env_education(education: dict[str, Any]) -> str | None:
    parts = [
        education.get("year_level"),
        education.get("degree"),
        education.get("department"),
        education.get("university"),
    ]
    text = ", ".join(str(part) for part in parts if part)
    return text or None


def _omit_empty(data: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in data.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            nested = _omit_empty(value)
            if nested:
                filtered[key] = nested
        elif isinstance(value, list):
            items = [item for item in value if item not in (None, "", [], {})]
            if items:
                filtered[key] = items
        else:
            filtered[key] = value
    return filtered
