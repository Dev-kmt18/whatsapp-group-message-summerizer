"""
Historical Message Scanner & Forwarder.
Scans messages from the last 2 days in a specific target group ("info Mechainal 2026"),
filters important notices/notes using NLP & Groq 120B AI, and forwards them to "Ai summery".
"""

import asyncio
import re
from typing import List, Dict
from rich.console import Console

from whatsapp_client import WhatsAppClient
from filter_engine import MessageFilterEngine
from storage import StorageManager
from config import USER_DATA_DIR, SELECTORS, FORWARD_CONTACT

console = Console()

async def scan_and_forward_history(target_group: str = "info Mechainal 2026", destination: str = "Ai summery"):
    console.print(f"[bold cyan]🔍 Starting Historical Scan for: [yellow]{target_group}[/yellow][/bold cyan]")
    console.print(f"[bold cyan]📤 Forward Destination: [green]{destination}[/green][/bold cyan]\n")

    client = WhatsAppClient(headless=True)
    filter_engine = MessageFilterEngine()
    storage = StorageManager()
    await storage.init_db()

    await client.start()
    logged_in = await client.wait_for_login(timeout_seconds=30)
    if not logged_in:
        console.print("[red][ERROR] WhatsApp Web session not authenticated.[/red]")
        await client.close()
        return

    console.print("[green][✓] Logged in successfully. Opening group...[/green]")

    opened = await client.search_and_open_chat(target_group)
    if not opened:
        # Try alternate spelling
        console.print(f"[yellow][!] Could not open '{target_group}', trying 'info Mechainal 2026'...[/yellow]")
        opened = await client.search_and_open_chat("info Mechainal 2026")

    if not opened:
        console.print(f"[red][ERROR] Could not locate group '{target_group}'. Please verify group name.[/red]")
        await client.close()
        return

    console.print(f"[cyan]➜ Group opened! Scrolling up to load last 2 days of messages...[/cyan]")

    # Scroll up 8 times to load historical messages
    page = client.page
    for i in range(8):
        try:
            # Scroll up inside the conversation panel
            await page.mouse.wheel(0, -3000)
            await asyncio.sleep(0.8)
        except Exception:
            pass

    await asyncio.sleep(2.0)

    # Extract all visible messages
    console.print("[cyan]➜ Extracting loaded messages...[/cyan]")
    messages = await client.extract_recent_messages(target_group, limit=100)
    console.print(f"[bold green][✓] Total messages extracted: {len(messages)}[/bold green]\n")

    important_found = []
    for msg in messages:
        raw_text = msg.get("text") or msg.get("content") or ""
        processed = filter_engine.process_message(
            chat_name=msg["chat_name"],
            sender=msg["sender"],
            timestamp=msg["timestamp"],
            text=raw_text
        )
        if processed:
            important_found.append(processed)

    console.print(f"[bold yellow]⚡ Important notices identified: {len(important_found)}[/bold yellow]\n")

    if not important_found:
        console.print("[dim]No notices or announcements found in the scanned window.[/dim]")
        await client.close()
        return

    # Forward to destination group
    console.print(f"[cyan]➜ Forwarding {len(important_found)} notices to '{destination}'...[/cyan]\n")

    for idx, item in enumerate(important_found, 1):
        console.print(f"[bold]Notice #{idx}:[/bold] [cyan]{item['category']}[/cyan] from [yellow]{item['sender']}[/yellow] ({item['timestamp']})")
        console.print(f"  [dim]Content preview:[/dim] {item['content'][:80]}...")

        # Generate formatted notice with Groq 120B AI Summary
        formatted_alert = filter_engine.generate_formatted_forward(item)

        console.print(f"  ➜ Sending to WhatsApp group: [bold green]{destination}[/bold green]...")
        sent = await client.send_whatsapp_message(destination, formatted_alert)
        if sent:
            console.print(f"  [green][✓] Sent successfully![/green]\n")
            # Save to storage DB
            await storage.save_message(item)
            await storage.mark_as_notified(item["hash"])
        else:
            console.print(f"  [yellow][!] Failed to send notice #{idx}.[/yellow]\n")

        # Open back the target group for next iteration if needed
        await asyncio.sleep(2.0)

    console.print("[bold green]🎉 All historical important notices scanned & forwarded successfully![/bold green]")
    await client.close()


if __name__ == "__main__":
    asyncio.run(scan_and_forward_history("info Mechanical 2026", "Ai summery"))
