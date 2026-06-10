from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from hunt.config import AppConfig
from hunt.cv_reader import read_cv
from hunt.email_sender import send_email
from hunt.email_writer import (
    GeneratedEmail,
    build_fallback_email,
    build_generation_warnings,
    merge_candidate_context,
    summarize_candidate,
    summarize_company,
    write_email,
)
from hunt.json_utils import LLMJsonParseError, body_looks_invalid, sanitize_email_body, validate_email_output
from hunt.tracker import (
    application_exists,
    create_batch_item,
    create_batch_run,
    finish_batch_run,
    save_application,
    update_status,
    update_batch_item,
)
from hunt.utils import HuntError, ensure_existing_file
from hunt.website_reader import extract_website_text


REQUIRED_COLUMNS = {"website", "email"}
RESULT_FIELDS = [
    "row_index",
    "company_name",
    "website",
    "email",
    "status",
    "subject",
    "error",
    "draft_path",
    "application_id",
]


@dataclass
class BatchRow:
    row_index: int
    company_name: str
    website: str
    email: str
    notes: str = ""
    role: str = ""
    language: str = ""
    internship_mode: str = ""
    status: str = "pending"
    error: str = ""


@dataclass
class BatchResult:
    row_index: int
    company_name: str
    website: str
    email: str
    status: str
    subject: str = ""
    error: str = ""
    draft_path: str = ""
    application_id: int | None = None


@dataclass
class BatchSummary:
    batch_run_id: int | None
    results: list[BatchResult]
    stopped: bool = False

    @property
    def sent_count(self) -> int:
        return sum(1 for result in self.results if result.status == "sent")

    @property
    def draft_count(self) -> int:
        return sum(1 for result in self.results if result.status == "drafted")

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status in {"skipped", "duplicate", "invalid"})

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "failed")


ConfirmCallback = Callable[[BatchRow, GeneratedEmail], str]
PreviewCallback = Callable[[BatchRow, GeneratedEmail, list[str]], None]
ProgressCallback = Callable[[str], None]


