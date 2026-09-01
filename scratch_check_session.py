import asyncio
from playwright.async_api import async_playwright
import os

async def check():
    user_data_dir = "./whatsapp_user_data"
    os.makedirs(user_data_dir, exist_ok=True)
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.pages[0] if context.pages else await context.new_page()
        print("[DEBUG] Navigating to WhatsApp Web...")
        await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=60000)
        
        await asyncio.sleep(8)
        
        title = await page.title()
        print(f"[DEBUG] Page Title: '{title}'")
        
        screenshot_path = "./scratch_wa.png"
        await page.screenshot(path=screenshot_path)
        print(f"[DEBUG] Saved screenshot to {screenshot_path}")

        qr_canvas = await page.query_selector("canvas, div[data-ref]")
        chat_pane = await page.query_selector("#pane-side, div[data-testid='chat-list'], div[contenteditable='true']")
        
        print(f"[DEBUG] QR canvas found: {qr_canvas is not None}")
        print(f"[DEBUG] Chat pane found: {chat_pane is not None}")

        await context.close()

if __name__ == "__main__":
    asyncio.run(check())
