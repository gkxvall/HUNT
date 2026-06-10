from __future__ import annotations

import json
import re
from dataclasses import dataclass

from hunt.config import ApplicantProfile, EmailStyleConfig, build_signature_context
from hunt.local_llm import generate_with_local_llm
from hunt.utils import HuntError


@dataclass(frozen=True)
class GeneratedEmail:
    subject: str
    body: str


def summarize_company(website_text: str) -> str:
    prompt = f"""
You are helping draft an internship application email.
Summarize the company using only the website text below.

Extract:
- what the company does
- products/services
- technologies mentioned
- possible internship-relevant details
- company tone/mission if visible

Do not invent details. If something is not visible, say it is not visible.
Keep the summary concise.

Website text:
{website_text}
""".strip()
    return generate_with_local_llm(prompt, temperature=0.2)


def summarize_candidate(cv_text: str) -> str:
    prompt = f"""
Summarize the candidate using only the CV text below.

Extract only factual details:
- education
- technical skills
- projects
- experience
- strengths for internship applications

Do not invent details. Do not exaggerate. Keep it concise.

CV text:
{cv_text}
""".strip()
    return generate_with_local_llm(prompt, temperature=0.2)


def _academic_level_description(level: str) -> str:
    descriptions = {
        "A": "casual/simple student tone: direct, friendly, simple words, less formal, suitable for startups",
        "B": "balanced professional tone: professional but natural, not too academic, not too casual",
        "C": "highly academic/formal tone: more formal, more structured, suitable for research labs, universities, academic internships, and R&D departments",
    }
    return descriptions.get(level, descriptions["B"])


def write_email(
    company_summary: str,
    candidate_summary: str,
    recipient_email: str,
    applicant_profile: ApplicantProfile,
    email_style_config: EmailStyleConfig,
) -> GeneratedEmail:
    applicant_fields = applicant_profile.to_prompt_dict(email_style_config)
    signature_context = build_signature_context(applicant_profile, email_style_config)
    prompt = f"""
Write a concise, natural internship application email to {recipient_email}.

Company summary:
{company_summary}

Candidate summary:
{candidate_summary}

Applicant profile fields allowed for this email:
{json.dumps(applicant_fields, ensure_ascii=False, indent=2)}

Signature context:
{json.dumps(signature_context, ensure_ascii=False, indent=2)}

Style configuration:
- Language: {email_style_config.language}
- Academic level: {email_style_config.academic_level} ({_academic_level_description(email_style_config.academic_level)})
- Extra tone hint: {email_style_config.tone}
- Maximum email body words: {email_style_config.max_words}
- Include links: {email_style_config.include_links}
- Include phone: {email_style_config.include_phone}
- Include location: {email_style_config.include_location}
- Signature style: {email_style_config.signature_style}

Email rules:
- Write the email in {email_style_config.language}
- Keep the body under {email_style_config.max_words} words
- Apply the academic level and tone hint above
- Mention one specific detail from the company
- Mention 1-2 relevant candidate skills/projects
- Use only facts from the CV summary, website summary, and applicant profile fields above
- Do not exaggerate
- Do not claim experience that is not present in the CV
- Do not invent applicant links
- Do not invent applicant contact info
- Do not include empty fields
- Do not include phone or location unless they appear in Signature context
- Include selected links in the signature only if they appear in Signature context
- Signature style meanings:
  - compact: short signature with name and selected links
  - detailed: name, email, phone/location if present in Signature context, links on separate lines
  - minimal: name only, and omit the signature if no name is present
- Do not include placeholders
- Avoid robotic phrases like "I am writing to express my profound interest"
- Return ONLY valid JSON in this exact shape:
{{
  "subject": "...",
  "body": "..."
}}
""".strip()
    raw_output = generate_with_local_llm(prompt, temperature=0.4)
    return parse_generated_email(raw_output)


def parse_generated_email(text: str) -> GeneratedEmail:
    for candidate in (text, *_extract_json_objects(text)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            subject = str(parsed.get("subject", "")).strip()
            body = str(parsed.get("body", "")).strip()
            if subject and body:
                return GeneratedEmail(subject=subject, body=body)

    match = re.search(
        r"^\s*Subject:\s*(?P<subject>.+?)\s*\n+\s*Email:\s*(?P<body>.+?)\s*$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise HuntError(
            "Could not parse generated email as JSON or Subject/Email text. "
            f"Raw model output:\n{text}"
        )

    subject = match.group("subject").strip()
    body = match.group("body").strip()
    if not subject or not body:
        raise HuntError("Generated email is missing a subject or body.")
    return GeneratedEmail(subject=subject, body=body)


def _extract_json_objects(text: str) -> list[str]:
    start = text.find("{")
    if start == -1:
        return []

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
                return [text[start : index + 1]]
    return []
