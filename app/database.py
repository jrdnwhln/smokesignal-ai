import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import get_sqlite_path


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with dictionary-like rows."""
    conn = sqlite3.connect(get_sqlite_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create MVP tables if they do not already exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone_number TEXT NOT NULL UNIQUE,
                sms_enabled INTEGER NOT NULL DEFAULT 0,
                voice_mode TEXT NOT NULL DEFAULT 'clean_retail',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                score REAL NOT NULL,
                priority TEXT NOT NULL,
                reason TEXT NOT NULL,
                alert_text TEXT NOT NULL,
                should_alert INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_user(name: str, phone_number: str, sms_enabled: bool, voice_mode: str) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (name, phone_number, sms_enabled, voice_mode, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, phone_number, int(sms_enabled), voice_mode, utc_now()),
        )
        user_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)


def get_users() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [row_to_dict(row) for row in rows]


def find_user_by_phone(phone_number: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,)).fetchone()
        return row_to_dict(row) if row else None


def set_user_sms_enabled(phone_number: str, enabled: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET sms_enabled = ? WHERE phone_number = ?",
            (int(enabled), phone_number),
        )
        return cursor.rowcount > 0


def save_alert(alert: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO alerts
                (symbol, asset_type, score, priority, reason, alert_text, should_alert, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert["symbol"],
                alert["asset_type"],
                alert["score"],
                alert["priority"],
                alert["reason"],
                alert.get("alert_text", ""),
                int(alert["should_alert"]),
                utc_now(),
            ),
        )
        alert_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return row_to_dict(row)


def get_alerts(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]
