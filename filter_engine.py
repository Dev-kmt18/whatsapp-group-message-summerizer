"""
Filter Engine for WhatsApp Messages.
Classifies messages into priority categories (ANNOUNCEMENT, TIME_TABLE, EVENT_PROGRAM, STUDY_MATERIAL, SPAM_CASUAL)
and extracts structured actionable metadata with branch-specific filtering.
"""

import re
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from config import CATEGORY_RULES, NOISE_PATTERNS


class MessageFilterEngine:
    """Intelligent classification and structured JSON extraction engine."""

    def __init__(self, category_rules: Optional[Dict] = None, noise_patterns: Optional[List[str]] = None):
        self.rules = category_rules or CATEGORY_RULES
        # Add Notes / Study Material rule if not present
        if "STUDY_MATERIAL" not in self.rules:
            self.rules["STUDY_MATERIAL"] = {
                "keywords": [
                    "notes", "pdf", "handwritten", "module", "unit", "assignment",
                    "study material", "book", "cheatsheet", "drive link", "slides", "ppt", "question paper"
                ],
                "weight": 2.0
            }
        self.noise_patterns = [re.compile(p, re.IGNORECASE) for p in (noise_patterns or NOISE_PATTERNS)]

    def generate_message_hash(self, chat_name: str, sender: str, timestamp: str, text: str) -> str:
        """Create a unique deterministic SHA256 hash for deduplication."""
        raw_key = f"{chat_name.strip()}|{sender.strip()}|{timestamp.strip()}|{text.strip()}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def is_noise(self, text: str) -> bool:
        """Return True if message is greeting, emoji reaction, casual chatter, or bot's own alert."""
        clean_text = text.strip()
        if not clean_text:
            return True

        # Extremely short non-informative messages (< 4 chars unless containing digits/links)
        if len(clean_text) < 4 and not any(c.isdigit() for c in clean_text) and "http" not in clean_text:
            return True

        # Ignore bot's own generated forwarded alerts to prevent loops
        if "IMPORTANT NOTICE ALERT" in clean_text or "From Group:" in clean_text or "Full Message:" in clean_text or "Original Message:" in clean_text:
            return True

        # Ignore WhatsApp system event strings
        system_events = [
            "joined from the community",
            "joined using this group",
            "messages and calls are end-to-end encrypted",
            "left the group",
            "was added",
            "changed the group",
            "security code changed",
            "waiting for this message"
        ]
        lower_clean = clean_text.lower()
        if any(ev in lower_clean for ev in system_events):
            return True

        # Match against noise patterns
        for pattern in self.noise_patterns:
            if pattern.search(clean_text):
                return True

        return False

    def classify(self, text: str) -> Tuple[str, List[str], float]:
        """
        Classify message content into primary category:
        (ANNOUNCEMENT, TIME_TABLE, EVENT_PROGRAM, STUDY_MATERIAL, SPAM_CASUAL)
        """
        if self.is_noise(text):
            return "SPAM_CASUAL", [], 0.0

        lower_text = text.lower()
        matched_tags = []
        category_scores: Dict[str, float] = {}

        cat_mapping = {
            "ANNOUNCEMENT": "ANNOUNCEMENT",
            "TIMETABLE": "TIME_TABLE",
            "EVENT": "EVENT_PROGRAM",
            "STUDY_MATERIAL": "STUDY_MATERIAL"
        }

        for category, rule in self.rules.items():
            score = 0.0
            keywords = rule.get("keywords", [])
            weight = rule.get("weight", 1.0)

            target_category_name = cat_mapping.get(category, category)

            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', lower_text):
                    score += 1.0 * weight
                    matched_tags.append(kw)
                elif kw in lower_text:
                    score += 0.5 * weight

            if score > 0:
                category_scores[target_category_name] = score

        has_link = bool(re.search(r'https?://\S+|www\.\S+', text))
        has_date_time = bool(re.search(r'\b(\d{1,2}:\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|mon|tue|wed|thu|fri|sat|sun|pm|am)\b', lower_text))

        if has_link:
            matched_tags.append("contains_link")
        if has_date_time:
            matched_tags.append("contains_datetime")

        if not category_scores:
            if has_link and has_date_time:
                return "ANNOUNCEMENT", matched_tags, 1.5
            return "SPAM_CASUAL", [], 0.0

        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        primary_category, top_score = sorted_categories[0]

        if top_score >= 1.0:
            return primary_category, list(set(matched_tags)), top_score

        return "SPAM_CASUAL", [], 0.0

    def extract_deadline_or_time(self, text: str) -> Optional[str]:
        """Extract explicit dates, days, or time strings from message."""
        patterns = [
            r'\b(?:by|due|on|before|at|until)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)?)\b',
            r'\b(?:tomorrow|today|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b',
            r'\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)?\b',
            r'\b\d{1,2}(?::\d{2})\s*(?:AM|PM|am|pm)\b'
        ]

        for p in patterns:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        return None

    def is_action_required(self, text: str) -> bool:
        """Determine if message demands user action (submission, registration, payment, attendance)."""
        action_keywords = [
            "submit", "submission", "register", "registration", "pay", "fee", "due",
            "fill", "form", "attend", "compulsory", "mandatory", "bring", "report to",
            "join link", "upload", "complete"
        ]
        lower_text = text.lower()
        return any(re.search(r'\b' + re.escape(kw) + r'\b', lower_text) for kw in action_keywords)

    def extract_title(self, text: str) -> str:
        """Derive a clean, concise title from the text."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return "WhatsApp Notice"

        clean_title = re.sub(r'^[\*#\_~:\s\-]+', '', lines[0]).strip()
        if len(clean_title) > 60:
            clean_title = clean_title[:57] + "..."
        return clean_title or "Notice Update"

    def parse_message_to_dict(self, text: str) -> Dict[str, Any]:
        """Return structured dictionary according to requirements."""
        category, tags, score = self.classify(text)
        is_important = (category != "SPAM_CASUAL")
        
        title = self.extract_title(text) if is_important else "Casual Message"
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        key_details = " ".join(lines[:2]) if lines else text.strip()
        if len(key_details) > 200:
            key_details = key_details[:197] + "..."

        deadline = self.extract_deadline_or_time(text) if is_important else None
        action_req = self.is_action_required(text) if is_important else False

        return {
            "category": category,
            "is_important": is_important,
            "title": title,
            "key_details": key_details,
            "deadline_or_time": deadline,
            "action_required": action_req
        }

    def parse_message_to_json(self, text: str) -> str:
        """Return strict JSON string representation without markdown formatting."""
        parsed_dict = self.parse_message_to_dict(text)
        return json.dumps(parsed_dict, indent=2, ensure_ascii=False)

    def process_message(
        self, chat_name: str, sender: str, timestamp: str, text: str
    ) -> Optional[Dict]:
        """
        Main handler with Mechanical-branch specific logic for NIT Srinagar.
        """
        clean_text = text.strip()
        sender_clean = (sender or "").strip().lower()

        # Strict ignore of self / bot sender or destination group to prevent loops
        if sender_clean in ["you", "me", "myself", "akshuu", "akshuuu"] or "ai summery" in chat_name.lower():
            return None

        lower_text = clean_text.lower()

        # Ignore casual student queries/banter like "class kha lagegi", "kaha ho", "send link"
        if re.search(r'\b(kha lagegi|kaha lagegi|kaha hai|kha hai|kisi ke pass|bhej do|kaha ho|kab hogi)\b', lower_text):
            return None

        is_mech = bool(re.search(r'\b(mech|mechanical|mechainal|drawing|ed|workshop)\b', lower_text))
        other_branches = bool(re.search(r'\b(ece|cse|civil|electrical|chemical|metallurgy|meta|it)\b', lower_text))
        is_all_batch = bool(re.search(r'\b(all students|all batches|circular|notice|exam|midterm|endsem|holiday|fee|director|dean|hostel|mess)\b', lower_text))

        # Filter out messages specific to other branches
        if other_branches and not is_mech and not is_all_batch:
            return None

        # Check Branch Specific Rule for "Nit srinagar batch 2026-30":
        if "nit srinagar" in chat_name.lower():
            if not is_mech and not is_all_batch:
                return None

        parsed = self.parse_message_to_dict(clean_text)
        if not parsed["is_important"]:
            return None

        msg_hash = self.generate_message_hash(chat_name, sender, timestamp, clean_text)
        category, tags, score = self.classify(clean_text)

        category_db = "ANNOUNCEMENT" if category == "ANNOUNCEMENT" else (
            "TIMETABLE" if category == "TIME_TABLE" else (
                "STUDY_MATERIAL" if category == "STUDY_MATERIAL" else "EVENT"
            )
        )

        return {
            "hash": msg_hash,
            "chat_name": chat_name.strip(),
            "sender": sender.strip() or "Unknown Sender",
            "timestamp": timestamp.strip(),
            "content": clean_text,
            "category": category_db,
            "tags": tags,
            "score": round(score, 2),
            "is_important": True,
            "parsed_structured": parsed
        }

    def generate_ai_summary(self, text: str) -> str:
        """Call Groq API (openai/gpt-oss-120b) to generate high-quality bullet summary."""
        try:
            from config import GROQ_API_KEY, GROQ_MODEL
            if not GROQ_API_KEY:
                return ""
            import httpx
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            prompt = (
                "You are an assistant for an Indian engineering college student. "
                "Summarize this WhatsApp notice into 1 or 2 concise bullet points. "
                "Explicitly highlight any timing, venue, dates/deadlines, and exact required actions. "
                "Do not add greetings or extra text:\n\n"
                f"{text}"
            )
            payload = {
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.2
            }
            with httpx.Client(timeout=6.0) as client:
                resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    ai_text = data["choices"][0]["message"]["content"].strip()
                    cleaned_lines = [l.strip() for l in ai_text.split("\n") if l.strip()]
                    return "\n".join(cleaned_lines)
        except Exception:
            pass
        return ""

    def generate_formatted_forward(self, processed: Dict) -> str:
        """Format the message cleanly with Summary at the TOP, followed by metadata and links."""
        parsed = processed.get("parsed_structured", {})
        category = processed.get("category", "NOTICE")
        group = processed.get("chat_name", "Group")
        sender = processed.get("sender", "Unknown")
        timestamp = processed.get("timestamp", "Recent")
        content = processed.get("content", "")
        summary = parsed.get("key_details", content[:150])
        deadline = parsed.get("deadline_or_time")

        icon = "📢" if category == "ANNOUNCEMENT" else (
            "📅" if category == "TIMETABLE" else (
                "📚" if category == "STUDY_MATERIAL" else "🎓"
            )
        )

        lines = [
            "🔔 *IMPORTANT NOTICE ALERT* 🔔",
            ""
        ]

        # Check if notice/event is TODAY or TOMORROW (Red Urgent Alert)
        lower_content = content.lower()
        is_today = any(w in lower_content for w in ["today", "aaj", "aaj hi", "tonight", "3:30 pm onwards"])
        is_tomorrow = any(w in lower_content for w in ["tomorrow", "kal", "kal hi"])

        if is_today:
            lines.append("🚨 *URGENT ALERT: HAPPENING TODAY!* 🚨")
            if deadline:
                lines.append(f"🔴 *Timing:* {deadline}")
            lines.append("")
        elif is_tomorrow:
            lines.append("⚠️ *URGENT ALERT: SCHEDULED FOR TOMORROW!* ⚠️")
            if deadline:
                lines.append(f"🔴 *Timing:* {deadline}")
            lines.append("")

        # Put Summary on TOP
        ai_summary = self.generate_ai_summary(content)
        if ai_summary:
            lines.append("📋 *AI Summary:*")
            lines.append(ai_summary)
        else:
            lines.append("📋 *Summary:*")
            lines.append(f"• {summary}")
            if parsed.get("action_required"):
                lines.append("• ⚠️ *Action Required:* Please review instructions / complete required steps.")

        # Document / File detection
        docs = re.findall(r'[\w,\s-]+\.(?:pdf|pptx|docx|ppt)', content, re.IGNORECASE)

        # Metadata
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━",
            f"👥 *Group:* {group}",
            f"👤 *Sender:* {sender}",
            f"🕒 *Time:* {timestamp}",
            f"📌 *Category:* {icon} {category}"
        ])
        if docs:
            lines.append(f"📁 *Attached File:* {docs[0].strip()}")
        if deadline and not (is_today or is_tomorrow):
            lines.append(f"⏰ *Timing/Deadline:* {deadline}")

        # Extract links
        links = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', content)
        if links:
            lines.append("")
            lines.append("🔗 *Links / Action:*")
            for lk in set(links):
                lines.append(f"👉 {lk}")

        # Original Notice
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━",
            "📝 *Original Notice:*",
            content
        ])

        return "\n".join(lines)
