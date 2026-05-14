import time

from app.ai_writer import generate_alert_text
from app.alert_sender import process_alert
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score


def scan_all_once(voice_mode: str = "clean_retail") -> list[dict]:
    """Run one scan across the default watchlist."""
    alerts = []
    symbols = DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"]
    for symbol in symbols:
        alert = calculate_confluence_score(symbol)
        alert_text = generate_alert_text(alert, voice_mode)
        saved_alert = process_alert(alert, alert_text)
        alerts.append({**alert, "alert_text": alert_text, "database_id": saved_alert["id"]})
    return alerts


def run_scheduler(interval_minutes: int = 5) -> None:
    """Optional simple loop for local experiments.

    Manual scans through FastAPI should be used first. A production scheduler
    would likely use APScheduler, Celery, or a managed job runner.
    """
    while True:
        scan_all_once()
        time.sleep(interval_minutes * 60)
