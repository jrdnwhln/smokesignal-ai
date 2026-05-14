import time
from threading import Thread
from typing import Any

from app.ai_writer import generate_alert_text
from app.alert_sender import process_alert, send_sms_alert
from app.database import get_sms_enabled_users, get_user_watchlist
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score

_scheduler_thread: Thread | None = None


def scan_all_once(voice_mode: str = "clean_retail") -> list[dict]:
    """Run one scan across the default watchlist."""
    alerts = []
    symbols = DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"] + DEFAULT_WATCHLIST["forex"]
    for symbol in symbols:
        alert = calculate_confluence_score(symbol)
        alert_text = generate_alert_text(alert, voice_mode)
        saved_alert = process_alert(alert, alert_text)
        alerts.append({**alert, "alert_text": alert_text, "database_id": saved_alert["id"]})
    return alerts


def _symbols_for_user(user: dict[str, Any]) -> list[str]:
    watchlist = get_user_watchlist(user["id"])
    if watchlist:
        return [item["symbol"] for item in watchlist]
    return DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"] + DEFAULT_WATCHLIST["forex"]


def build_hourly_digest(user: dict[str, Any], alerts: list[dict[str, Any]]) -> str:
    """Create one SMS-friendly hourly summary for a user."""
    actionable_alerts = [alert for alert in alerts if alert["should_alert"]]
    actionable_alerts.sort(key=lambda alert: alert["score"], reverse=True)
    top_alerts = actionable_alerts[:3]

    if not top_alerts:
        return (
            "SmokeSignal hourly: no WATCH or HIGH PRIORITY signals right now. "
            "Markets still being monitored. Not financial advice. Market alerts only."
        )

    parts = [
        f"{alert['symbol']} {alert['priority']} {alert['score']}/10"
        for alert in top_alerts
    ]
    intro = "SmokeSignal hourly: " if user.get("voice_mode") != "atl_homie" else "Aye, hourly SmokeSignal: "
    return f"{intro}" + " | ".join(parts) + ". Don't chase, stay sharp. Not financial advice. Market alerts only."


def send_hourly_update_to_user(user: dict[str, Any]) -> dict[str, Any]:
    """Scan a user's watchlist, save alerts, and send one opted-in SMS digest."""
    symbols = _symbols_for_user(user)
    alerts = []
    for symbol in symbols:
        alert = calculate_confluence_score(symbol)
        alert_text = generate_alert_text(alert, user.get("voice_mode", "clean_retail"))
        saved_alert = process_alert(alert, alert_text)
        alerts.append({**alert, "alert_text": alert_text, "database_id": saved_alert["id"]})

    digest = build_hourly_digest(user, alerts)
    sent = send_sms_alert(user, digest)
    return {
        "user_id": user["id"],
        "phone_number": user["phone_number"],
        "sent": sent,
        "digest": digest,
        "alerts_scanned": len(alerts),
    }


def run_hourly_update_once() -> list[dict[str, Any]]:
    """Send one hourly digest to every opted-in SMS user."""
    users = get_sms_enabled_users()
    return [send_hourly_update_to_user(user) for user in users]


def run_scheduler(interval_minutes: int = 5) -> None:
    """Optional simple loop for local experiments.

    Manual scans through FastAPI should be used first. A production scheduler
    would likely use APScheduler, Celery, or a managed job runner.
    """
    while True:
        scan_all_once()
        time.sleep(interval_minutes * 60)


def run_hourly_sms_scheduler() -> None:
    """Simple local hourly loop for opted-in SMS digests."""
    while True:
        run_hourly_update_once()
        time.sleep(60 * 60)


def start_hourly_sms_scheduler() -> bool:
    """Start the hourly SMS loop once per app process."""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return False

    _scheduler_thread = Thread(target=run_hourly_sms_scheduler, daemon=True)
    _scheduler_thread.start()
    return True
