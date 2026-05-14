from urllib.parse import parse_qs
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.ai_writer import generate_alert_text
from app.alert_sender import process_alert, send_sms_alert
from app.config import settings
from app.database import (
    create_user,
    find_user_by_phone,
    get_alerts,
    get_user_watchlist,
    get_users,
    init_db,
    seed_default_watchlist,
    set_user_sms_enabled,
    upsert_user,
)
from app.models import SubscribeRequest, TestSmsRequest, UserCreate
from app.scheduler import run_hourly_update_once, scan_all_once, start_hourly_sms_scheduler
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score


app = FastAPI(
    title="SmokeSignal AI",
    description="Local MVP market monitoring and alert engine. Not financial advice.",
    version="0.1.0",
)
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()
    if settings.HOURLY_UPDATES_ENABLED:
        start_hourly_sms_scheduler()


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


def _subscription_page_html() -> HTMLResponse:
    return HTMLResponse("""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>SmokeSignal AI SMS Alerts</title>
        <style>
          body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #101418;
            color: #f5f7fa;
          }
          main {
            max-width: 560px;
            margin: 0 auto;
            padding: 32px 20px 48px;
          }
          .logo {
            display: block;
            width: min(360px, 82vw);
            height: auto;
            margin: 0 auto 20px;
            border-radius: 8px;
          }
          h1 {
            font-size: 30px;
            margin-bottom: 8px;
            text-align: center;
          }
          p {
            color: #cbd3dc;
            line-height: 1.5;
            text-align: center;
          }
          form {
            display: grid;
            gap: 14px;
            margin-top: 28px;
          }
          label {
            font-weight: 700;
          }
          input, select, button {
            width: 100%;
            box-sizing: border-box;
            border-radius: 6px;
            border: 1px solid #39424e;
            padding: 12px;
            font-size: 16px;
          }
          input, select {
            background: #161d24;
            color: #f5f7fa;
          }
          button {
            border: 0;
            background: #ff6b35;
            color: #111;
            font-weight: 800;
            cursor: pointer;
          }
          .notice {
            font-size: 13px;
            color: #aeb8c4;
          }
        </style>
      </head>
      <body>
        <main>
          <img class="logo" src="/static/smokesignal-logo.png" alt="SmokeSignal AI logo" />
          <h1>SmokeSignal AI</h1>
          <p>Subscribe to hourly market monitoring texts for stocks, crypto, and forex. Alerts are for education and monitoring only.</p>
          <form method="post" action="/subscribe">
            <label for="name">Name</label>
            <input id="name" name="name" placeholder="Jordan" required />

            <label for="phone_number">Phone number</label>
            <input id="phone_number" name="phone_number" placeholder="+12565551234" required />

            <label for="voice_mode">Alert voice</label>
            <select id="voice_mode" name="voice_mode">
              <option value="atl_homie">ATL Homie</option>
              <option value="market_homie">Market Homie</option>
              <option value="clean_retail">Clean Retail</option>
              <option value="professional">Professional</option>
            </select>

            <p class="notice">
              By subscribing, you agree to receive recurring hourly SmokeSignal AI market monitoring texts.
              Message and data rates may apply. Reply STOP to opt out. Not financial advice. Market alerts only.
            </p>

            <button type="submit">Start SMS Alerts</button>
          </form>
        </main>
      </body>
    </html>
    """)


@app.get("/subscribe", response_class=HTMLResponse)
def subscribe_page() -> HTMLResponse:
    """Small local signup page for opted-in SMS alerts."""
    return _subscription_page_html()


@app.get("/join", response_class=HTMLResponse)
def join_page() -> HTMLResponse:
    """Fresh alias for the SMS signup page."""
    return _subscription_page_html()


def _decode_request_data(raw_body: bytes, content_type: str) -> dict:
    if "application/json" in content_type and raw_body:
        return {}
    parsed = parse_qs(raw_body.decode("utf-8")) if raw_body else {}
    return {key: values[0] for key, values in parsed.items() if values}


def _subscribe_user(name: str, phone_number: str, voice_mode: str) -> dict:
    user = upsert_user(name=name, phone_number=phone_number, sms_enabled=True, voice_mode=voice_mode)
    seed_default_watchlist(user["id"], DEFAULT_WATCHLIST)
    welcome_text = (
        "SmokeSignal AI subscription active. You'll receive hourly market monitoring updates. "
        "Reply STOP to opt out. Not financial advice. Market alerts only."
    )
    welcome_sent = send_sms_alert(user, welcome_text)
    return {
        "message": "Subscription active.",
        "welcome_sms_sent": welcome_sent,
        "user": user,
        "watchlist": get_user_watchlist(user["id"]),
    }


@app.post("/subscribe")
async def subscribe(request: Request):
    content_type = request.headers.get("content-type", "")
    raw_body = await request.body()

    if "application/json" in content_type and raw_body:
        payload = SubscribeRequest(**await request.json())
        result = _subscribe_user(payload.name, payload.phone_number, payload.voice_mode)
        return result

    data = _decode_request_data(raw_body, content_type)
    result = _subscribe_user(
        name=data.get("name", "SmokeSignal User"),
        phone_number=data.get("phone_number", ""),
        voice_mode=data.get("voice_mode", "atl_homie"),
    )
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="en">
          <head><title>SmokeSignal AI Subscription</title></head>
          <body style="font-family: Arial, sans-serif; background:#101418; color:#f5f7fa; padding:40px;">
            <h1>Subscription active</h1>
            <p>{result["user"]["phone_number"]} is opted into hourly SmokeSignal AI market monitoring texts.</p>
            <p>Reply STOP to opt out. Not financial advice. Market alerts only.</p>
            <p><a style="color:#ff9f68;" href="/docs">Open API docs</a></p>
          </body>
        </html>
        """
    )


@app.post("/unsubscribe")
async def unsubscribe(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    raw_body = await request.body()
    data = await request.json() if "application/json" in content_type and raw_body else _decode_request_data(raw_body, content_type)
    phone_number = data.get("phone_number", "")
    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number is required.")
    updated = set_user_sms_enabled(phone_number, False)
    return {"unsubscribed": updated, "phone_number": phone_number}


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


@app.get("/users/{user_id}/watchlist")
def user_watchlist(user_id: int) -> list[dict]:
    return get_user_watchlist(user_id)


@app.post("/hourly-update")
def hourly_update() -> dict:
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=403, detail="Manual hourly updates only work in development.")
    results = run_hourly_update_once()
    return {"users_notified": len(results), "results": results}


@app.post("/scheduler/hourly/start")
def scheduler_hourly_start() -> dict:
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=403, detail="Manual scheduler start only works in development.")
    started = start_hourly_sms_scheduler()
    return {"started": started, "message": "Hourly SMS scheduler is running." if started else "Hourly SMS scheduler was already running."}


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
