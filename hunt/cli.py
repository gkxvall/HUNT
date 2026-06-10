from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hunt.config import AppConfig, config_snapshot, env_example_warnings, load_config, mask_email
from hunt.cv_reader import read_cv
from hunt.email_sender import send_email
from hunt.email_writer import (
    GeneratedEmail,
    build_email_prompt,
    build_generation_warnings,
    build_prompt_snapshot,
    summarize_candidate,
    summarize_company,
    write_email,
)
from hunt.json_utils import LLMJsonParseError
from hunt.local_llm import check_ollama_connection
from hunt.tracker import list_applications, save_application, update_status
from hunt.utils import HuntError
from hunt.website_reader import extract_website_text


app = typer.Typer(help="HUNT: local AI-powered internship application assistant.")
console = Console()
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _show_error(message: str) -> None:
    console.print(Panel(message, title="HUNT Error", border_style="red"))


def _mask_email(email: str | None) -> str:
    return mask_email(email)


def _flatten_preview_fields(data: dict[str, object], prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, value in data.items():
        label = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(_flatten_preview_fields(value, label))
        elif isinstance(value, list):
            rows.append((label, ", ".join(str(item) for item in value)))
        else:
            rows.append((label, str(value)))
    return rows


def _render_profile_used(config: AppConfig) -> None:
    profile_used = config.applicant_profile.to_prompt_dict(config.email_style)
    signature_used = config.applicant_profile.to_signature_dict(config.email_style)
    signature_profile_fields = {
        key: value for key, value in signature_used.items() if key != "style"
    }
    rows = _flatten_preview_fields(
        {"profile": profile_used, "signature": signature_profile_fields}
    )
    if not rows:
        return

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for field, value in rows:
        table.add_row(field, value)
    console.print(Panel(table, title="Profile Used", border_style="blue"))


def _render_warnings(warnings: list[str]) -> None:
    if not warnings:
        return
    console.print(
        Panel(
            "\n".join(f"- {warning}" for warning in warnings),
            title="Generation Warnings",
            border_style="yellow",
        )
    )


def _render_preview(
    website: str,
    recipient_email: str,
    subject: str,
    body: str,
    config: AppConfig,
) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Company website", website)
    table.add_row("To", recipient_email)
    masked_sender = _mask_email(config.email_address)
    if masked_sender:
        table.add_row("Sender email", masked_sender)
    table.add_row("Ollama model", config.ollama_model)
    table.add_row("Email language", config.email_style.language)
    table.add_row("Academic level", config.email_style.academic_level)
    table.add_row("Tone", config.email_style.tone)
    table.add_row("Length", config.email_style.length)
    table.add_row("Max words", str(config.email_style.max_words))
    table.add_row("Format", config.email_style.email_format)
    table.add_row("Include links", str(config.email_style.include_links))
    table.add_row("Include phone", str(config.email_style.include_phone))
    table.add_row("Include location", str(config.email_style.include_location))
    table.add_row("Include GPA", str(config.email_style.include_gpa))
    table.add_row("Include languages", str(config.email_style.include_languages))
    table.add_row("Include availability", str(config.email_style.include_availability))
    table.add_row("Subject", subject)

    console.print(
        Panel(
            table,
            title="Generated Email Preview",
            border_style="cyan",
        )
    )
    _render_profile_used(config)
    console.print(Panel(body, title="Email Body", border_style="green"))


def _write_debug_files(
    prompt: str,
    snapshot: dict[str, object],
) -> tuple[Path, Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = DATA_DIR / "last_prompt.txt"
    snapshot_path = DATA_DIR / "last_config_snapshot.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return prompt_path, snapshot_path


def _write_llm_debug_outputs(debug_outputs: dict[str, object]) -> Path:
    debug_dir = DATA_DIR / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    for name in ("company", "candidate", "email"):
        raw = str(debug_outputs.get(f"{name}_raw", ""))
        parsed = debug_outputs.get(f"{name}_parsed", {})
        (debug_dir / f"{name}_raw.txt").write_text(raw, encoding="utf-8")
        (debug_dir / f"{name}_parsed.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return debug_dir


@app.command()
def apply(
    website: Annotated[str, typer.Option("--website", help="Company website URL.")],
    cv: Annotated[str, typer.Option("--cv", help="Local CV path: PDF, DOCX, or TXT.")],
    email: Annotated[str, typer.Option("--email", help="Target company email address.")],
    send: Annotated[bool, typer.Option("--send", help="Ask to send after preview.")] = False,
    debug_prompt: Annotated[
        bool,
        typer.Option("--debug-prompt", help="Save the final prompt and config snapshot."),
    ] = False,
    debug_llm_output: Annotated[
        bool,
        typer.Option("--debug-llm-output", help="Save raw and parsed LLM outputs."),
    ] = False,
) -> None:
    """Generate a tailored internship application email."""
    application_id: int | None = None
    try:
        config = load_config()
        generation_warnings: list[str] = []
        debug_outputs: dict[str, object] = {}
        with console.status("Checking Ollama...", spinner="dots"):
            check_ollama_connection(config.ollama_model)

        with console.status("Reading company website...", spinner="dots"):
            website_text = extract_website_text(website)

        with console.status("Reading CV...", spinner="dots"):
            cv_text = read_cv(cv)

        with console.status("Summarizing company...", spinner="dots"):
            company_summary = summarize_company(
                website_text,
                config.ollama_model,
                debug_outputs=debug_outputs if debug_llm_output else None,
                warnings=generation_warnings,
            )

        with console.status("Summarizing candidate...", spinner="dots"):
            candidate_summary = summarize_candidate(
                cv_text,
                config.ollama_model,
                debug_outputs=debug_outputs if debug_llm_output else None,
                warnings=generation_warnings,
            )

        if debug_prompt:
            final_prompt = build_email_prompt(
                company_summary,
                candidate_summary,
                email,
                config.applicant_profile,
                config.internship_preferences,
                config.email_style,
            )
            debug_snapshot = {
                "config": config_snapshot(config),
                "prompt_context": build_prompt_snapshot(
                    company_summary,
                    candidate_summary,
                    config.applicant_profile,
                    config.internship_preferences,
                    config.email_style,
                ),
            }
            prompt_path, snapshot_path = _write_debug_files(final_prompt, debug_snapshot)
            console.print(
                f"[cyan]Debug prompt saved to:[/cyan] {prompt_path}\n"
                f"[cyan]Debug config snapshot saved to:[/cyan] {snapshot_path}"
            )

        with console.status("Writing email...", spinner="dots"):
            subject, body = write_email(
                company_summary,
                candidate_summary,
                email,
                config.applicant_profile,
                config.internship_preferences,
                config.email_style,
                config.ollama_model,
                debug_outputs=debug_outputs if debug_llm_output else None,
            )
            generated = GeneratedEmail(
                subject=subject,
                body=body,
                warnings=build_generation_warnings(
                    subject,
                    body,
                    config.applicant_profile,
                    config.internship_preferences,
                    config.email_style,
                ),
            )

        if debug_llm_output:
            debug_dir = _write_llm_debug_outputs(debug_outputs)
            console.print(f"[cyan]Saved raw and parsed LLM outputs to:[/cyan] {debug_dir}")

        application_id = save_application(
            company_website=website,
            recipient_email=email,
            subject=generated.subject,
            body=generated.body,
            status="previewed",
        )
        _render_preview(website, email, generated.subject, generated.body, config)
        _render_warnings(generation_warnings + generated.warnings)

        if not send:
            console.print("[yellow]Preview only. Nothing was sent.[/yellow]")
            return

        confirmed = typer.confirm("Send this email with CV attached?", default=False)
        if not confirmed:
            update_status(application_id, "cancelled")
            console.print("[yellow]Cancelled. Nothing was sent.[/yellow]")
            return

        with console.status("Sending email...", spinner="dots"):
            send_email(
                sender_email=config.email_address or "",
                app_password=config.email_app_password or "",
                recipient_email=email,
                subject=generated.subject,
                body=generated.body,
                attachment_path=cv,
            )
        update_status(application_id, "sent")
        console.print("[green]Email sent and application tracked.[/green]")
    except HuntError as exc:
        if application_id is not None:
            update_status(application_id, "failed")
        _show_error(str(exc))
        raise typer.Exit(code=1) from exc
    except LLMJsonParseError as exc:
        if application_id is not None:
            update_status(application_id, "failed")
        _show_error(str(exc))
        raise typer.Exit(code=1) from exc


@app.command("history")
def history() -> None:
    """Show tracked application history."""
    records = list_applications()
    if not records:
        console.print("[yellow]No applications tracked yet.[/yellow]")
        return

    table = Table(title="Application History", show_lines=False)
    table.add_column("ID", justify="right")
    table.add_column("Created")
    table.add_column("Status")
    table.add_column("Website")
    table.add_column("Recipient")
    table.add_column("Subject")

    for record in records:
        table.add_row(
            str(record.id),
            record.created_at,
            record.status,
            record.company_website,
            record.recipient_email,
            record.subject,
        )
    console.print(table)


@app.command("check-llm")
def check_llm() -> None:
    """Check the local Ollama connection and configured model."""
    config = load_config()
    try:
        _, model = check_ollama_connection(config.ollama_model)
    except HuntError as exc:
        _show_error(str(exc))
        raise typer.Exit(code=1) from exc

    console.print(
        Panel(
            f"Ollama is running and model '{model}' is available.\n"
            f"Configured model: {config.ollama_model}",
            border_style="green",
        )
    )


@app.command("config")
def show_config() -> None:
    """Show loaded non-secret configuration and prompt dictionaries."""
    loaded_config = load_config()
    snapshot = config_snapshot(loaded_config)

    overview = Table.grid(padding=(0, 1))
    overview.add_column(style="bold")
    overview.add_column()
    if loaded_config.env_path:
        overview.add_row(".env loaded", loaded_config.env_path)
    else:
        overview.add_row(".env loaded", "No .env file found")
    masked = mask_email(loaded_config.email_address)
    if masked:
        overview.add_row("Sender email", masked)
    overview.add_row("Ollama model", loaded_config.ollama_model)
    overview.add_row("Email language", loaded_config.email_style.language)
    overview.add_row("Academic level", loaded_config.email_style.academic_level)
    overview.add_row("Tone", loaded_config.email_style.tone)
    overview.add_row("Length", loaded_config.email_style.length)
    overview.add_row("Max words", str(loaded_config.email_style.max_words))
    overview.add_row("Internship mode", loaded_config.internship_preferences.mode)
    overview.add_row("Internship type", loaded_config.internship_preferences.internship_type)
    overview.add_row("Include GPA", str(loaded_config.email_style.include_gpa))
    overview.add_row("Include links", str(loaded_config.email_style.include_links))
    overview.add_row("Include phone", str(loaded_config.email_style.include_phone))
    overview.add_row("Include location", str(loaded_config.email_style.include_location))
    console.print(Panel(overview, title="Loaded Configuration", border_style="cyan"))

    if not loaded_config.env_path:
        console.print(
            Panel("No .env file was found. Defaults and process environment are being used.", border_style="yellow")
        )
    for warning in env_example_warnings():
        console.print(Panel(warning, title="Configuration Warning", border_style="yellow"))

    for title, key in (
        ("Profile Fields Passed To LLM", "applicant_profile_prompt"),
        ("Signature Fields Passed To LLM", "signature"),
        ("Internship Fields Passed To LLM", "internship_preferences"),
    ):
        rows = _flatten_preview_fields(snapshot[key])  # type: ignore[arg-type]
        if not rows:
            console.print(Panel("No fields.", title=title, border_style="blue"))
            continue
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        for field, value in rows:
            table.add_row(field, value)
        console.print(Panel(table, title=title, border_style="blue"))
