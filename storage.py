"""
Storage module for SQLite database management and JSON file exports.
Handles message deduplication and log persistence.
"""

import json
import sqlite3
import aiosqlite
from pathlib import Path
from typing import Dict, List, Optional
from config import DB_PATH, JSON_LOG_PATH


class StorageManager:
    """Manages SQLite database storage and JSON export operations asynchronously."""

    def __init__(self, db_path: str = DB_PATH, json_path: str = JSON_LOG_PATH):
        self.db_path = db_path
        self.json_path = json_path

    async def init_db(self):
        """Initialize the SQLite database schema if it doesn't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_hash TEXT UNIQUE NOT NULL,
                    chat_name TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    timestamp_raw TEXT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    score REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_notified INTEGER DEFAULT 0
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_message_hash ON messages(message_hash)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_category ON messages(category)")
            await db.commit()

    async def save_message(self, msg: Dict) -> bool:
        """
        Save a classified message to SQLite and update the JSON log file.
        Returns True if inserted (new message), False if duplicate (hash exists).
        """
        tags_json = json.dumps(msg.get("tags", []))
        inserted = False

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO messages 
                    (message_hash, chat_name, sender, timestamp_raw, content, category, tags, score, is_notified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        msg["hash"],
                        msg["chat_name"],
                        msg["sender"],
                        msg.get("timestamp", ""),
                        msg["content"],
                        msg["category"],
                        tags_json,
                        msg.get("score", 1.0)
                    )
                )
                await db.commit()
                inserted = True
            except sqlite3.IntegrityError:
                # Unique hash constraint violated -> Duplicate message
                inserted = False

        if inserted:
            await self._append_to_json_file(msg)

        return inserted

    async def _append_to_json_file(self, msg: Dict):
        """Append message record to JSON log file."""
        log_file = Path(self.json_path)
        existing_logs = []

        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    existing_logs = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing_logs = []

        existing_logs.append(msg)

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(existing_logs, f, indent=2, ensure_ascii=False)

    async def mark_as_notified(self, message_hash: str):
        """Mark a message as successfully notified in SQLite."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE messages SET is_notified = 1 WHERE message_hash = ?",
                (message_hash,)
            )
            await db.commit()

    async def fetch_unnotified(self) -> List[Dict]:
        """Fetch all messages that haven't been dispatched via notifier yet."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM messages WHERE is_notified = 0 ORDER BY id ASC"
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "hash": r["message_hash"],
                        "chat_name": r["chat_name"],
                        "sender": r["sender"],
                        "timestamp": r["timestamp_raw"],
                        "content": r["content"],
                        "category": r["category"],
                        "tags": json.loads(r["tags"]),
                        "score": r["score"],
                        "created_at": r["created_at"]
                    })
                return results

    async def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """Fetch recent extracted messages."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_daily_summary(self) -> Dict[str, List[Dict]]:
        """Group stored messages by category for summary reports."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM messages ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()

        summary: Dict[str, List[Dict]] = {
            "ANNOUNCEMENT": [],
            "TIMETABLE": [],
            "EVENT": []
        }

        for r in rows:
            cat = r["category"]
            item = {
                "chat_name": r["chat_name"],
                "sender": r["sender"],
                "timestamp": r["timestamp_raw"],
                "content": r["content"],
                "created_at": r["created_at"]
            }
            if cat in summary:
                summary[cat].append(item)
            else:
                summary.setdefault(cat, []).append(item)

        return summary