def is_valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def is_valid_website(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def read_batch_csv(csv_path: str | Path) -> list[BatchRow]:
    path = Path(csv_path)
    if not path.exists():
        raise HuntError(f"Batch CSV not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise HuntError("Batch CSV is empty.")
        normalized = [name.strip().lower() for name in reader.fieldnames]
        missing = REQUIRED_COLUMNS - set(normalized)
        if missing:
            raise HuntError(f"Batch CSV missing required columns: {', '.join(sorted(missing))}")

        rows: list[BatchRow] = []
        for index, raw_row in enumerate(reader):
            row = {str(key).strip().lower(): (value or "").strip() for key, value in raw_row.items()}
            rows.append(
                BatchRow(
                    row_index=index,
                    company_name=row.get("company_name", ""),
                    website=row.get("website", ""),
                    email=row.get("email", ""),
                    notes=row.get("notes", ""),
                    role=row.get("role", ""),
                    language=row.get("language", ""),
                    internship_mode=row.get("internship_mode", ""),
                    status=row.get("status", "pending") or "pending",
                )
            )
    return rows


def validate_batch_rows(
    rows: list[BatchRow],
    allow_duplicates: bool = False,
) -> list[BatchRow]:
    seen: set[tuple[str, str]] = set()
    validated: list[BatchRow] = []
    for row in rows:
        if not is_valid_email(row.email):
            row.status = "invalid"
            row.error = "Invalid email"
        elif not is_valid_website(row.website):
            row.status = "invalid"
            row.error = "Invalid website URL"
        else:
            key = (row.email.lower(), row.website.rstrip("/").lower())
            if not allow_duplicates and key in seen:
                row.status = "duplicate"
                row.error = "Duplicate email/website in batch"
            else:
                seen.add(key)
                row.status = "pending"
        validated.append(row)
    return validated


def select_rows(rows: list[BatchRow], start_at: int = 0, limit: int | None = None) -> list[BatchRow]:
    selected = [row for row in rows if row.row_index >= start_at]
    return selected[:limit] if limit is not None else selected


def save_draft(
    row: BatchRow,
    subject: str,
    body: str,
    cv_path: str,
    status: str = "drafted",
    drafts_dir: Path | str = Path("data") / "drafts",
) -> Path:
    directory = Path(drafts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().date().isoformat()
    company = _slug(row.company_name or urlparse(row.website).netloc or "company")
    email_slug = _slug(row.email.replace("@", "_at_"))
    path = directory / f"{date_prefix}_{company}_{email_slug}.md"
    path.write_text(
        "\n".join(
            [
                "---",
                f"company_name: {row.company_name}",
                f"website: {row.website}",
                f"email: {row.email}",
                f"status: {status}",
                f"created_at: {datetime.now().isoformat(timespec='seconds')}",
                "---",
                "",
                f"Subject: {subject}",
                "",
                "Email:",
                body,
                "",
                "CV attachment:",
                cv_path,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def update_results_csv(output_path: str | Path, results: list[BatchResult]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "row_index": result.row_index,
                    "company_name": result.company_name,
                    "website": result.website,
                    "email": result.email,
                    "status": result.status,
                    "subject": result.subject,
                    "error": result.error,
                    "draft_path": result.draft_path,
                    "application_id": result.application_id or "",
                }
            )


def quality_check_email(
    subject: str,
    body: str,
    row: BatchRow,
    config: AppConfig,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings = validate_email_output(subject, body, config.email_style.max_words)
    if not subject.strip():
        errors.append("Subject is empty")
    if not body.strip():
        errors.append("Body is empty")
    if body_looks_invalid(body, config.email_style.language):
        errors.append("Body contains raw JSON, control tokens, code fences, or suspicious junk")
    if not is_valid_email(row.email):
        errors.append("Invalid recipient email")
    if not is_valid_website(row.website):
        errors.append("Invalid website URL")
    return errors, warnings


def process_batch(
    csv_path: str,
    cv_path: str,
    config: AppConfig,
    *,
    send: bool = False,
    draft_only: bool = False,
    yes: bool = False,
    limit: int | None = None,
    start_at: int = 0,
    delay: int | None = None,
    skip_existing: bool = True,
    dry_run: bool = False,
    output: str = "data/batch_results.csv",
    allow_duplicates: bool = False,
    use_cache: bool = False,
    confirm_callback: ConfirmCallback | None = None,
    preview_callback: PreviewCallback | None = None,
    progress_callback: ProgressCallback | None = None,
    db_path: Path | str | None = None,
) -> BatchSummary:
    ensure_existing_file(cv_path)
    rows = validate_batch_rows(read_batch_csv(csv_path), allow_duplicates=allow_duplicates)
    selected = select_rows(rows, start_at=start_at, limit=limit)
    results: list[BatchResult] = []

    if dry_run:
        for row in selected:
            results.append(_row_result(row, row.status, row.error))
        update_results_csv(output, results)
        return BatchSummary(batch_run_id=None, results=results)

    db_kwargs = {"db_path": db_path} if db_path is not None else {}
    batch_run_id = create_batch_run(csv_path, cv_path, len(selected), **db_kwargs)
    website_cache: dict[str, str] = {}
    cv_text = ""
    candidate_summary: dict[str, object] = {}
    processed = sent = drafted = skipped = failed = 0
    stopped = False

    try:
        cv_text = read_cv(cv_path)
        candidate_summary = summarize_candidate(cv_text, config.ollama_model)
        for position, row in enumerate(selected, start=1):
            row_config = _config_for_row(config, row)
            if progress_callback:
                progress_callback(f"[{position}/{len(selected)}] Processing {row.company_name or row.website} <{row.email}>")

            item_id = create_batch_item(
                batch_run_id,
                row.row_index,
                row.company_name,
                row.website,
                row.email,
                row.role,
                row.notes,
                status=row.status if row.status in {"invalid", "duplicate"} else "pending",
                error=row.error,
                **db_kwargs,
            )

            if row.status in {"invalid", "duplicate"}:
                result = _row_result(row, row.status, row.error)
                results.append(result)
                update_results_csv(output, results)
                skipped += 1
                continue

            if skip_existing and application_exists(row.website, row.email, {"sent", "previewed"}, **db_kwargs):
                update_batch_item(item_id, "skipped", error="Existing application found", **db_kwargs)
                result = _row_result(row, "skipped", "Existing application found")
                results.append(result)
                update_results_csv(output, results)
                skipped += 1
                continue

            try:
                if progress_callback:
                    progress_callback("Reading website...")
                website_text = website_cache.get(row.website) if use_cache else None
                if website_text is None:
                    website_text = extract_website_text(row.website)
                    website_cache[row.website] = website_text

                if progress_callback:
                    progress_callback("Generating email...")
                company_summary = summarize_company(website_text, config.ollama_model)
                company_summary = _apply_row_context(company_summary, row)
                subject, body = write_email(
                    company_summary,
                    candidate_summary,
                    row.email,
                    row_config.applicant_profile,
                    row_config.internship_preferences,
                    row_config.email_style,
                    config.ollama_model,
                )
            except (HuntError, LLMJsonParseError):
                company_summary = {"company_name": row.company_name, "what_company_does": row.notes}
                candidate_context = merge_candidate_context(candidate_summary, row_config.applicant_profile, row_config.email_style)
                subject, body = build_fallback_email(company_summary, candidate_context, row_config)

            body = sanitize_email_body(body, row_config.email_style.language)
            errors, warnings = quality_check_email(subject, body, row, row_config)
            if send and yes and warnings:
                errors.append("Quality warnings present in unattended send mode: " + "; ".join(warnings))
            if errors:
                error = "; ".join(errors)
                update_batch_item(item_id, "failed", subject=subject, body=body, error=error, **db_kwargs)
                result = _row_result(row, "failed", error, subject=subject)
                results.append(result)
                update_results_csv(output, results)
                failed += 1
                continue

            application_id = save_application(row.website, row.email, subject, body, status="previewed", **db_kwargs)
            draft_path = ""
            if config.batch_save_drafts or draft_only or not send:
                draft_path = str(save_draft(row, subject, body, cv_path, status="drafted"))
            update_batch_item(item_id, "drafted", subject=subject, body=body, error="; ".join(warnings), **db_kwargs)
            result = _row_result(row, "drafted", "; ".join(warnings), subject, draft_path, application_id)

            generated = GeneratedEmail(subject=subject, body=body)
            if preview_callback:
                preview_callback(row, generated, warnings)

            if send and not draft_only:
                action = "SEND" if yes else (confirm_callback(row, generated) if confirm_callback else "SKIP")
                action = action.strip().upper()
                if action == "QUIT":
                    stopped = True
                    result.status = "skipped"
                    result.error = "Batch stopped by user"
                    update_batch_item(item_id, "skipped", subject=subject, body=body, error=result.error, **db_kwargs)
                    results.append(result)
                    update_results_csv(output, results)
                    skipped += 1
                    break
                if action == "SKIP":
                    result.status = "skipped"
                    result.error = "Skipped by user"
                    update_batch_item(item_id, "skipped", subject=subject, body=body, error=result.error, **db_kwargs)
                    skipped += 1
                elif action == "EDIT":
                    drafted += 1
                elif action == "SEND":
                    if not Path(cv_path).exists():
                        result.status = "failed"
                        result.error = "CV attachment missing"
                        update_batch_item(item_id, "failed", subject=subject, body=body, error=result.error, **db_kwargs)
                        failed += 1
                    else:
                        send_email(config.email_address or "", config.email_app_password or "", row.email, subject, body, attachment_path=cv_path)
                        result.status = "sent"
                        update_batch_item(item_id, "sent", subject=subject, body=body, **db_kwargs)
                        update_status(application_id, "sent", **db_kwargs)
                        sent += 1
                        if delay and delay > 0:
                            time.sleep(delay)
                else:
                    result.status = "skipped"
                    result.error = "Unknown action"
                    update_batch_item(item_id, "skipped", subject=subject, body=body, error=result.error, **db_kwargs)
                    skipped += 1
            else:
                drafted += 1

            results.append(result)
            update_results_csv(output, results)
            processed += 1
    except KeyboardInterrupt:
        stopped = True
    finally:
        finish_batch_run(
            batch_run_id,
            "stopped" if stopped else "completed",
            processed,
            sent,
            drafted,
            skipped,
            failed,
            **db_kwargs,
        )
        update_results_csv(output, results)

    return BatchSummary(batch_run_id=batch_run_id, results=results, stopped=stopped)


def _row_result(
    row: BatchRow,
    status: str,
    error: str = "",
    subject: str = "",
    draft_path: str = "",
    application_id: int | None = None,
) -> BatchResult:
    return BatchResult(
        row_index=row.row_index,
        company_name=row.company_name,
        website=row.website,
        email=row.email,
        status=status,
        subject=subject,
        error=error,
        draft_path=draft_path,
        application_id=application_id,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "company"


def _config_for_row(config: AppConfig, row: BatchRow) -> AppConfig:
    email_style = config.email_style
    internship_preferences = config.internship_preferences
    if row.language:
        email_style = replace(email_style, language=row.language)
    if row.internship_mode:
        internship_preferences = replace(internship_preferences, mode=row.internship_mode)
    return replace(config, email_style=email_style, internship_preferences=internship_preferences)


def _apply_row_context(company_summary: dict[str, object], row: BatchRow) -> dict[str, object]:
    enriched = dict(company_summary)
    if row.company_name and not enriched.get("company_name"):
        enriched["company_name"] = row.company_name
    if row.notes:
        enriched["batch_notes"] = row.notes
    if row.role:
        enriched["target_role"] = row.role
    return enriched
