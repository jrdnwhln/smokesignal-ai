# SmokeSignal AI

SmokeSignal AI is a local desktop backend prototype for an AI-powered market alert system. It monitors a default watchlist of stocks and crypto, checks market data and mock headlines, calculates a Confluence Score from 0 to 10, writes short alert messages in different voice modes, saves alerts to SQLite, and exposes local FastAPI routes for testing.

## What SmokeSignal AI Does

- Tracks a default watchlist of stocks and crypto.
- Pulls free delayed stock quote data from Stooq when available.
- Pulls live crypto market data from CoinGecko when available.
- Pulls live forex reference rates from Frankfurter when available.
- Falls back to mock market data if a live data source is unavailable.
- Pulls mock news headlines.
- Scores price movement, volume, volatility, news catalysts, and sentiment.
- Tracks stocks, crypto, and major forex pairs.
- Generates alert text in Professional, Clean Retail, Market Homie, or ATL Homie voice.
- Saves alerts to a local SQLite database.
- Prints alerts to the terminal.
- Provides FastAPI routes for local testing.
- Includes future-ready placeholders for Twilio SMS, push, and email alerts.

## What SmokeSignal AI Does Not Do

- It does not place trades.
- It does not connect to broker accounts.
- It does not provide financial advice.
- It does not tell users to buy or sell.
- It does not guarantee profits or outcomes.

## Safety and Legal Disclaimer

This tool is for market monitoring and education only. It does not provide financial advice, trading instructions, or guaranteed outcomes.

Every generated alert includes:

```text
Not financial advice. Market alerts only.
```

## Project Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install requirements:

```bash
pip install -r requirements.txt
```

Copy the environment example:

```bash
copy .env.example .env
```

## Configure `.env`

The MVP runs without API keys. Stock quotes try Stooq first, crypto data tries CoinGecko first, forex rates try Frankfurter first, then all fall back to mock data. News is still mock-first.

```env
APP_ENV=development
DATABASE_URL=sqlite:///./smokesignal.db

OPENAI_API_KEY=

MARKET_DATA_API_KEY=
NEWS_API_KEY=

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
SMS_ENABLED=false

HOURLY_UPDATES_ENABLED=false
```

Keep `SMS_ENABLED=false` until users have clearly opted in and Twilio is fully configured.

## Run the FastAPI App

```bash
uvicorn app.main:app --reload
```

Open the app:

```text
http://127.0.0.1:8000
```

Open local docs:

```text
http://127.0.0.1:8000/docs
```

Open the SMS subscription page:

```text
http://127.0.0.1:8000/subscribe
```

## Test `/scan`

In a browser:

```text
http://127.0.0.1:8000/scan
```

Or with PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/scan
```

Scan one symbol:

```text
http://127.0.0.1:8000/scan/NVDA
```

Stock scans use free delayed quote data when available:

```text
http://127.0.0.1:8000/scan/NVDA?voice_mode=atl_homie
```

Try a different voice mode:

```text
http://127.0.0.1:8000/scan/NVDA?voice_mode=market_homie
```

Try ATL Homie voice:

```text
http://127.0.0.1:8000/scan/BTC?voice_mode=atl_homie
```

Scan a forex pair:

```text
http://127.0.0.1:8000/scan/EURUSD?voice_mode=atl_homie
```

## Test Alert Generation

Run tests:

```bash
pytest
```

You can also generate alerts through:

- `GET /scan`
- `GET /scan/{symbol}`
- `GET /alerts`

## SMS Subscription Flow

Users can subscribe from:

```text
http://127.0.0.1:8000/subscribe
```

The form creates or updates a local user, opts them into SMS, seeds the default watchlist, and sends a welcome text only when Twilio and `SMS_ENABLED=true` are configured.

Useful routes:

- `POST /subscribe`
- `POST /unsubscribe`
- `GET /users`
- `GET /users/{user_id}/watchlist`
- `POST /hourly-update`
- `POST /scheduler/hourly/start`

`POST /hourly-update` runs one manual hourly digest in development. `POST /scheduler/hourly/start` starts the local hourly loop in development. To start it automatically when the app boots, set:

```env
HOURLY_UPDATES_ENABLED=true
```

## Twilio SMS Later

The `app/alert_sender.py` module includes `send_sms_alert(user, alert_text)`.

SMS will only send when:

- `SMS_ENABLED=true`
- the user has `sms_enabled=true`
- Twilio credentials are configured
- the user has opted in

Inbound opt-out words are handled by `POST /sms/webhook`:

- `STOP`
- `UNSUBSCRIBE`
- `CANCEL`
- `QUIT`

## Why SMS Is Disabled by Default

SMS should never be sent to users who have not opted in. The MVP saves and prints alerts locally first so development can happen safely without sending real messages or accidentally contacting users.

## Future Roadmap

### Phase 1

Local mock data MVP plus free stock quotes, live crypto data, and forex rate fallback.

### Phase 2

Deepen real stock and crypto data with better intraday candles and volume-average checks.

### Phase 3

Connect real stock/news data provider.

### Phase 4

Add user accounts and custom watchlists.

### Phase 5

Add Twilio SMS for opted-in users.

### Phase 6

Add mobile app with push notifications.

### Phase 7

Add AI-powered source monitoring for SEC filings, earnings, crypto exchange announcements, and major financial news.
