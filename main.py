"""
WhatsApp Important Message Extractor & Filter - Main Entry Point.
Orchestrates Playwright browser automation, message filtering, storage, and notification alerts.
"""

import argparse
import asyncio
import signal
import sys
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from config import DEFAULT_TARGET_CHATS, POLL_INTERVAL_SECONDS, HEADLESS, FORWARD_CONTACT
from whatsapp_client import WhatsAppClient
from filter_engine import MessageFilterEngine
from storage import StorageManager
from notifier import NotifierManager

console = Console()
running = True


def handle_shutdown(sig, frame):
    """Handle graceful shutdown signals."""
    global running
    console.print("\n[bold yellow][!] Shutdown signal received. Cleaning up...[/bold yellow]")
    running = False


async def run_monitoring_loop(
    target_chats: List[str],
    poll_interval: int,
    headless: bool,
    forward_contact: Optional[str] = FORWARD_CONTACT
):
    """Main asynchronous execution loop."""
    global running

    console.print(Panel.fit(
        "[bold green]WhatsApp Important Message Extractor & Filter[/bold green]\n"
        "[dim]Playwright Persistent Context | Smart Categorization | SQLite Log | Telegram Alerts[/dim]",
        border_style="green"
    ))

    # Initialize Modules
    storage = StorageManager()
    await storage.init_db()

    filter_engine = MessageFilterEngine()
    notifier = NotifierManager()
    client = WhatsAppClient(headless=headless)

    console.print(f"[info][*] Target Chats to Monitor:[/info] {', '.join(target_chats)}")
    console.print(f"[info][*] Poll Interval:[/info] {poll_interval} seconds")
    console.print(f"[info][*] Headless Mode:[/info] {headless}")

    # Step 1: Launch Browser
    try:
        await client.start()
    except Exception as e:
        console.print(f"[bold red][ERROR] Failed to start browser context: {e}[/bold red]")
        return

    # Step 2: Authenticate Session
    authenticated = await client.wait_for_login(timeout_seconds=120)
    if not authenticated:
        console.print("[bold red][!] Authentication failed or timed out. Exiting.[/bold red]")
        await client.close()
        return

    console.print("[bold green][✓] Session ready! Starting real-time extraction loop...[/bold green]\n")

    cycle_count = 0

    while running:
        cycle_count += 1
        console.print(f"[dim]--- Monitoring Cycle #{cycle_count} ---[/dim]")

        # Verify Connection
        is_alive = await client.check_connection()
        if not is_alive:
            console.print("[yellow][!] Connection interrupted. Attempting to restore...[/yellow]")
            await asyncio.sleep(5)
            continue

        new_extracted_count = 0

        for chat in target_chats:
            if not running:
                break

            console.print(f"[cyan][*] Monitoring Chat:[/cyan] [bold]{chat}[/bold]")

            opened = await client.search_and_open_chat(chat)
            if not opened:
                console.print(f"  [dim]└─ Chat '{chat}' not visible or not found.[/dim]")
                continue

            # Extract Messages
            raw_messages = await client.extract_recent_messages(chat, limit=15)

            for raw_msg in raw_messages:
                # Filter & Classify
                processed = filter_engine.process_message(
                    chat_name=raw_msg["chat_name"],
                    sender=raw_msg["sender"],
                    timestamp=raw_msg["timestamp"],
                    text=raw_msg["text"]
                )

                if processed:
                    # Save to DB (returns True if new)
                    is_new = await storage.save_message(processed)

                    if is_new:
                        new_extracted_count += 1
                        icon = "📢" if processed["category"] == "ANNOUNCEMENT" else ("📅" if processed["category"] == "TIMETABLE" else "🎓")
                        
                        console.print(
                            f"  [bold green]➜ {icon} NEW IMPORTANT MESSAGE DETECTED![/bold green]\n"
                            f"    [bold]Category:[/bold] {processed['category']} | [bold]Sender:[/bold] {processed['sender']}\n"
                            f"    [bold]Tags:[/bold] {', '.join(processed['tags'])}\n"
                            f"    [dim]Preview:[/dim] {processed['content'][:100]}..."
                        )

                        # Trigger Notification Alert (Telegram / Webhook)
                        alert_sent = await notifier.notify(processed)
                        if alert_sent:
                            await storage.mark_as_notified(processed["hash"])
                            console.print("    [dim]└─ Instant Alert Dispatched Successfully.[/dim]")

                        # Forward to designated WhatsApp Contacts / Groups
                        if forward_contact:
                            forward_msg = filter_engine.generate_formatted_forward(processed)
                            destinations = [d.strip() for d in forward_contact.split(",") if d.strip()]
                            for dest in destinations:
                                console.print(f"    [cyan]➜ Forwarding formatted notice to: [bold]{dest}[/bold]...[/cyan]")
                                sent = await client.send_whatsapp_message(dest, forward_msg)
                                if sent:
                                    console.print(f"      [green][✓] Forwarded successfully to {dest}![/green]")
                                else:
                                    console.print(f"      [yellow][!] Could not forward to {dest}.[/yellow]")

            await asyncio.sleep(2.0)

        if new_extracted_count == 0:
            console.print("  [dim]└─ No new important messages found in this cycle.[/dim]")

        # Perform keep-alive mouse move
        await client.keep_alive()

        # Wait until next cycle
        for _ in range(poll_interval):
            if not running:
                break
            await asyncio.sleep(1)

    # Cleanup on exit
    await client.close()
    console.print("[bold green][✓] Cleanup complete. Shutdown successfully.[/bold green]")


async def display_summary():
    """Display a formatted summary table of all extracted messages stored in DB."""
    storage = StorageManager()
    summary = await storage.get_daily_summary()

    table = Table(title="WhatsApp Important Messages Summary Report", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan", width=15)
    table.add_column("Chat Group", style="green", width=22)
    table.add_column("Sender", style="yellow", width=18)
    table.add_column("Timestamp", style="dim", width=15)
    table.add_column("Message Preview", style="white")

    total_count = 0
    for category, messages in summary.items():
        for msg in messages:
            total_count += 1
            table.add_row(
                category,
                msg["chat_name"],
                msg["sender"],
                msg["timestamp"],
                msg["content"][:80].replace("\n", " ") + "..."
            )

    console.print(table)
    console.print(f"\n[bold green]Total Extracted Important Messages:[/bold green] {total_count}")


def main():
    """CLI Argument Parser & Dispatcher."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    parser = argparse.ArgumentParser(description="WhatsApp Important Message Extractor & Filter")
    parser.add_argument(
        "--headless",
        action="store_true",
        default=HEADLESS,
        help="Run browser in headless mode (use --no-headless for first-time QR scan)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Run browser in visible (headful) mode to scan QR code"
    )
    parser.add_argument(
        "--target-chats",
        type=str,
        default=",".join(DEFAULT_TARGET_CHATS),
        help="Comma-separated target chat names to monitor"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=POLL_INTERVAL_SECONDS,
        help="Polling interval in seconds between monitoring cycles"
    )
    parser.add_argument(
        "--forward-to",
        type=str,
        default=FORWARD_CONTACT,
        help="WhatsApp contact name to forward important messages and summaries to"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary report of stored messages and exit"
    )

    args = parser.parse_args()

    if args.summary:
        asyncio.run(display_summary())
        sys.exit(0)

    target_chat_list = [c.strip() for c in args.target_chats.split(",") if c.strip()]

    try:
        asyncio.run(run_monitoring_loop(
            target_chats=target_chat_list,
            poll_interval=args.poll_interval,
            headless=args.headless,
            forward_contact=args.forward_to
        ))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
