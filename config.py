"""
Configuration module for WhatsApp Important Message Extractor.
Contains environment loading, Playwright DOM selectors, keyword filters, and system paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

# Browser Session Settings
USER_DATA_DIR = os.getenv("USER_DATA_DIR", str(BASE_DIR / "whatsapp_user_data"))
HEADLESS = os.getenv("HEADLESS", "False").lower() in ("true", "1", "t")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))

# Storage Paths
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "whatsapp_messages.db"))
JSON_LOG_PATH = os.getenv("JSON_LOG_PATH", str(BASE_DIR / "important_messages.json"))

# Notification Credentials & Forwarding
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
FORWARD_CONTACT = os.getenv("FORWARD_CONTACT", "Ai summery, Akshuuu")

# Groq AI LLM Settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Default Target Chats to Monitor (can be overridden via CLI args or env)
DEFAULT_TARGET_CHATS = [
    "Info Mechanical 2026",
    "Royal Mechanical (26-30)",
    "BEE_Mech_Autumn 2026",
    "Engineering Drawing",
    "Engineering Chemistry",
    "INDUS HOSTEL BATCH 2026",
    "Nit srinagar batch 2026-30"
]

# Robust WhatsApp Web DOM Selectors (Attribute & Text fallback based)
SELECTORS = {
    # Main container indicators
    "app_container": "div#app",
    "qr_canvas": "canvas[aria-label*='Scan'], div[data-ref]",
    "pane_side": "#pane-side, div[data-testid='chat-list'], div[contenteditable='true'], header span[title], div[role='grid']",
    
    # Chat search & list
    "search_input": "div[contenteditable='true'][data-tab='3'], div[contenteditable='true'][role='textbox'], p.selectable-text.copyable-text, label div[contenteditable='true'], div._ai1w",
    "chat_list_items": "#pane-side div[role='gridcell'], #pane-side div[aria-selected]",
    "chat_title": "span[title], div[aria-label] span[dir='auto']",
    "unread_badge": "span[aria-label*='unread message'], span[data-testid='icon-unread-count']",
    
    # Main chat pane & message input
    "active_chat_header": "header span[title]",
    "message_list_container": "div[data-testid='conversation-panel-wrapper'], div.copyable-area",
    "message_rows": "div[role='row'], div[data-testid='msg-container']",
    "message_input": "footer div[contenteditable='true'][role='textbox'], footer p.selectable-text, footer div[contenteditable='true'], div[contenteditable='true'][data-tab='10']",
    
    # Message bubble breakdown
    "message_bubble": "div.message-in, div.message-out, div[data-testid*='msg-']",
    "sender_name": "span[aria-label*=':'], span.copyable-text[data-pre-plain-text], div._amvy, span._ao3e",
    "timestamp_element": "span[data-pre-plain-text], div[data-pre-plain-text], span[dir='auto']",
    "message_text": "span.selectable-text.copyable-text, div.copyable-text span",
    
    # Disconnect indicators
    "phone_disconnected": "div[data-testid='popup-contents'], div[aria-label*='Phone not connected']"
}

# Categorization Keywords & RegEx Rules
CATEGORY_RULES = {
    "ANNOUNCEMENT": {
        "keywords": [
            "notice", "announcement", "important", "attention", "circular",
            "deadline", "urgent", "note", "mandatory", "official", "alert",
            "submission", "reminder", "form link", "instruction", "policy", "regard"
        ],
        "weight": 2.0
    },
    "TIMETABLE": {
        "keywords": [
            "timetable", "schedule", "class", "exam", "test", "quiz", "midterm",
            "endsem", "viva", "lecture", "lab", "rescheduled", "cancelled",
            "due date", "room no", "venue", "slot", "timing", "batch", "syllabus"
        ],
        "weight": 2.5
    },
    "EVENT": {
        "keywords": [
            "event", "workshop", "webinar", "seminar", "hackathon", "competition",
            "guest lecture", "registration", "certificate", "speaker", "join us",
            "register at", "meet link", "zoom link", "google meet", "fest", "symposium"
        ],
        "weight": 2.0
    }
}

# Noise & Casual Chatter to Ignore
NOISE_PATTERNS = [
    r"^(hi|hello|hey|gm|gn|good morning|good evening|good night|thanks|thank you|ok|okay|k|thx|tq)\b",
    r"^(hbd|happy birthday|congrats|congratulations)\b",
    r"^\s*$",  # empty or whitespace only
    r"^(👍|❤️|🙏|😊|😂|🤣|🙌|🔥|✨)+$"  # emoji-only strings
]
