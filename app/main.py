from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request

from app.ai_writer import generate_alert_text
from app.alert_sender import process_alert, send_sms_alert
from app.config import settings
from app.database import (
    create_user,
    find_user_by_phone,
    get_alerts,
    get_users,
    init_db,
    set_user_sms_enabled,
)
from app.models import TestSmsRequest, UserCreate
from app.scheduler import scan_all_once
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score


app = FastAPI(
    title="SmokeSignal AI",
    description="Local MVP market monitoring and alert engine. Not financial advice.",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root() -> dict:
    return {
        "app": "SmokeSignal AI",
        "status": "running",
        "environment": settings.APP_ENV,
        "disclaimer": "Not financial advice. Market alerts only.",
    }


@app.get("/watchlist")
def watchlist() -> dict:
    return DEFAULT_WATCHLIST


@app.get("/scan")
def scan() -> dict:
    alerts = scan_all_once()
    return {"count": len(alerts), "alerts": alerts}


@app.get("/scan/{symbol}")
def scan_symbol(symbol: str, voice_mode: str = "clean_retail") -> dict:
    alert = calculate_confluence_score(symbol)
    alert_text = generate_alert_text(alert, voice_mode)
    saved_alert = process_alert(alert, alert_text)
    return {**alert, "alert_text": alert_text, "database_id": saved_alert["id"]}


@app.get("/alerts")
def alerts() -> list[dict]:
    return get_alerts()


@app.post("/users")
def users_create(user: UserCreate) -> dict:
    try:
        return create_user(
            name=user.name,
            phone_number=user.phone_number,
            sms_enabled=user.sms_enabled,
            voice_mode=user.voice_mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/users")
def users_list() -> list[dict]:
    return get_users()


@app.post("/test-sms")
def test_sms(request: TestSmsRequest) -> dict:
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=403, detail="Test SMS only works in development.")

    test_user = {
        "phone_number": request.phone_number,
        "sms_enabled": True,
    }
    sent = send_sms_alert(test_user, request.message)
    return {
        "sent": sent,
        "message": "SMS attempted only if SMS_ENABLED and Twilio settings are configured.",
    }


@app.post("/sms/webhook")
async def sms_webhook(request: Request) -> dict:
    """Placeholder Twilio inbound SMS webhook.

    Twilio usually posts URL-encoded form fields named From and Body. JSON is
    also accepted to make local testing easier.
    """
    content_type = request.headers.get("content-type", "")
    raw_body = await request.body()

    if "application/json" in content_type and raw_body:
        data = await request.json()
    else:
        parsed = parse_qs(raw_body.decode("utf-8")) if raw_body else {}
        data = {key: values[0] for key, values in parsed.items() if values}

    phone_number = data.get("From")
    body = data.get("Body", "")
    normalized_body = (body or "").strip().upper()

    if normalized_body in {"STOP", "UNSUBSCRIBE", "CANCEL", "QUIT"}:
        if phone_number:
            set_user_sms_enabled(phone_number, False)
        return {"message": "You have been opted out of SmokeSignal AI SMS alerts."}

    user = find_user_by_phone(phone_number) if phone_number else None
    return {
        "message": "SmokeSignal AI webhook received.",
        "known_user": bool(user),
    }
