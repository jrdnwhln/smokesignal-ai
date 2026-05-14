import re
from typing import Any

from app.ai_writer import DISCLAIMER, generate_alert_text, normalize_voice_mode
from app.database import find_user_by_phone, set_user_sms_enabled, set_user_voice_mode, upsert_user
from app.market_reader import read_market
from app.market_senses import build_market_senses
from app.signal_engine import DEFAULT_WATCHLIST, calculate_confluence_score


STOP_WORDS = {"STOP", "UNSUBSCRIBE", "CANCEL", "QUIT"}
RESUME_WORDS = {"START", "RESUME", "UNPAUSE", "ON"}
HELP_WORDS = {"HELP", "MENU", "COMMANDS"}


def _all_symbols() -> set[str]:
    return set(DEFAULT_WATCHLIST["stocks"] + DEFAULT_WATCHLIST["crypto"] + DEFAULT_WATCHLIST["forex"])


def _clean_message(body: str) -> str:
    return re.sub(r"\s+", " ", (body or "").strip())


def _public_voice_name(voice_mode: str) -> str:
    normalized = normalize_voice_mode(voice_mode)
    if normalized == "atl_homie":
        return "twin"
    return "normal clanka"


def _user_for_reply(phone_number: str | None) -> dict[str, Any]:
    if not phone_number:
        return {"phone_number": "", "sms_enabled": False, "voice_mode": "twin", "name": "SmokeSignal User"}

    user = find_user_by_phone(phone_number)
    if user:
        return user

    return upsert_user(
        name="SmokeSignal User",
        phone_number=phone_number,
        sms_enabled=True,
        voice_mode="atl_homie",
    )


def _help_text(voice_mode: str) -> str:
    if normalize_voice_mode(voice_mode) == "atl_homie":
        return (
            "Twin, text: SCAN NVDA, BTC, MARKET, SENSES, STATUS, TWIN, NORMAL, PAUSE, or RESUME. "
            f"SmokeSignal reads the board, no buy/sell calls. {DISCLAIMER}"
        )
    return (
        "SmokeSignal commands: SCAN NVDA, BTC, MARKET, SENSES, STATUS, TWIN, NORMAL, PAUSE, or RESUME. "
        f"Market monitoring only. {DISCLAIMER}"
    )


def _status_text(user: dict[str, Any]) -> str:
    voice_name = _public_voice_name(user.get("voice_mode", "twin"))
    enabled = "on" if user.get("sms_enabled") else "paused"
    if normalize_voice_mode(user.get("voice_mode")) == "atl_homie":
        return f"Twin, your SmokeSignal texts are {enabled}. Voice mode: {voice_name}. Stay tapped in. {DISCLAIMER}"
    return f"SmokeSignal SMS status: {enabled}. Voice mode: {voice_name}. {DISCLAIMER}"


def _extract_symbol(message: str) -> str | None:
    tokens = re.findall(r"[A-Z]{2,6}", message.upper().replace("/", ""))
    symbols = _all_symbols()
    for token in tokens:
        if token in symbols:
            return token
    return None


def _short_market_reply(voice_mode: str) -> str:
    read = read_market(voice_mode)
    senses = read.get("market_senses", {})
    leaders = ", ".join(f"{item['symbol']} {item['score']}/10" for item in read["leaders"][:3])
    phase = senses.get("phase", read["regime"]["regime"])
    crash = senses.get("indexes", {}).get("crash_pressure", "n/a")

    if normalize_voice_mode(voice_mode) == "atl_homie":
        return (
            f"Twin, tape say {phase}. Top smoke: {leaders}. Crash pressure {crash}/100. "
            f"Read the whole board, no chasing. {DISCLAIMER}"
        )[:320]
    return (
        f"Market read: {phase}. Leading confluence: {leaders}. Crash pressure {crash}/100. {DISCLAIMER}"
    )[:320]


def _short_senses_reply(voice_mode: str) -> str:
    senses = build_market_senses(voice_mode)
    return senses["briefing"][:320]


def build_sms_reply(phone_number: str | None, body: str | None) -> dict[str, Any]:
    """Parse an inbound SMS and build a safe market-monitoring reply."""
    message = _clean_message(body or "")
    upper = message.upper()
    user = _user_for_reply(phone_number)
    voice_mode = user.get("voice_mode", "twin")

    if upper in STOP_WORDS or any(word in upper.split() for word in STOP_WORDS):
        if phone_number:
            set_user_sms_enabled(phone_number, False)
        return {
            "action": "opt_out",
            "reply": "You have been opted out of SmokeSignal AI SMS alerts. Reply RESUME to opt back in.",
            "user": find_user_by_phone(phone_number) if phone_number else user,
        }

    if upper in RESUME_WORDS or any(word in upper.split() for word in RESUME_WORDS):
        if phone_number:
            set_user_sms_enabled(phone_number, True)
        return {
            "action": "resume",
            "reply": f"SmokeSignal AI texts resumed. {_help_text(voice_mode)}",
            "user": find_user_by_phone(phone_number) if phone_number else user,
        }

    if "TWIN" in upper or "ATL" in upper:
        if phone_number:
            set_user_voice_mode(phone_number, "atl_homie")
        return {
            "action": "voice_twin",
            "reply": f"Twin mode locked. I got you with the street-level market read, still no buy/sell calls. {DISCLAIMER}",
            "user": find_user_by_phone(phone_number) if phone_number else user,
        }

    if "NORMAL" in upper or "PROFESSIONAL" in upper or "CLANKA" in upper:
        if phone_number:
            set_user_voice_mode(phone_number, "professional")
        return {
            "action": "voice_normal",
            "reply": f"Normal clanka mode locked. Alerts will stay clean and professional. {DISCLAIMER}",
            "user": find_user_by_phone(phone_number) if phone_number else user,
        }

    if upper in HELP_WORDS or "HELP" in upper:
        return {"action": "help", "reply": _help_text(voice_mode), "user": user}

    if "STATUS" in upper:
        return {"action": "status", "reply": _status_text(user), "user": user}

    if "PAUSE" in upper or "OFF" == upper:
        if phone_number:
            set_user_sms_enabled(phone_number, False)
        return {
            "action": "pause",
            "reply": "SmokeSignal hourly texts paused. Reply RESUME to turn them back on.",
            "user": find_user_by_phone(phone_number) if phone_number else user,
        }

    if "SENSE" in upper or "PRESSURE" in upper or "CRASH" in upper:
        return {"action": "market_senses", "reply": _short_senses_reply(voice_mode), "user": user}

    if "MARKET" in upper or "TAPE" in upper or "READ" in upper:
        return {"action": "market_read", "reply": _short_market_reply(voice_mode), "user": user}

    symbol = _extract_symbol(upper)
    if symbol:
        alert = calculate_confluence_score(symbol)
        return {
            "action": "scan_symbol",
            "reply": generate_alert_text(alert, voice_mode),
            "user": user,
            "symbol": symbol,
        }

    return {
        "action": "fallback",
        "reply": _help_text(voice_mode),
        "user": user,
    }
