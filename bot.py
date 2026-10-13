"""Bot: listens for button presses in Telegram and acts on them.

Buttons on every job card:
  🔗 למשרה   (op)  sends the link and stops showing the job in later reports
  ✖ הסר      (hx)  dismisses the job: it never appears again
  התאם קו"ח  (cv)  builds the tailored CV, and stops showing the job
  COVER LETTER (cl) writes the cover letter, and stops showing the job

Run it and leave it running:  python bot.py
Only the owner's chat is served; everything else is ignored. Nothing is ever sent to a third party:
files and text come back to the same chat, and applying stays manual.
"""
import html
import sqlite3
import sys
import threading
import time
import traceback

import assessor
import tg

HIDE_ACTIONS = {"op": "opened", "hx": "dismissed", "cv": "cv", "cl": "letter"}
QUICK = {"op": "הקישור נשלח", "hx": "הוסרה מהרשימה"}


def trace(event, detail):
    db = sqlite3.connect(assessor.DB_PATH)
    db.execute("INSERT INTO trace VALUES (datetime('now'),'bot','',?,?)", (event, detail))
    db.commit()
    db.close()


def job_row(job_id):
    db = sqlite3.connect(assessor.DB_PATH)
    row = db.execute("SELECT company, title, url FROM jobs WHERE rowid=?", (job_id,)).fetchone()
    db.close()
    return row


def mark_hidden(job_id, reason):
    """The job is acted on or dismissed: keep it out of every later report (the key stays, so a re-scan cannot bring it back)."""
    db = sqlite3.connect(assessor.DB_PATH)
    for col in ("hidden INTEGER DEFAULT 0", "hidden_reason TEXT", "hidden_at TEXT"):
        try:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    db.execute("UPDATE jobs SET hidden=1, hidden_reason=?, hidden_at=datetime('now') WHERE rowid=?", (reason, job_id))
    db.commit()
    db.close()


def handle(cb):
    action, job_id = cb["data"].split(":")
    job_id = int(job_id)
    msg_id = cb["message"]["message_id"]
    try:
        if action in ("op", "hx"):
            mark_hidden(job_id, HIDE_ACTIONS[action])  # instant actions are hidden right away
        row = job_row(job_id)
        if action == "op":
            company, title, url = row
            tg.send_message(f'🔗 <a href="{html.escape(url)}">{html.escape(title)}</a> | {html.escape(company)}',
                            [[{"text": "פתח את המשרה", "url": url}]], reply_to=msg_id)
            trace("opened", f"job {job_id}: {company} / {title}")
        elif action == "hx":
            company, title, _ = row
            try:  # turn the card into a one-line note; omitting reply_markup also removes its buttons
                tg.api("editMessageText", chat_id=tg.CHAT_ID, message_id=msg_id, parse_mode="HTML",
                       text=f"✖ <s>{html.escape(title)}</s> | {html.escape(company)}\nהוסרה מהרשימה ולא תופיע שוב")
            except Exception:
                pass  # the note is cosmetic; the job is already hidden
            trace("dismissed", f"job {job_id}: {company} / {title}")
        elif action in ("cv", "cl"):
            import tailor  # imported lazily so the listener starts fast
            if action == "cv":
                tg.api("sendChatAction", chat_id=tg.CHAT_ID, action="upload_document")
                path, notes = tailor.make_cv(job_id)
                tg.send_document(path, caption=f"קורות חיים מותאמים: {notes}", reply_to=msg_id)
                mark_hidden(job_id, "cv")  # only after a CV really exists
                trace("cv_sent", f"job {job_id}: {notes}")
            else:
                tg.api("sendChatAction", chat_id=tg.CHAT_ID, action="typing")
                letter = tailor.make_letter(job_id)
                tg.send_message(letter, html=False, reply_to=msg_id)
                mark_hidden(job_id, "letter")
                trace("letter_sent", f"job {job_id}")
    except Exception as e:
        traceback.print_exc()
        if "Credit balance is too low" in str(e):
            msg = ("⚠️ לא הצלחתי להכין: אין כרגע גישה למודל מהמחשב (\"Credit balance is too low\").\n"
                   "המשרה לא הוסתרה, אפשר לנסות שוב אחרי שהחיבור יתוקן.")
        else:
            msg = f"לא הצלחתי להכין ({action}): {e}"
        tg.send_message(msg, html=False, reply_to=msg_id)
        trace("error", f"{action} job {job_id}: {e}")


def main():
    offset = None
    print("Bot listening. Ctrl+C to stop.")
    while True:
        try:
            params = dict(timeout=50, allowed_updates=["callback_query"])
            if offset:
                params["offset"] = offset
            for u in tg.api("getUpdates", http_timeout=70, **params)["result"]:
                offset = u["update_id"] + 1
                cb = u.get("callback_query")
                if not cb or cb["from"]["id"] != tg.CHAT_ID:  # ignore anyone but the owner
                    continue
                action = cb.get("data", ":").split(":")[0]
                try:  # a press older than ~1 minute can no longer be acknowledged; still serve it
                    tg.api("answerCallbackQuery", callback_query_id=cb["id"], text=QUICK.get(action, "מכין... זה לוקח כחצי דקה"))
                except Exception:
                    pass
                threading.Thread(target=handle, args=(cb,), daemon=True).start()
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
