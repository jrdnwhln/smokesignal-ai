from app.config import settings


DISCLAIMER = "Not financial advice. Market alerts only."


def _template_alert(alert: dict, voice_mode: str = "clean_retail") -> str:
    symbol = alert["symbol"]
    score = alert["score"]
    priority = alert["priority"]

    if voice_mode == "professional":
        message = (
            f"{symbol} is showing elevated market activity with {priority.lower()} status. "
            f"Confluence Score: {score}/10."
        )
    elif voice_mode == "market_homie":
        message = (
            f"Aye, {symbol} heating up. Volume loud, price moving fast, and news may be adding fuel. "
            f"Confluence: {score}/10. Don't chase blind."
        )
    else:
        message = (
            f"{symbol} is moving fast with stronger activity and a possible news catalyst. "
            f"Worth watching. Score: {score}/10."
        )

    return f"{message} {DISCLAIMER}"


def rewrite_alert_with_llm(alert: dict, voice_mode: str = "clean_retail") -> str | None:
    """Optional future LLM rewrite hook.

    Keep this disabled for the local MVP. When enabled later, pass the structured
    alert data to an LLM with strict safety rules: no buy/sell instructions, no
    guaranteed outcomes, and always include the disclaimer.
    """
    if not settings.OPENAI_API_KEY:
        return None
    # Add OpenAI client call here later.
    return None


def generate_alert_text(alert: dict, voice_mode: str = "clean_retail") -> str:
    """Generate short, SMS-friendly alert copy."""
    llm_text = rewrite_alert_with_llm(alert, voice_mode)
    if llm_text:
        text = llm_text
    else:
        text = _template_alert(alert, voice_mode)

    if DISCLAIMER not in text:
        text = f"{text} {DISCLAIMER}"
    return text[:320]
