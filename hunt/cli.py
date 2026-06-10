from __future__ import annotations

from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hunt.config import AppConfig, load_config
from hunt.cv_reader import read_cv
from hunt.email_sender import send_email
from hunt.email_writer import summarize_candidate, summarize_company, write_email
from hunt.local_llm import check_ollama_connection
from hunt.tracker import list_applications, save_application, update_status
from hunt.utils import HuntError
from hunt.website_reader import extract_website_text


app = typer.Typer(help="HUNT: local AI-powered internship application assistant.")
console = Console()


def _show_error(message: str) -> None:
    console.print(Panel(message, title="HUNT Error", border_style="red"))


def _mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***" if local else "***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


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


@app.command()
def apply(
    website: Annotated[str, typer.Option("--website", help="Company website URL.")],
    cv: Annotated[str, typer.Option("--cv", help="Local CV path: PDF, DOCX, or TXT.")],
    email: Annotated[str, typer.Option("--email", help="Target company email address.")],
    send: Annotated[bool, typer.Option("--send", help="Ask to send after preview.")] = False,
) -> None:
    """Generate a tailored internship application email."""
    application_id: int | None = None
    try:
        config = load_config()
        with console.status("Checking Ollama...", spinner="dots"):
            check_ollama_connection()

        with console.status("Reading company website...", spinner="dots"):
            website_text = extract_website_text(website)

        with console.status("Reading CV...", spinner="dots"):
            cv_text = read_cv(cv)

        with console.status("Summarizing company...", spinner="dots"):
            company_summary = summarize_company(website_text)

        with console.status("Summarizing candidate...", spinner="dots"):
            candidate_summary = summarize_candidate(cv_text)

        with console.status("Writing email...", spinner="dots"):
            generated = write_email(
                company_summary,
                candidate_summary,
                email,
                config.applicant_profile,
                config.internship_preferences,
                config.email_style,
            )

        application_id = save_application(
            company_website=website,
            recipient_email=email,
            subject=generated.subject,
            body=generated.body,
            status="previewed",
        )
        _render_preview(website, email, generated.subject, generated.body, config)

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
        _, model = check_ollama_connection()
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
