from __future__ import annotations

import re
from dataclasses import dataclass

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


def write_email(company_summary: str, candidate_summary: str, recipient_email: str) -> GeneratedEmail:
    prompt = f"""
Write a concise, natural internship application email to {recipient_email}.

Company summary:
{company_summary}

Candidate summary:
{candidate_summary}

Email rules:
- Under 180 words
- Professional but natural
- Mention one specific detail from the company
- Mention 1-2 relevant candidate skills/projects
- Do not exaggerate
- Do not claim experience that is not present in the CV
- Avoid robotic phrases like "I am writing to express my profound interest"
- Return ONLY the email in this exact format:

    Subject: <subject line here>

    Email:
        <email body here>

    Do not add explanations.
    Do not add markdown.
    Do not add bullet points.
    Do not wrap the answer in quotes.
""".strip()
    raw_output = generate_with_local_llm(prompt, temperature=0.4)
    return parse_generated_email(raw_output)


def parse_generated_email(text: str) -> GeneratedEmail:
    match = re.search(
        r"^\s*Subject:\s*(?P<subject>.+?)\s*\n+\s*Email:\s*(?P<body>.+?)\s*$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise HuntError("Could not parse generated email. Expected 'Subject:' and 'Email:' sections.")

    subject = match.group("subject").strip()
    body = match.group("body").strip()
    if not subject or not body:
        raise HuntError("Generated email is missing a subject or body.")
    return GeneratedEmail(subject=subject, body=body)
