"""Telegram smoke test. Reads TELEGRAM_BOT_TOKEN (and optionally TELEGRAM_CHAT_ID) from .env.

Step 1: run once after sending any message to your bot -> prints your chat id.
Step 2: put the chat id in .env, run again -> sends a sample job alert.
"""
import json
import pathlib
import urllib.parse
import urllib.request

ENV = {}
for line in (pathlib.Path(__file__).parent / ".env").read_text(encoding="utf-8-sig").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()

TOKEN = ENV["TELEGRAM_BOT_TOKEN"]
CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")
API = f"https://api.telegram.org/bot{TOKEN}"


def call(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data) as r:
        return json.load(r)


if not CHAT_ID:
    updates = call("getUpdates")["result"]
    if not updates:
        raise SystemExit("No messages yet. Send any message to your bot in Telegram, then run again.")
    print("Your chat id:", updates[-1]["message"]["chat"]["id"])
else:
    text = (
        "<b>משרה חדשה - דוגמה</b>\n"
        "Senior Product Manager, Payments\n"
        "Wix | לפני 40 דקות | התאמה 78%\n"
        "<a href=\"https://example.com/job\">למשרה</a>\n\n"
        "(הודעת בדיקה מסוכן חיפוש העבודה)"
    )
    print(call("sendMessage", chat_id=CHAT_ID, text=text, parse_mode="HTML", disable_web_page_preview="true"))
