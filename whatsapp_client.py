"""
WhatsApp Web Playwright Client.
Provides persistent browser context management, DOM message scraping, chat navigation,
session keepalive, and disconnect handling.
"""

import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from config import SELECTORS, USER_DATA_DIR, HEADLESS


class WhatsAppClient:
    """Async Playwright automation client for WhatsApp Web."""

    def __init__(
        self,
        user_data_dir: str = USER_DATA_DIR,
        headless: bool = HEADLESS,
        selectors: Optional[Dict] = None
    ):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.selectors = selectors or SELECTORS
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._is_connected = False

    async def start(self):
        """Launch persistent browser context and load WhatsApp Web."""
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()
        
        # Chromium flags to prevent idle timeouts & maintain stable session
        args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-blink-features=AutomationControlled"
        ]

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            args=args
        )

        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)

    async def wait_for_login(self, timeout_seconds: int = 180) -> bool:
        """Wait for user authentication (QR scan or existing session restore)."""
        if not self.page:
            return False

        print("[INFO] Checking WhatsApp Web login status...", flush=True)

        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            # Check if any logged-in element is visible in DOM
            try:
                logged_in_el = await self.page.query_selector(self.selectors["pane_side"])
                if logged_in_el:
                    print("[SUCCESS] WhatsApp Web session authenticated successfully!", flush=True)
                    self._is_connected = True
                    return True
            except Exception:
                pass

            # Check if QR code canvas is present
            try:
                qr_el = await self.page.query_selector(self.selectors["qr_canvas"])
                if qr_el and await qr_el.is_visible():
                    if self.headless:
                        print("[WARNING] QR Code detected! Run main.py with --no-headless to scan.", flush=True)
                        return False
            except Exception:
                pass

            await asyncio.sleep(1.0)

        print("[ERROR] Login timeout reached. Please check browser window.", flush=True)
        return False

    async def check_connection(self) -> bool:
        """Verify session is still active and not disconnected."""
        if not self.page:
            return False

        try:
            # Check for pane-side presence
            pane = await self.page.query_selector(self.selectors["pane_side"])
            if not pane:
                # Check for disconnect popup
                disconnect_popup = await self.page.query_selector(self.selectors["phone_disconnected"])
                if disconnect_popup:
                    print("[WARNING] Phone disconnected alert detected on WhatsApp Web!")
                self._is_connected = False
                return False

            self._is_connected = True
            return True
        except Exception:
            self._is_connected = False
            return False

    async def keep_alive(self):
        """Periodic interaction to keep WebSocket connection active and prevent timeout."""
        if not self.page or not self._is_connected:
            return

        try:
            # Slight mouse move over chat list
            await self.page.mouse.move(100, 200)
            await self.page.mouse.move(100, 220)
        except Exception:
            pass

    async def get_available_chats(self) -> List[str]:
        """Fetch visible target chat titles from the side panel."""
        if not self.page:
            return []

        chat_names = []
        try:
            items = await self.page.query_selector_all(self.selectors["chat_list_items"])
            for item in items:
                title_el = await item.query_selector(self.selectors["chat_title"])
                if title_el:
                    name = await title_el.get_attribute("title") or await title_el.inner_text()
                    if name and name.strip():
                        chat_names.append(name.strip())
        except Exception as e:
            print(f"[DEBUG] Error reading chat titles: {e}")

        return list(set(chat_names))

    async def dismiss_modals(self):
        """Dismiss any blocking modal popups (e.g. desktop app promos, notification dialogs)."""
        if not self.page:
            return
        try:
            # Check for dialogs
            dialog = await self.page.query_selector("div[role='dialog']")
            if dialog:
                close_btn = await dialog.query_selector("button, [data-icon='x'], [aria-label*='Close'], [aria-label*='close']")
                if close_btn:
                    await close_btn.click(force=True)
                else:
                    await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
        except Exception:
            pass

    async def search_and_open_chat(self, chat_name: str) -> bool:
        """Search for a specific chat by name and open it."""
        if not self.page:
            return False

        await self.dismiss_modals()

        try:
            # 1. Check if chat is already active in header
            active_header = await self.page.query_selector(self.selectors["active_chat_header"])
            if active_header:
                current_title = await active_header.get_attribute("title") or await active_header.inner_text()
                if current_title and (chat_name.lower() in current_title.lower() or current_title.lower() in chat_name.lower()):
                    return True

            # 2. Check visible items anywhere on page using Playwright's case-insensitive locator
            clean_name = re.sub(r'\(.*?\)', '', chat_name).strip()
            short_name = clean_name.split()[0] if clean_name else chat_name

            locator = self.page.locator(f"span[title*='{clean_name}' i], span:text-matches('{clean_name}', 'i')").first
            if await locator.count() > 0 and await locator.is_visible():
                await locator.click(force=True)
                await asyncio.sleep(1.2)
                return True

            # 3. Otherwise, use search box
            search_input = self.page.locator("div#side div[contenteditable='true'], div[data-tab='3'], div[role='textbox']").first
            if await search_input.count() > 0:
                await search_input.click(force=True)
                await self.page.keyboard.press("Meta+A" if "mac" in str(self.page).lower() else "Control+A")
                await self.page.keyboard.press("Backspace")
                await search_input.fill(short_name)
                await asyncio.sleep(1.5)

                match_item = self.page.locator(f"div[role='listitem'] span[title*='{short_name}' i], div[role='listitem'] span:text-matches('{short_name}', 'i')").first
                if await match_item.count() > 0:
                    await match_item.click(force=True)
                    await asyncio.sleep(1.2)
                    return True

                first_result = self.page.locator("div#pane-side div[role='listitem']").first
                if await first_result.count() > 0:
                    await first_result.click(force=True)
                    await asyncio.sleep(1.2)
                    return True

        except Exception as e:
            print(f"[DEBUG] Chat '{chat_name}' search check: {e}", flush=True)

        return False

    async def extract_recent_messages(self, chat_name: str, limit: int = 15) -> List[Dict]:
        """Extract recent visible message bubbles from the currently opened chat."""
        if not self.page:
            return []

        extracted = []
        try:
            # Find message rows or bubbles
            messages = await self.page.query_selector_all(self.selectors["message_rows"])
            if not messages:
                messages = await self.page.query_selector_all(self.selectors["message_bubble"])

            # Slice to recent limit
            recent_bubbles = messages[-limit:] if len(messages) > limit else messages

            for msg_el in recent_bubbles:
                text_content = ""
                sender = "Group Member"
                timestamp = "Just Now"

                # Method A: Parse data-pre-plain-text attribute (Format: "[10:45 AM, 8/31/2026] John: ")
                copyable_el = await msg_el.query_selector("[data-pre-plain-text]")
                if copyable_el:
                    pre_text = await copyable_el.get_attribute("data-pre-plain-text")
                    if pre_text:
                        # Extract timestamp and sender using Regex
                        match = re.search(r"\[(.*?)\]\s*(.*?):", pre_text)
                        if match:
                            timestamp = match.group(1).strip()
                            sender = match.group(2).strip()

                # Method B: Extract complete text content (including image captions & multi-line notices)
                text_el = await msg_el.query_selector("span.selectable-text.copyable-text, div[data-testid='image-caption'], div._amvz span, span[dir='ltr']")
                if text_el:
                    text_content = await text_el.inner_text()
                else:
                    text_content = await msg_el.inner_text()

                # Also capture image description or OCR text from posters/flyers
                img_el = await msg_el.query_selector("img[src*='blob:'], div[data-testid='image-thumb'], img[alt]")
                if img_el:
                    img_alt = await img_el.get_attribute("alt") or ""
                    if img_alt and len(img_alt.strip()) > 5 and img_alt.strip() not in text_content:
                        text_content = f"{text_content}\n[Poster/Image: {img_alt.strip()}]"

                    # Run OCR on image if bubble has little or no text
                    if len(text_content.strip()) < 80:
                        try:
                            import tempfile
                            box = await img_el.bounding_box()
                            if box and box['width'] > 60 and box['height'] > 60:
                                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                                    tmp_path = tmp.name
                                await img_el.screenshot(path=tmp_path)
                                from filter_engine import MessageFilterEngine
                                ocr_text = MessageFilterEngine.extract_text_from_image(tmp_path)
                                try:
                                    os.remove(tmp_path)
                                except Exception:
                                    pass
                                if ocr_text and len(ocr_text.strip()) > 10:
                                    text_content = f"{text_content}\n[Poster Content / Club Details]:\n{ocr_text.strip()}".strip()
                        except Exception:
                            pass

                if text_content and text_content.strip():
                    extracted.append({
                        "chat_name": chat_name,
                        "sender": sender,
                        "timestamp": timestamp,
                        "text": text_content.strip()
                    })

        except Exception as e:
            print(f"[ERROR] Extraction error in chat '{chat_name}': {e}")

        return extracted

    async def send_whatsapp_message(self, contact_name: str, message_text: str) -> bool:
        """Send a message to a designated WhatsApp contact or group."""
        if not self.page or not message_text.strip():
            return False

        try:
            # 1. Open contact chat
            opened = await self.search_and_open_chat(contact_name)
            if not opened:
                print(f"[WARNING] Could not open contact '{contact_name}' to forward message.", flush=True)
                return False

            await asyncio.sleep(1.0)

            # 2. Locate footer input field
            msg_input = await self.page.wait_for_selector(
                self.selectors["message_input"],
                timeout=8000
            )

            if not msg_input:
                print(f"[ERROR] Message input field not found for '{contact_name}'.", flush=True)
                return False

            await msg_input.click(force=True)
            await asyncio.sleep(0.5)

            # 3. Fast line-by-line insert with Shift+Enter for perfect paragraphs & linebreaks
            lines = message_text.split("\n")
            for i, line in enumerate(lines):
                if line:
                    await self.page.keyboard.insert_text(line)
                if i < len(lines) - 1:
                    await self.page.keyboard.press("Shift+Enter")

            await asyncio.sleep(0.4)

            # 4. Click send button or press Enter
            send_btn = await self.page.query_selector("span[data-testid='send'], button[aria-label='Send'], span[data-icon='send']")
            if send_btn:
                await send_btn.click(force=True)
            else:
                await self.page.keyboard.press("Enter")

            await asyncio.sleep(1.5)
            print(f"[SUCCESS] Message forwarded successfully to WhatsApp contact: '{contact_name}'!", flush=True)
            return True

        except Exception as e:
            print(f"[ERROR] Failed to send message to '{contact_name}': {e}", flush=True)
            return False

    async def close(self):
        """Clean up browser context resources."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        print("[INFO] WhatsApp Client browser session closed cleanly.")
