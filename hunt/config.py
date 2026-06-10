from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv


DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_EMAIL_LANGUAGE = "English"
DEFAULT_ACADEMIC_LEVEL = "B"
DEFAULT_EMAIL_TONE = "professional"
DEFAULT_EMAIL_LENGTH = "medium"
DEFAULT_EMAIL_MAX_WORDS = 350
DEFAULT_EMAIL_FORMAT = "full"
DEFAULT_GREETING_STYLE = "team"
DEFAULT_SIGNATURE_STYLE = "compact"
BATCH_DEFAULT_DELAY_SECONDS = 20
BATCH_DEFAULT_LIMIT = 20
MIN_EMAIL_WORDS = 80
MAX_EMAIL_WORDS = 700

TRUE_VALUES = {"true", "1", "yes", "y", "on"}
FALSE_VALUES = {"false", "0", "no", "n", "off"}
PLACEHOLDER_VALUES = {
    "your_email@gmail.com",
    "your_gmail_app_password",
    "your_name",
    "your name",
    "your username",
    "your-url",
    "your url",
    "example.com",
    "n/a",
    "none",
}
INTERNSHIP_MODES = {"remote", "on-site", "hybrid", "flexible"}
INTERNSHIP_TYPES = {
    "internship",
    "summer internship",
    "mandatory internship",
    "voluntary internship",
    "research internship",
    "part-time internship",
}
EMAIL_LENGTHS = {"short", "medium", "long"}
EMAIL_FORMATS = {"compact", "full"}
GREETING_STYLES = {"team", "hiring-team", "recruiter", "formal"}
SIGNATURE_STYLES = {"minimal", "compact", "detailed"}
EMAIL_TONES = {
    "professional",
    "warm",
    "confident",
    "humble",
    "startup",
    "research-focused",
    "formal",
    "friendly",
}


def load_environment() -> str | None:
    env_path = find_dotenv(filename=".env", usecwd=True)
    if env_path:
        load_dotenv(env_path, override=True)
        return env_path

    project_root_env = Path(__file__).resolve().parent.parent / ".env"
    if project_root_env.exists():
        load_dotenv(project_root_env, override=True)
        return str(project_root_env)

    return None


