from __future__ import annotations

import json
import re
from dataclasses import dataclass

from hunt.config import ApplicantInternshipPreferences, ApplicantProfile, EmailStyleConfig
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


def _length_description(length: str) -> str:
    descriptions = {
        "short": "aim for 150-220 words",
        "medium": "aim for 250-400 words",
        "long": "aim for 400-650 words",
    }
    return descriptions.get(length, descriptions["medium"])


def build_email_prompt(
    company_summary: str,
    candidate_summary: str,
    recipient_email: str,
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    email_style_config: EmailStyleConfig,
) -> str:
    applicant_fields = applicant_profile.to_prompt_dict(email_style_config)
    internship_fields = internship_preferences.to_prompt_dict(email_style_config)
    signature_context = applicant_profile.to_signature_dict(email_style_config)

    return f"""
Write a concise, natural internship application email to {recipient_email}.

Company summary:
{company_summary}

Candidate summary from CV:
{candidate_summary}

Applicant profile fields allowed for this email:
{json.dumps(applicant_fields, ensure_ascii=False, indent=2)}

Internship preferences allowed for this email:
{json.dumps(internship_fields, ensure_ascii=False, indent=2)}

Signature dictionary:
{json.dumps(signature_context, ensure_ascii=False, indent=2)}

Email style configuration:
{json.dumps(email_style_config.to_prompt_dict(), ensure_ascii=False, indent=2)}

Academic level guide:
- A: casual/simple student tone; direct, friendly, simple words, less formal, suitable for startups
- B: balanced professional tone; professional but natural, not too academic, not too casual
- C: highly academic/formal tone; more formal and structured, suitable for research labs, universities, academic internships, and R&D departments

Length guide:
- EMAIL_LENGTH={email_style_config.length}: {_length_description(email_style_config.length)}
- EMAIL_MAX_WORDS={email_style_config.max_words}: hard maximum for the email body

Information rules:
- Use only the company summary, candidate summary, applicant profile fields, internship preferences, and signature dictionary above.
- Do not invent details, links, contact info, achievements, grades, availability, or names.
- Omit missing information naturally.
- For stable personal info such as name, location, education, contact, GPA, and languages, prefer the applicant profile fields over the CV summary when both mention the same thing.
- For skills, projects, and experience, use both the CV summary and optional applicant highlights, but avoid duplicate mentions.
- If the same project appears in both the CV summary and applicant highlights, prefer the richer description.

Email rules:
- Write the email in {email_style_config.language}.
- Match academic level {email_style_config.academic_level}: {_academic_level_description(email_style_config.academic_level)}.
- Use this tone hint: {email_style_config.tone}.
- Match internship mode from internship preferences when present.
- Mention one specific detail from the company.
- Mention 1-2 relevant candidate skills, projects, or experience items.
- Mention GPA only if it appears in the allowed applicant profile fields.
- Mention availability only if it appears in the allowed internship preferences.
- Mention languages only if they appear in the allowed applicant profile fields.
- Mention university requirement only if it appears in the allowed internship preferences.
- Mention insurance only if it appears in the allowed internship preferences.
- Mention remote reason only if it appears in the allowed internship preferences.
- Mention CV attachment only if include_cv_attachment_note is true.
- Do not include phone, location, or links unless they appear in the signature dictionary or allowed applicant profile fields.
- Sign off using only the signature dictionary. Do not add empty labels.
- Do not include placeholders such as None, N/A, [your name], [portfolio], or similar text.

Subject rules:
- If include_subject_keywords is true, include exactly one relevant keyword in the subject, such as "AI Engineering", "Computer Vision", or "Machine Learning".
- If include_subject_keywords is false, use the simple subject "Internship Application".

Signature rules:
- minimal:
  Best regards,
  [Name if available]
- compact:
  Best regards,
  [Name if available]
  [GitHub/LinkedIn/Portfolio if enabled and available, concise single line]
- detailed:
  Best regards,
  [Name if available]
  Email: [email if available]
  Phone: [phone if enabled and available]
  Location: [location if enabled and available]
  Portfolio: [portfolio if enabled and available]
  GitHub: [github if enabled and available]
  LinkedIn: [linkedin if enabled and available]
- Do not include empty signature labels.

Return ONLY valid JSON in this exact shape:
{{
  "subject": "...",
  "body": "..."
}}
""".strip()


def write_email(
    company_summary: str,
    candidate_summary: str,
    recipient_email: str,
    applicant_profile: ApplicantProfile,
    internship_preferences: ApplicantInternshipPreferences,
    email_style_config: EmailStyleConfig,
) -> GeneratedEmail:
    prompt = build_email_prompt(
        company_summary,
        candidate_summary,
        recipient_email,
        applicant_profile,
        internship_preferences,
        email_style_config,
    )
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
