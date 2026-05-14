from typing import Any

from app.config import settings
from app.database import save_alert
from app.intelligence import observe_alert


def print_alert(alert_text: str) -> None:
    print("\n=== SmokeSignal AI Alert ===")
    print(alert_text)
    print("============================\n")


def send_sms_alert(user: dict[str, Any], alert_text: str) -> bool:
    """Send an opted-in SMS alert when Twilio is configured."""
    if not settings.SMS_ENABLED:
        print("SMS disabled by configuration. Alert saved only.")
        return False

    if not user.get("sms_enabled"):
        print("User has not opted into SMS. Alert saved only.")
        return False

    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        print("Twilio credentials missing. Alert saved only.")
        return False

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=alert_text,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=user["phone_number"],
        )
        return True
    except Exception as exc:
        print(f"Twilio SMS failed: {exc}. Alert saved only.")
        return False


def send_push_notification() -> None:
    """Future placeholder for mobile push alerts."""
    print("Push notifications are not implemented in the MVP.")


def send_email_alert() -> None:
    """Future placeholder for email alerts."""
    print("Email alerts are not implemented in the MVP.")


def process_alert(alert: dict[str, Any], alert_text: str) -> dict[str, Any]:
    """Print and save the alert. SMS can be layered on per opted-in user later."""
    alert_to_save = {**alert, "alert_text": alert_text}
    saved_alert = save_alert(alert_to_save)
    observe_alert(alert_to_save)

    if alert["should_alert"]:
        print_alert(alert_text)
    else:
        print(f"{alert['symbol']}: no alert. Score {alert['score']}/10.")

    return saved_alert
