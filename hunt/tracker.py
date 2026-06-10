from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "applications.db"
VALID_STATUSES = {"previewed", "sent", "cancelled", "failed"}
BATCH_STATUSES = {"pending", "generated", "drafted", "sent", "skipped", "failed", "invalid", "duplicate"}


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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    csv_path TEXT NOT NULL,
                    cv_path TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    total_rows INTEGER NOT NULL,
                    processed_rows INTEGER NOT NULL DEFAULT 0,
                    sent_count INTEGER NOT NULL DEFAULT 0,
                    draft_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_run_id INTEGER NOT NULL,
                    row_index INTEGER NOT NULL,
                    company_name TEXT,
                    website TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT,
                    notes TEXT,
                    status TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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


def application_exists(
    website: str,
    recipient_email: str,
    statuses: set[str],
    db_path: Path | str = DEFAULT_DB_PATH,
) -> bool:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        placeholders = ",".join("?" for _ in statuses)
        row = connection.execute(
            f"""
            SELECT 1 FROM applications
            WHERE company_website = ? AND recipient_email = ? AND status IN ({placeholders})
            LIMIT 1
            """,
            (website, recipient_email, *statuses),
        ).fetchone()
    return row is not None


def create_batch_run(
    csv_path: str,
    cv_path: str,
    total_rows: int,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    init_db(db_path)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO batch_runs (
                    csv_path, cv_path, started_at, total_rows, processed_rows,
                    sent_count, draft_count, skipped_count, failed_count, status
                )
                VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
                """,
                (csv_path, cv_path, started_at, total_rows, "running"),
            )
            return int(cursor.lastrowid)


def create_batch_item(
    batch_run_id: int,
    row_index: int,
    company_name: str,
    website: str,
    email: str,
    role: str,
    notes: str,
    status: str = "pending",
    error: str = "",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    if status not in BATCH_STATUSES:
        raise ValueError(f"Invalid batch status: {status}")
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO batch_items (
                    batch_run_id, row_index, company_name, website, email, role,
                    notes, status, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (batch_run_id, row_index, company_name, website, email, role, notes, status, error, now, now),
            )
            return int(cursor.lastrowid)


def update_batch_item(
    item_id: int,
    status: str,
    subject: str = "",
    body: str = "",
    error: str = "",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    if status not in BATCH_STATUSES:
        raise ValueError(f"Invalid batch status: {status}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute(
                """
                UPDATE batch_items
                SET status = ?, subject = ?, body = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, subject, body, error, now, item_id),
            )


def finish_batch_run(
    batch_run_id: int,
    status: str,
    processed_rows: int,
    sent_count: int,
    draft_count: int,
    skipped_count: int,
    failed_count: int,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute(
                """
                UPDATE batch_runs
                SET finished_at = ?, processed_rows = ?, sent_count = ?,
                    draft_count = ?, skipped_count = ?, failed_count = ?, status = ?
                WHERE id = ?
                """,
                (finished_at, processed_rows, sent_count, draft_count, skipped_count, failed_count, status, batch_run_id),
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
