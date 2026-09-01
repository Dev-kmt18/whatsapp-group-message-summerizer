"""
Notification module for Telegram Bot alerts, custom Webhook calls, and summary reports.
"""

import httpx
from typing import Dict, Optional
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALERT_WEBHOOK_URL

CATEGORY_ICONS = {
    "ANNOUNCEMENT": "📢",
    "TIMETABLE": "📅",
    "EVENT": "🎓"
}


class NotifierManager:
    """Handles notification delivery across multiple channels."""

    def __init__(
        self,
        telegram_token: str = TELEGRAM_BOT_TOKEN,
        telegram_chat_id: str = TELEGRAM_CHAT_ID,
        webhook_url: str = ALERT_WEBHOOK_URL
    ):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url

    def format_telegram_message(self, msg: Dict) -> str:
        """Format message into clean Telegram HTML markup."""
        icon = CATEGORY_ICONS.get(msg.get("category", ""), "📌")
        category = msg.get("category", "NOTICE")
        chat = msg.get("chat_name", "WhatsApp Group")
        sender = msg.get("sender", "Unknown")
        timestamp = msg.get("timestamp", "")
        content = msg.get("content", "")
        tags = ", ".join(msg.get("tags", []))

        text = (
            f"<b>{icon} {category} DETECTED</b>\n"
            f"💬 <b>Group:</b> {chat}\n"
            f"👤 <b>Sender:</b> {sender}\n"
            f"🕒 <b>Time:</b> {timestamp}\n"
            f"🏷️ <b>Tags:</b> <code>{tags}</code>\n\n"
            f"📝 <b>Message:</b>\n{content}"
        )
        return text

    async def send_telegram_alert(self, msg: Dict) -> bool:
        """Send instant alert to Telegram Bot."""
        if not self.telegram_token or not self.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": self.format_telegram_message(msg),
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPError as e:
                print(f"[ERROR] Failed to send Telegram alert: {e}")
                return False

    async def send_webhook_alert(self, msg: Dict) -> bool:
        """Send JSON alert to a generic HTTP Webhook endpoint."""
        if not self.webhook_url:
            return False

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(self.webhook_url, json=msg)
                response.raise_for_status()
                return True
            except httpx.HTTPError as e:
                print(f"[ERROR] Failed to send Webhook alert: {e}")
                return False

    async def notify(self, msg: Dict) -> bool:
        """Dispatch notification through all enabled channels."""
        success_telegram = await self.send_telegram_alert(msg)
        success_webhook = await self.send_webhook_alert(msg)
        return success_telegram or success_webhook