def clean_env(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if cleaned.lower() in PLACEHOLDER_VALUES:
        return None
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
        return int((value or "").strip())
    except ValueError:
        return default


def parse_csv(value: str | None) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for raw_item in (value or "").split(","):
        item = clean_env(raw_item)
        if not item:
            continue
        dedupe_key = item.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(item)
    return items


def normalize_choice(value: str | None, allowed: set[str], default: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in allowed else default


def normalize_academic_level(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    return normalized if normalized in {"A", "B", "C"} else DEFAULT_ACADEMIC_LEVEL


def clamp_email_max_words(value: str | None) -> int:
    parsed = parse_int(value, DEFAULT_EMAIL_MAX_WORDS)
    return max(MIN_EMAIL_WORDS, min(MAX_EMAIL_WORDS, parsed))


def _omit_empty(data: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in data.items():
        if value is None or value == "" or value == [] or value == {}:
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


@dataclass(frozen=True)
class EmailStyleConfig:
    language: str = DEFAULT_EMAIL_LANGUAGE
    academic_level: str = DEFAULT_ACADEMIC_LEVEL
    tone: str = DEFAULT_EMAIL_TONE
    length: str = DEFAULT_EMAIL_LENGTH
    max_words: int = DEFAULT_EMAIL_MAX_WORDS
    email_format: str = DEFAULT_EMAIL_FORMAT
    greeting_style: str = DEFAULT_GREETING_STYLE
    signature_style: str = DEFAULT_SIGNATURE_STYLE
    include_subject_keywords: bool = True
    include_cv_attachment_note: bool = True
    include_university_requirement: bool = True
    include_insurance_note: bool = True
    include_links: bool = True
    include_phone: bool = False
    include_location: bool = False
    include_gpa: bool = False
    include_languages: bool = False
    include_availability: bool = False
    include_remote_reason: bool = True

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "academic_level": self.academic_level,
            "tone": self.tone,
            "length": self.length,
            "max_words": self.max_words,
            "email_format": self.email_format,
            "greeting_style": self.greeting_style,
            "signature_style": self.signature_style,
            "include_subject_keywords": self.include_subject_keywords,
            "include_cv_attachment_note": self.include_cv_attachment_note,
            "include_university_requirement": self.include_university_requirement,
            "include_insurance_note": self.include_insurance_note,
            "include_links": self.include_links,
            "include_phone": self.include_phone,
            "include_location": self.include_location,
            "include_gpa": self.include_gpa,
            "include_languages": self.include_languages,
            "include_availability": self.include_availability,
            "include_remote_reason": self.include_remote_reason,
        }


@dataclass(frozen=True)
class ApplicantIdentity:
    full_name: str | None = None
    preferred_name: str | None = None
    nationality: str | None = None
    current_location: str | None = None
    timezone: str | None = None
    short_bio: str | None = None


@dataclass(frozen=True)
class ApplicantContact:
    personal_email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    telegram: str | None = None
    discord: str | None = None


@dataclass(frozen=True)
class ApplicantLinks:
    portfolio_url: str | None = None
    blog_url: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    kaggle_url: str | None = None
    google_scholar_url: str | None = None
    orcid_url: str | None = None
    medium_url: str | None = None
    devto_url: str | None = None
    youtube_url: str | None = None
    personal_website_url: str | None = None


@dataclass(frozen=True)
class ApplicantEducation:
    university: str | None = None
    faculty: str | None = None
    department: str | None = None
    degree: str | None = None
    year_level: str | None = None
    expected_graduation: str | None = None
    gpa: str | None = None
    gpa_scale: str | None = None
    relevant_coursework: list[str] = field(default_factory=list)
    academic_advisor: str | None = None
    university_country: str | None = None
    university_city: str | None = None


@dataclass(frozen=True)
class ApplicantSkillsAndInterests:
    main_interests: list[str] = field(default_factory=list)
    technical_skills: list[str] = field(default_factory=list)
    programming_languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    research_interests: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ApplicantProject:
    name: str | None = None
    url: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ApplicantExperience:
    title: str | None = None
    organization: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ApplicantInternshipPreferences:
    mode: str = "remote"
    internship_type: str = "internship"
    field_preferences: list[str] = field(default_factory=list)
    target_roles: list[str] = field(default_factory=list)
    availability_start: str | None = None
    availability_end: str | None = None
    duration: str | None = None
    hours_per_week: str | None = None
    relocation_open: bool = False
    work_authorization: str | None = None
    visa_status: str | None = None
    university_requirement: bool = True
    insurance_covered_by_university: bool = True
    remote_reason: str | None = None
    note: str | None = None

    def to_prompt_dict(self, style_config: EmailStyleConfig) -> dict[str, Any]:
        data: dict[str, Any] = {
            "mode": self.mode,
            "internship_type": self.internship_type,
            "field_preferences": self.field_preferences,
            "target_roles": self.target_roles,
            "duration": self.duration,
            "hours_per_week": self.hours_per_week,
            "relocation_open": self.relocation_open,
            "work_authorization": self.work_authorization,
            "visa_status": self.visa_status,
            "note": self.note,
        }
        if style_config.include_availability:
            data["availability_start"] = self.availability_start
            data["availability_end"] = self.availability_end
        if style_config.include_university_requirement:
            data["university_requirement"] = self.university_requirement
        if style_config.include_insurance_note:
            data["insurance_covered_by_university"] = self.insurance_covered_by_university
        if style_config.include_remote_reason:
            data["remote_reason"] = self.remote_reason
        return _omit_empty(data)


@dataclass(frozen=True)
class ApplicantProfile:
    identity: ApplicantIdentity = field(default_factory=ApplicantIdentity)
    contact: ApplicantContact = field(default_factory=ApplicantContact)
    links: ApplicantLinks = field(default_factory=ApplicantLinks)
    education: ApplicantEducation = field(default_factory=ApplicantEducation)
    skills: ApplicantSkillsAndInterests = field(default_factory=ApplicantSkillsAndInterests)
    projects: list[ApplicantProject] = field(default_factory=list)
    experiences: list[ApplicantExperience] = field(default_factory=list)

    def to_prompt_dict(self, style_config: EmailStyleConfig) -> dict[str, Any]:
        identity = _omit_empty(asdict(self.identity))
        if not style_config.include_location:
            identity.pop("current_location", None)
        contact: dict[str, Any] = {}
        if self.contact.personal_email and style_config.signature_style == "detailed":
            contact["personal_email"] = self.contact.personal_email
        if style_config.include_phone and self.contact.phone:
            contact["phone"] = self.contact.phone

        links = _omit_empty(asdict(self.links)) if style_config.include_links else {}
        education = _omit_empty(asdict(self.education))
        if not style_config.include_gpa:
            education.pop("gpa", None)
            education.pop("gpa_scale", None)

        skills = _omit_empty(asdict(self.skills))
        if not style_config.include_languages:
            skills.pop("languages", None)

        projects = [_omit_empty(asdict(project)) for project in self.projects]
        experiences = [_omit_empty(asdict(experience)) for experience in self.experiences]

        data = {
            "identity": identity,
            "contact": contact,
            "links": links,
            "education": education,
            "skills_and_interests": skills,
            "projects": [project for project in projects if project],
            "experience_highlights": [experience for experience in experiences if experience],
        }
        return _omit_empty(data)

    def to_signature_dict(self, style_config: EmailStyleConfig) -> dict[str, Any]:
        data: dict[str, Any] = {"style": style_config.signature_style}
        name = self.identity.full_name or self.identity.preferred_name
        if name:
            data["name"] = name

        if style_config.signature_style == "minimal":
            return _omit_empty(data)

        if style_config.signature_style == "detailed" and self.contact.personal_email:
            data["email"] = self.contact.personal_email
        if style_config.include_phone and self.contact.phone:
            data["phone"] = self.contact.phone
        if style_config.include_location and self.identity.current_location:
            data["location"] = self.identity.current_location

        if style_config.include_links:
            link_keys = (
                "portfolio_url",
                "github_url",
                "linkedin_url",
                "blog_url",
                "kaggle_url",
                "google_scholar_url",
                "orcid_url",
                "medium_url",
                "devto_url",
                "youtube_url",
                "personal_website_url",
            )
            links = {
                key: value
                for key in link_keys
                if (value := getattr(self.links, key)) is not None
            }
            if links:
                data["links"] = links

        return _omit_empty(data)


@dataclass(frozen=True)
class AppConfig:
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    email_address: str | None = None
    email_app_password: str | None = None
    env_path: str | None = None
    applicant_profile: ApplicantProfile = field(default_factory=ApplicantProfile)
    internship_preferences: ApplicantInternshipPreferences = field(
        default_factory=ApplicantInternshipPreferences
    )
    email_style: EmailStyleConfig = field(default_factory=EmailStyleConfig)
    batch_default_delay_seconds: int = BATCH_DEFAULT_DELAY_SECONDS
    batch_default_limit: int = BATCH_DEFAULT_LIMIT
    batch_allow_duplicates: bool = False
    batch_skip_existing: bool = True
    batch_save_drafts: bool = True


def build_signature_context(
    applicant_profile: ApplicantProfile,
    email_style_config: EmailStyleConfig,
) -> dict[str, Any]:
    return applicant_profile.to_signature_dict(email_style_config)


def load_config() -> AppConfig:
    env_path = load_environment()
    email_style = EmailStyleConfig(
        language=clean_env(os.getenv("EMAIL_LANGUAGE")) or DEFAULT_EMAIL_LANGUAGE,
        academic_level=normalize_academic_level(os.getenv("EMAIL_ACADEMIC_LEVEL")),
        tone=normalize_choice(os.getenv("EMAIL_TONE"), EMAIL_TONES, DEFAULT_EMAIL_TONE),
        length=normalize_choice(os.getenv("EMAIL_LENGTH"), EMAIL_LENGTHS, DEFAULT_EMAIL_LENGTH),
        max_words=clamp_email_max_words(os.getenv("EMAIL_MAX_WORDS")),
        email_format=normalize_choice(os.getenv("EMAIL_FORMAT"), EMAIL_FORMATS, DEFAULT_EMAIL_FORMAT),
        greeting_style=normalize_choice(
            os.getenv("EMAIL_GREETING_STYLE"), GREETING_STYLES, DEFAULT_GREETING_STYLE
        ),
        signature_style=normalize_choice(
            os.getenv("EMAIL_SIGNATURE_STYLE"), SIGNATURE_STYLES, DEFAULT_SIGNATURE_STYLE
        ),
        include_subject_keywords=parse_bool(os.getenv("EMAIL_INCLUDE_SUBJECT_KEYWORDS"), True),
        include_cv_attachment_note=parse_bool(os.getenv("EMAIL_INCLUDE_CV_ATTACHMENT_NOTE"), True),
        include_university_requirement=parse_bool(
            os.getenv("EMAIL_INCLUDE_UNIVERSITY_REQUIREMENT"), True
        ),
        include_insurance_note=parse_bool(os.getenv("EMAIL_INCLUDE_INSURANCE_NOTE"), True),
        include_links=parse_bool(os.getenv("EMAIL_INCLUDE_LINKS"), True),
        include_phone=parse_bool(os.getenv("EMAIL_INCLUDE_PHONE"), False),
        include_location=parse_bool(os.getenv("EMAIL_INCLUDE_LOCATION"), False),
        include_gpa=parse_bool(os.getenv("EMAIL_INCLUDE_GPA"), False),
        include_languages=parse_bool(os.getenv("EMAIL_INCLUDE_LANGUAGES"), False),
        include_availability=parse_bool(os.getenv("EMAIL_INCLUDE_AVAILABILITY"), False),
        include_remote_reason=parse_bool(os.getenv("EMAIL_INCLUDE_REMOTE_REASON"), True),
    )

    profile = ApplicantProfile(
        identity=ApplicantIdentity(
            full_name=clean_env(os.getenv("APPLICANT_FULL_NAME")),
            preferred_name=clean_env(os.getenv("APPLICANT_PREFERRED_NAME")),
            nationality=clean_env(os.getenv("APPLICANT_NATIONALITY")),
            current_location=clean_env(os.getenv("APPLICANT_CURRENT_LOCATION"))
            or clean_env(os.getenv("APPLICANT_LOCATION")),
            timezone=clean_env(os.getenv("APPLICANT_TIMEZONE")),
            short_bio=clean_env(os.getenv("APPLICANT_SHORT_BIO")),
        ),
        contact=ApplicantContact(
            personal_email=clean_env(os.getenv("APPLICANT_PERSONAL_EMAIL")),
            phone=clean_env(os.getenv("APPLICANT_PHONE")),
            whatsapp=clean_env(os.getenv("APPLICANT_WHATSAPP")),
            telegram=clean_env(os.getenv("APPLICANT_TELEGRAM")),
            discord=clean_env(os.getenv("APPLICANT_DISCORD")),
        ),
        links=ApplicantLinks(
            portfolio_url=clean_env(os.getenv("APPLICANT_PORTFOLIO_URL")),
            blog_url=clean_env(os.getenv("APPLICANT_BLOG_URL")),
            github_url=clean_env(os.getenv("APPLICANT_GITHUB_URL")),
            linkedin_url=clean_env(os.getenv("APPLICANT_LINKEDIN_URL")),
            kaggle_url=clean_env(os.getenv("APPLICANT_KAGGLE_URL")),
            google_scholar_url=clean_env(os.getenv("APPLICANT_GOOGLE_SCHOLAR_URL")),
            orcid_url=clean_env(os.getenv("APPLICANT_ORCID_URL")),
            medium_url=clean_env(os.getenv("APPLICANT_MEDIUM_URL")),
            devto_url=clean_env(os.getenv("APPLICANT_DEVTO_URL")),
            youtube_url=clean_env(os.getenv("APPLICANT_YOUTUBE_URL")),
            personal_website_url=clean_env(os.getenv("APPLICANT_PERSONAL_WEBSITE_URL")),
        ),
        education=ApplicantEducation(
            university=clean_env(os.getenv("APPLICANT_UNIVERSITY")),
            faculty=clean_env(os.getenv("APPLICANT_FACULTY")),
            department=clean_env(os.getenv("APPLICANT_DEPARTMENT")),
            degree=clean_env(os.getenv("APPLICANT_DEGREE")),
            year_level=clean_env(os.getenv("APPLICANT_YEAR_LEVEL")),
            expected_graduation=clean_env(os.getenv("APPLICANT_EXPECTED_GRADUATION")),
            gpa=clean_env(os.getenv("APPLICANT_GPA")),
            gpa_scale=clean_env(os.getenv("APPLICANT_GPA_SCALE")),
            relevant_coursework=parse_csv(os.getenv("APPLICANT_RELEVANT_COURSEWORK")),
            academic_advisor=clean_env(os.getenv("APPLICANT_ACADEMIC_ADVISOR")),
            university_country=clean_env(os.getenv("APPLICANT_UNIVERSITY_COUNTRY")),
            university_city=clean_env(os.getenv("APPLICANT_UNIVERSITY_CITY")),
        ),
        skills=ApplicantSkillsAndInterests(
            main_interests=parse_csv(os.getenv("APPLICANT_MAIN_INTERESTS")),
            technical_skills=parse_csv(os.getenv("APPLICANT_TECHNICAL_SKILLS")),
            programming_languages=parse_csv(os.getenv("APPLICANT_PROGRAMMING_LANGUAGES")),
            frameworks=parse_csv(os.getenv("APPLICANT_FRAMEWORKS")),
            tools=parse_csv(os.getenv("APPLICANT_TOOLS")),
            research_interests=parse_csv(os.getenv("APPLICANT_RESEARCH_INTERESTS")),
            soft_skills=parse_csv(os.getenv("APPLICANT_SOFT_SKILLS")),
            languages=parse_csv(os.getenv("APPLICANT_LANGUAGES")),
        ),
        projects=[
            project
            for project in (
                _load_project(1),
                _load_project(2),
                _load_project(3),
            )
            if _omit_empty(asdict(project))
        ],
        experiences=[
            experience
            for experience in (
                _load_experience(1),
                _load_experience(2),
            )
            if _omit_empty(asdict(experience))
        ],
    )

    internship_preferences = ApplicantInternshipPreferences(
        mode=normalize_choice(os.getenv("INTERNSHIP_MODE"), INTERNSHIP_MODES, "remote"),
        internship_type=normalize_choice(
            os.getenv("INTERNSHIP_TYPE"), INTERNSHIP_TYPES, "internship"
        ),
        field_preferences=parse_csv(os.getenv("INTERNSHIP_FIELD_PREFERENCES")),
        target_roles=parse_csv(os.getenv("INTERNSHIP_TARGET_ROLES")),
        availability_start=clean_env(os.getenv("INTERNSHIP_AVAILABILITY_START")),
        availability_end=clean_env(os.getenv("INTERNSHIP_AVAILABILITY_END")),
        duration=clean_env(os.getenv("INTERNSHIP_DURATION")),
        hours_per_week=clean_env(os.getenv("INTERNSHIP_HOURS_PER_WEEK")),
        relocation_open=parse_bool(os.getenv("INTERNSHIP_RELOCATION_OPEN"), False),
        work_authorization=clean_env(os.getenv("INTERNSHIP_WORK_AUTHORIZATION")),
        visa_status=clean_env(os.getenv("INTERNSHIP_VISA_STATUS")),
        university_requirement=parse_bool(os.getenv("INTERNSHIP_UNIVERSITY_REQUIREMENT"), True),
        insurance_covered_by_university=parse_bool(
            os.getenv("INTERNSHIP_INSURANCE_COVERED_BY_UNIVERSITY"), True
        ),
        remote_reason=clean_env(os.getenv("INTERNSHIP_REMOTE_REASON")),
        note=clean_env(os.getenv("INTERNSHIP_NOTE")),
    )

    return AppConfig(
        ollama_model=clean_env(os.getenv("OLLAMA_MODEL")) or DEFAULT_OLLAMA_MODEL,
        email_address=clean_env(os.getenv("EMAIL_ADDRESS")),
        email_app_password=clean_env(os.getenv("EMAIL_APP_PASSWORD")),
        env_path=env_path,
        applicant_profile=profile,
        internship_preferences=internship_preferences,
        email_style=email_style,
        batch_default_delay_seconds=max(0, parse_int(os.getenv("BATCH_DEFAULT_DELAY_SECONDS"), BATCH_DEFAULT_DELAY_SECONDS)),
        batch_default_limit=max(1, parse_int(os.getenv("BATCH_DEFAULT_LIMIT"), BATCH_DEFAULT_LIMIT)),
        batch_allow_duplicates=parse_bool(os.getenv("BATCH_ALLOW_DUPLICATES"), False),
        batch_skip_existing=parse_bool(os.getenv("BATCH_SKIP_EXISTING"), True),
        batch_save_drafts=parse_bool(os.getenv("BATCH_SAVE_DRAFTS"), True),
    )


def config_snapshot(config: AppConfig) -> dict[str, Any]:
    return {
        "env_path": config.env_path,
        "ollama_model": config.ollama_model,
        "sender_email_masked": mask_email(config.email_address),
        "email_style": config.email_style.to_prompt_dict(),
        "batch": {
            "default_delay_seconds": config.batch_default_delay_seconds,
            "default_limit": config.batch_default_limit,
            "allow_duplicates": config.batch_allow_duplicates,
            "skip_existing": config.batch_skip_existing,
            "save_drafts": config.batch_save_drafts,
        },
        "applicant_profile_prompt": config.applicant_profile.to_prompt_dict(config.email_style),
        "signature": config.applicant_profile.to_signature_dict(config.email_style),
        "internship_preferences": config.internship_preferences.to_prompt_dict(config.email_style),
    }


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***" if local else "***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def env_example_warnings(path: Path | None = None) -> list[str]:
    env_example = path or Path(__file__).resolve().parent.parent / ".env.example"
    if not env_example.exists():
        return []

    suspicious_prefixes = ("APPLICANT_",)
    warnings: list[str] = []
    for line in env_example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        value = raw_value.split("#", 1)[0].strip()
        if key.startswith(suspicious_prefixes) and clean_env(value):
            warnings.append(
                ".env.example may contain real applicant info. Keep example applicant fields empty."
            )
            break
    return warnings


def _load_project(index: int) -> ApplicantProject:
    prefix = f"APPLICANT_TOP_PROJECT_{index}"
    return ApplicantProject(
        name=clean_env(os.getenv(f"{prefix}_NAME")),
        url=clean_env(os.getenv(f"{prefix}_URL")),
        description=clean_env(os.getenv(f"{prefix}_DESCRIPTION")),
    )


def _load_experience(index: int) -> ApplicantExperience:
    prefix = f"APPLICANT_TOP_EXPERIENCE_{index}"
    return ApplicantExperience(
        title=clean_env(os.getenv(f"{prefix}_TITLE")),
        organization=clean_env(os.getenv(f"{prefix}_ORGANIZATION")),
        description=clean_env(os.getenv(f"{prefix}_DESCRIPTION")),
    )
