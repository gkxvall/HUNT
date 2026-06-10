from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv


load_dotenv()

DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_EMAIL_LANGUAGE = "English"
DEFAULT_ACADEMIC_LEVEL = "B"
DEFAULT_EMAIL_TONE = "professional"
DEFAULT_EMAIL_MAX_WORDS = 180
DEFAULT_SIGNATURE_STYLE = "compact"

TRUE_VALUES = {"true", "1", "yes", "y", "on"}
FALSE_VALUES = {"false", "0", "no", "n", "off"}
SIGNATURE_STYLES = {"compact", "detailed", "minimal"}
PLACEHOLDER_VALUES = {
    "your_email@gmail.com",
    "your_gmail_app_password",
    "your-name",
    "your_name",
    "your-url",
}


def _clean_env(value: str | None) -> str:
    cleaned = (value or "").strip()
    if cleaned.lower() in PLACEHOLDER_VALUES:
        return ""
    return cleaned


def parse_bool(value: str | None, default: bool) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def parse_int(value: str | None, default: int) -> int:
    try:
        parsed = int((value or "").strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def normalize_academic_level(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    return normalized if normalized in {"A", "B", "C"} else DEFAULT_ACADEMIC_LEVEL


def normalize_signature_style(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in SIGNATURE_STYLES else DEFAULT_SIGNATURE_STYLE


@dataclass(frozen=True)
class EmailStyleConfig:
    language: str = DEFAULT_EMAIL_LANGUAGE
    academic_level: str = DEFAULT_ACADEMIC_LEVEL
    tone: str = DEFAULT_EMAIL_TONE
    max_words: int = DEFAULT_EMAIL_MAX_WORDS
    include_links: bool = True
    include_phone: bool = False
    include_location: bool = False
    signature_style: str = DEFAULT_SIGNATURE_STYLE


@dataclass(frozen=True)
class ApplicantProfile:
    full_name: str = ""
    phone: str = ""
    location: str = ""
    personal_email: str = ""
    portfolio_url: str = ""
    blog_url: str = ""
    github_url: str = ""
    linkedin_url: str = ""

    def to_prompt_dict(self, style_config: EmailStyleConfig) -> dict[str, str]:
        prompt_fields: dict[str, str] = {}
        if self.full_name:
            prompt_fields["full_name"] = self.full_name

        if style_config.signature_style == "detailed" and self.personal_email:
            prompt_fields["personal_email"] = self.personal_email

        if style_config.include_phone and self.phone:
            prompt_fields["phone"] = self.phone

        if style_config.include_location and self.location:
            prompt_fields["location"] = self.location

        if style_config.include_links and style_config.signature_style != "minimal":
            for key in ("portfolio_url", "blog_url", "github_url", "linkedin_url"):
                value = getattr(self, key)
                if value:
                    prompt_fields[key] = value

        return prompt_fields


@dataclass(frozen=True)
class AppConfig:
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    email_address: str = ""
    email_app_password: str = ""
    applicant_profile: ApplicantProfile = field(default_factory=ApplicantProfile)
    email_style: EmailStyleConfig = field(default_factory=EmailStyleConfig)


def build_signature_context(
    applicant_profile: ApplicantProfile,
    email_style_config: EmailStyleConfig,
) -> dict[str, Any]:
    if email_style_config.signature_style == "minimal":
        context: dict[str, Any] = {"style": "minimal"}
        if applicant_profile.full_name:
            context["full_name"] = applicant_profile.full_name
        return context

    context: dict[str, Any] = {"style": email_style_config.signature_style}
    profile_fields = applicant_profile.to_prompt_dict(email_style_config)

    for key in ("full_name", "personal_email", "phone", "location"):
        if key in profile_fields:
            context[key] = profile_fields[key]

    links = {
        key: profile_fields[key]
        for key in ("portfolio_url", "blog_url", "github_url", "linkedin_url")
        if key in profile_fields
    }
    if links:
        context["links"] = links

    return context


def load_config() -> AppConfig:
    language = _clean_env(os.getenv("EMAIL_LANGUAGE")) or DEFAULT_EMAIL_LANGUAGE
    tone = _clean_env(os.getenv("EMAIL_TONE")) or DEFAULT_EMAIL_TONE

    email_style = EmailStyleConfig(
        language=language,
        academic_level=normalize_academic_level(os.getenv("EMAIL_ACADEMIC_LEVEL")),
        tone=tone,
        max_words=parse_int(os.getenv("EMAIL_MAX_WORDS"), DEFAULT_EMAIL_MAX_WORDS),
        include_links=parse_bool(os.getenv("EMAIL_INCLUDE_LINKS"), True),
        include_phone=parse_bool(os.getenv("EMAIL_INCLUDE_PHONE"), False),
        include_location=parse_bool(os.getenv("EMAIL_INCLUDE_LOCATION"), False),
        signature_style=normalize_signature_style(os.getenv("EMAIL_SIGNATURE_STYLE")),
    )

    email_address = _clean_env(os.getenv("EMAIL_ADDRESS"))
    personal_email = _clean_env(os.getenv("APPLICANT_PERSONAL_EMAIL"))
    if not personal_email and email_style.signature_style == "detailed":
        personal_email = email_address

    profile = ApplicantProfile(
        full_name=_clean_env(os.getenv("APPLICANT_FULL_NAME")),
        phone=_clean_env(os.getenv("APPLICANT_PHONE")),
        location=_clean_env(os.getenv("APPLICANT_LOCATION")),
        personal_email=personal_email,
        portfolio_url=_clean_env(os.getenv("APPLICANT_PORTFOLIO_URL")),
        blog_url=_clean_env(os.getenv("APPLICANT_BLOG_URL")),
        github_url=_clean_env(os.getenv("APPLICANT_GITHUB_URL")),
        linkedin_url=_clean_env(os.getenv("APPLICANT_LINKEDIN_URL")),
    )

    return AppConfig(
        ollama_model=_clean_env(os.getenv("OLLAMA_MODEL")) or DEFAULT_OLLAMA_MODEL,
        email_address=email_address,
        email_app_password=_clean_env(os.getenv("EMAIL_APP_PASSWORD")),
        applicant_profile=profile,
        email_style=email_style,
    )
