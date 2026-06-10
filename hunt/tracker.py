from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "applications.db"
VALID_STATUSES = {"previewed", "sent", "cancelled", "failed"}


@dataclass(frozen=True)
class ApplicationRecord:
    id: int
    company_website: str
    recipient_email: str
    subject: str
    body: str
    status: str
    created_at: str


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_website TEXT NOT NULL,
                    recipient_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )


def save_application(
    company_website: str,
    recipient_email: str,
    subject: str,
    body: str,
    status: str = "previewed",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    init_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO applications (
                    company_website, recipient_email, subject, body, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (company_website, recipient_email, subject, body, status, created_at),
            )
            return int(cursor.lastrowid)


def update_status(application_id: int, status: str, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute(
                "UPDATE applications SET status = ? WHERE id = ?",
                (status, application_id),
            )


def list_applications(db_path: Path | str = DEFAULT_DB_PATH) -> list[ApplicationRecord]:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, company_website, recipient_email, subject, body, status, created_at
            FROM applications
            ORDER BY id DESC
            """
        ).fetchall()

    return [
        ApplicationRecord(
            id=int(row["id"]),
            company_website=str(row["company_website"]),
            recipient_email=str(row["recipient_email"]),
            subject=str(row["subject"]),
            body=str(row["body"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]
