from fastapi.testclient import TestClient

from app.database import find_user_by_phone
from app.main import app
from app.sms_responder import build_sms_reply


def test_sms_responder_scans_symbol_in_twin_voice():
    response = build_sms_reply("+15550001001", "scan NVDA")

    assert response["action"] == "scan_symbol"
    assert "NVDA" in response["reply"]
    assert "Not financial advice. Market alerts only." in response["reply"]


def test_sms_responder_returns_market_senses():
    response = build_sms_reply("+15550001002", "crash pressure")

    assert response["action"] == "market_senses"
    assert "pressure" in response["reply"].lower()
    assert "Not financial advice. Market alerts only." in response["reply"]


def test_sms_responder_can_pause_and_resume_user():
    phone_number = "+15550001003"

    pause = build_sms_reply(phone_number, "pause")
    paused_user = find_user_by_phone(phone_number)
    resume = build_sms_reply(phone_number, "resume")
    resumed_user = find_user_by_phone(phone_number)

    assert pause["action"] == "pause"
    assert paused_user["sms_enabled"] == 0
    assert resume["action"] == "resume"
    assert resumed_user["sms_enabled"] == 1


def test_sms_webhook_returns_reply_for_inbound_message():
    with TestClient(app) as client:
        response = client.post(
            "/sms/webhook",
            data={"From": "+15550001004", "Body": "market read"},
        )

    data = response.json()
    assert response.status_code == 200
    assert data["message"] == "SmokeSignal AI reply generated."
    assert data["action"] == "market_read"
    assert "reply" in data
