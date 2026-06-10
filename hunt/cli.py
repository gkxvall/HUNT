from __future__ import annotations

import os
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hunt.cv_reader import read_cv
from hunt.email_sender import send_email
from hunt.email_writer import summarize_candidate, summarize_company, write_email
from hunt.local_llm import check_ollama_connection, get_ollama_model
from hunt.tracker import list_applications, save_application, update_status
from hunt.utils import HuntError
from hunt.website_reader import extract_website_text


app = typer.Typer(help="HUNT: local AI-powered internship application assistant.")
console = Console()


def _show_error(message: str) -> None:
    console.print(Panel(message, title="HUNT Error", border_style="red"))


def _render_preview(website: str, recipient_email: str, subject: str, body: str) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Company website", website)
    table.add_row("To", recipient_email)
    table.add_row("Ollama model", get_ollama_model())
    table.add_row("Subject", subject)

    console.print(
        Panel(
            table,
            title="Generated Email Preview",
            border_style="cyan",
        )
    )
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
            generated = write_email(company_summary, candidate_summary, email)

        application_id = save_application(
            company_website=website,
            recipient_email=email,
            subject=generated.subject,
            body=generated.body,
            status="previewed",
        )
        _render_preview(website, email, generated.subject, generated.body)

        if not send:
            console.print("[yellow]Preview only. Nothing was sent.[/yellow]")
            return

        confirmed = typer.confirm("Send this email with CV attached?", default=False)
        if not confirmed:
            update_status(application_id, "cancelled")
            console.print("[yellow]Cancelled. Nothing was sent.[/yellow]")
            return

        sender_email = os.getenv("EMAIL_ADDRESS", "")
        app_password = os.getenv("EMAIL_APP_PASSWORD", "")
        with console.status("Sending email...", spinner="dots"):
            send_email(
                sender_email=sender_email,
                app_password=app_password,
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
    try:
        _, model = check_ollama_connection()
    except HuntError as exc:
        _show_error(str(exc))
        raise typer.Exit(code=1) from exc

    console.print(Panel(f"Ollama is running and model '{model}' is available.", border_style="green"))
