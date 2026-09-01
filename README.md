# WhatsApp Real-Time Important Message Extractor & Filter

A modular, production-ready Python automation tool built with **Playwright (Async)**, **SQLite**, and **Rich** to monitor designated WhatsApp Web group chats in real-time, filter out noise/casual chatter, extract critical announcements, timetables, and events, store them locally, and send instant alerts to a Telegram Bot or custom Webhook.

---

## Key Features

- 🔑 **Persistent Browser Session**: Reuses Playwright context (`user_data_dir`) so QR code scanning is only required once.
- 🎯 **Target Chat Monitoring**: Scans specific WhatsApp group chats or individual chats periodically or in real-time.
- 🧠 **Smart NLP & Rule Filter**:
  - Automatically filters out greetings ("hi", "gm", "thanks"), emojis, memes, and short banter.
  - Retains and tags priority messages:
    - 📢 **Announcements / Notices / Official Alerts**
    - 📅 **Class Timetables / Exam Schedules / Rescheduled Lectures**
    - 🎓 **Events / Workshops / Webinars / Registration Links**
- 💾 **Deduplication & Storage**:
  - Generates deterministic SHA256 hashes per message to prevent duplicate processing.
  - Stores full history in **SQLite database** (`whatsapp_messages.db`) and **JSON log** (`important_messages.json`).
- ⚡ **Instant Alerts**:
  - Instant notifications sent to a **Telegram Bot** (HTML formatted with action icons).
  - Webhook dispatch support for integration with third-party automation webhooks (n8n, Zapier, custom APIs).
- 🛡️ **Session Resilience & Auto-Keepalive**: Includes keepalive interactions, disconnect detection, and robust DOM fallback selectors.

---

## Project Architecture

```
whatsapp agent/
├── config.py              # Selectors, environment loading, classification rules & thresholds
├── filter_engine.py       # Noise elimination and rule-based NLP classification engine
├── storage.py             # Asynchronous SQLite DB manager and JSON logger
├── notifier.py            # Telegram Bot & Webhook notification dispatcher
├── whatsapp_client.py     # Playwright persistent context browser automation client
├── main.py                # Main CLI entry point & continuous monitoring loop
├── test_filter_engine.py  # Unit tests for rule engine and classification
├── requirements.txt       # Python dependencies
├── .env.example           # Configuration template
└── README.md              # Setup and usage documentation
```

---

## Step-by-Step Setup Instructions

### 1. Install System Dependencies & Playwright Browsers

Ensure Python 3.9+ is installed. Clone/navigate to the project folder and run:

```bash
# Install Python packages
pip install -r requirements.txt

# Install Playwright Chromium browser binary
playwright install chromium
```

### 2. Configure Environment Variables (Optional for Notifications)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to set your credentials:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890
ALERT_WEBHOOK_URL=https://your-webhook-endpoint.com/api/alerts
POLL_INTERVAL_SECONDS=15
```

---

## Initial Session Setup (Scan QR Code Once)

Run the script in **visible mode (`--no-headless`)** for the initial run to scan the WhatsApp Web QR code:

```bash
python main.py --no-headless --target-chats "College Announcements, Class Group, Work Team"
```

1. Chromium will open `https://web.whatsapp.com`.
2. Scan the QR code using WhatsApp on your phone (`Linked Devices` -> `Link a Device`).
3. Once logged in, the session state is saved in `./whatsapp_user_data`.
4. Subsequent runs can be executed in **headless mode**!

---

## Usage Guide

### 1. Continuous Monitoring (Headless Mode)

```bash
python main.py --headless --target-chats "College Announcements, Class Group, Work Team" --poll-interval 15
```

### 2. View Summary Report of Extracted Messages

To view a formatted terminal table of all extracted messages stored in the SQLite database:

```bash
python main.py --summary
```

### 3. Run Unit Tests

```bash
python3 test_filter_engine.py
```

---

## Best Practices to Avoid Session Disconnects & Timeouts

1. **Keep `--poll-interval` Reasonable**: Set poll interval between `15` and `60` seconds to avoid excessive DOM churn.
2. **Keep Browser Active**: The `whatsapp_client.py` includes a `keep_alive()` method that issues subtle interactions to keep the WebSocket active.
3. **Dedicated WhatsApp Web Device**: Ensure your phone maintains internet connectivity or multi-device feature is enabled.
4. **Persistent Profile Backup**: Keep the `./whatsapp_user_data` directory intact across system restarts.

---

## License

MIT License. Free for personal, academic, and open-source usage.
