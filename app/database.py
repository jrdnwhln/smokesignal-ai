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
                voice_mode TEXT NOT NULL DEFAULT 'professional',
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intelligence_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                symbol TEXT,
                summary TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL UNIQUE,
                mentions INTEGER NOT NULL DEFAULT 0,
                catalyst_mentions INTEGER NOT NULL DEFAULT 0,
                last_symbol TEXT,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                observations INTEGER NOT NULL DEFAULT 0,
                alert_observations INTEGER NOT NULL DEFAULT 0,
                last_symbol TEXT,
                last_score REAL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                fired INTEGER NOT NULL,
                alert_score REAL NOT NULL,
                priority TEXT NOT NULL,
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


def upsert_user(name: str, phone_number: str, sms_enabled: bool, voice_mode: str) -> dict[str, Any]:
    """Create a user or update an existing subscription record."""
    existing_user = find_user_by_phone(phone_number)
    with get_connection() as conn:
        if existing_user:
            conn.execute(
                """
                UPDATE users
                SET name = ?, sms_enabled = ?, voice_mode = ?
                WHERE phone_number = ?
                """,
                (name, int(sms_enabled), voice_mode, phone_number),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (name, phone_number, sms_enabled, voice_mode, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, phone_number, int(sms_enabled), voice_mode, utc_now()),
            )
        row = conn.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,)).fetchone()
        return row_to_dict(row)


def get_users() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [row_to_dict(row) for row in rows]


def get_sms_enabled_users() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM users WHERE sms_enabled = 1 ORDER BY created_at DESC").fetchall()
        return [row_to_dict(row) for row in rows]


def find_user_by_phone(phone_number: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,)).fetchone()
        return row_to_dict(row) if row else None


def add_watchlist_symbol(user_id: int, symbol: str, asset_type: str) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM user_watchlists
            WHERE user_id = ? AND symbol = ? AND asset_type = ?
            """,
            (user_id, symbol, asset_type),
        ).fetchone()
        if existing:
            return
        conn.execute(
            """
            INSERT INTO user_watchlists (user_id, symbol, asset_type)
            VALUES (?, ?, ?)
            """,
            (user_id, symbol, asset_type),
        )


def seed_default_watchlist(user_id: int, watchlist: dict[str, list[str]]) -> None:
    for asset_type, symbols in watchlist.items():
        singular_asset_type = "stock" if asset_type == "stocks" else asset_type.rstrip("s")
        for symbol in symbols:
            add_watchlist_symbol(user_id, symbol, singular_asset_type)


def get_user_watchlist(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM user_watchlists
            WHERE user_id = ?
            ORDER BY asset_type, symbol
            """,
            (user_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def set_user_sms_enabled(phone_number: str, enabled: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET sms_enabled = ? WHERE phone_number = ?",
            (int(enabled), phone_number),
        )
        return cursor.rowcount > 0


def set_user_voice_mode(phone_number: str, voice_mode: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET voice_mode = ? WHERE phone_number = ?",
            (voice_mode, phone_number),
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


def save_intelligence_event(event_type: str, summary: str, symbol: str | None = None, metadata: str | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO intelligence_events (event_type, symbol, summary, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_type, symbol, summary, metadata, utc_now()),
        )
        row = conn.execute("SELECT * FROM intelligence_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_to_dict(row)


def get_intelligence_events(limit: int = 25) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM intelligence_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def record_source_observation(source: str, symbol: str, is_catalyst: bool) -> None:
    if not source:
        return

    with get_connection() as conn:
        existing = conn.execute("SELECT * FROM source_memory WHERE source = ?", (source,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE source_memory
                SET mentions = mentions + 1,
                    catalyst_mentions = catalyst_mentions + ?,
                    last_symbol = ?,
                    last_seen_at = ?
                WHERE source = ?
                """,
                (int(is_catalyst), symbol, utc_now(), source),
            )
        else:
            conn.execute(
                """
                INSERT INTO source_memory (source, mentions, catalyst_mentions, last_symbol, last_seen_at)
                VALUES (?, 1, ?, ?, ?)
                """,
                (source, int(is_catalyst), symbol, utc_now()),
            )


def get_source_memory(limit: int = 25) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM source_memory
            ORDER BY catalyst_mentions DESC, mentions DESC, last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def set_agent_state_value(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, utc_now()),
        )


def get_agent_state_values() -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value, updated_at FROM agent_state").fetchall()
        return {row["key"]: {"value": row["value"], "updated_at": row["updated_at"]} for row in rows}


def record_strategy_observation(strategy: dict[str, Any], alert: dict[str, Any]) -> None:
    strategy_id = strategy["id"]
    fired = bool(strategy.get("fired"))
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO strategy_memory
                (strategy_id, name, description, observations, alert_observations, last_symbol, last_score, last_seen_at)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(strategy_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                observations = observations + 1,
                alert_observations = alert_observations + excluded.alert_observations,
                last_symbol = excluded.last_symbol,
                last_score = excluded.last_score,
                last_seen_at = excluded.last_seen_at
            """,
            (
                strategy_id,
                strategy["name"],
                strategy["description"],
                int(fired),
                alert["symbol"],
                strategy["confidence"],
                utc_now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO strategy_observations
                (strategy_id, symbol, asset_type, confidence, fired, alert_score, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                alert["symbol"],
                alert["asset_type"],
                strategy["confidence"],
                int(fired),
                alert["score"],
                alert["priority"],
                utc_now(),
            ),
        )


def get_strategy_memory(limit: int = 25) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM strategy_memory
            ORDER BY alert_observations DESC, observations DESC, last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]


def get_strategy_observations(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM strategy_observations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [row_to_dict(row) for row in rows]
