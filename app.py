"""
Hugging Face Spaces Web Entry Point & Dashboard.
Runs FastAPI web server on port 7860 to provide live status & message logs,
while executing the WhatsApp monitoring loop in a background thread/task.
"""

import asyncio
import os
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse

from config import DEFAULT_TARGET_CHATS, POLL_INTERVAL_SECONDS, FORWARD_CONTACT
from storage import StorageManager
from main import run_monitoring_loop

app = FastAPI(title="WhatsApp Important Message Agent")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Agent Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
        .container { max-width: 1000px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
        h1 { font-size: 1.8rem; color: #38bdf8; display: flex; align-items: center; gap: 0.5rem; }
        .badge { background: #10b981; color: white; padding: 0.3rem 0.8rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; }
        .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }
        h2 { font-size: 1.2rem; margin-bottom: 1rem; color: #94a3b8; }
        .groups-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .group-tag { background: #334155; padding: 0.4rem 0.8rem; border-radius: 8px; font-size: 0.9rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { text-align: left; padding: 0.75rem 1rem; border-bottom: 1px solid #334155; }
        th { background: #0f172a; color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; }
        tr:hover { background: #243248; }
        .cat-badge { padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
        .cat-announcement { background: #dc2626; color: white; }
        .cat-timetable { background: #2563eb; color: white; }
        .cat-event { background: #7c3aed; color: white; }
        .cat-study { background: #059669; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>💬 WhatsApp Agent Cloud Monitor</h1>
            <span class="badge">● 24/7 ACTIVE</span>
        </header>

        <div class="card">
            <h2>Active Monitored Groups</h2>
            <div class="groups-list">
                {groups_html}
            </div>
            <div style="margin-top: 1rem; font-size: 0.9rem; color: #94a3b8;">
                Forwarding Important Notices to: <strong style="color: #38bdf8;">{forward_contact}</strong>
            </div>
        </div>

        <div class="card">
            <h2>Recent Extracted Notices & Summaries</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Group</th>
                        <th>Sender</th>
                        <th>Time</th>
                        <th>Message Preview</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    storage = StorageManager()
    recent = await storage.get_recent_messages(limit=25)

    groups_html = "".join(f"<span class='group-tag'>📌 {g}</span>" for g in DEFAULT_TARGET_CHATS)

    rows = []
    for m in recent:
        cat = m.get("category", "NOTICE")
        cat_class = "cat-announcement" if cat == "ANNOUNCEMENT" else (
            "cat-timetable" if cat == "TIMETABLE" else (
                "cat-study" if cat == "STUDY_MATERIAL" else "cat-event"
            )
        )
        preview = (m.get("content", "")[:90] + "...").replace("\n", " ")
        rows.append(f"""
            <tr>
                <td><span class="cat-badge {cat_class}">{cat}</span></td>
                <td><strong>{m.get('chat_name')}</strong></td>
                <td>{m.get('sender')}</td>
                <td style="color: #94a3b8;">{m.get('timestamp_raw')}</td>
                <td>{preview}</td>
            </tr>
        """)

    rows_html = "".join(rows) if rows else "<tr><td colspan='5' style='text-align:center;color:#94a3b8;'>Monitoring active. Waiting for new messages...</td></tr>"

    return HTML_TEMPLATE.format(
        groups_html=groups_html,
        forward_contact=FORWARD_CONTACT or "Akshuuu",
        rows_html=rows_html
    )

@app.on_event("startup")
async def startup_event():
    """Start WhatsApp monitoring in background task."""
    print("[INFO] Starting background WhatsApp monitoring task...")
    asyncio.create_task(run_monitoring_loop(
        target_chats=DEFAULT_TARGET_CHATS,
        poll_interval=POLL_INTERVAL_SECONDS,
        headless=True,
        forward_contact=FORWARD_CONTACT or "Akshuuu"
    ))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
