"""Bot: listens for button presses in Telegram and generates the tailored CV / cover letter on demand.

Run it and leave it running:  python bot.py
Only the owner's chat is served; everything else is ignored. Nothing is ever sent to a third party:
files and text come back to the same chat, and applying stays manual.
"""
import sqlite3
import sys
import threading
import time
import traceback

import assessor
import tg


def trace(event, detail):
    db = sqlite3.connect(assessor.DB_PATH)
    db.execute("INSERT INTO trace VALUES (datetime('now'),'bot','',?,?)", (event, detail))
    db.commit()
    db.close()


def handle(cb):
    action, job_id = cb["data"].split(":")
    job_id = int(job_id)
    try:
        import tailor  # imported lazily so the listener starts fast
        if action == "cv":
            tg.api("sendChatAction", chat_id=tg.CHAT_ID, action="upload_document")
            path, notes = tailor.make_cv(job_id)
            tg.send_document(path, caption=f"קורות חיים מותאמים: {notes}", reply_to=cb["message"]["message_id"])
            trace("cv_sent", f"job {job_id}: {notes}")
        elif action == "cl":
            tg.api("sendChatAction", chat_id=tg.CHAT_ID, action="typing")
            letter = tailor.make_letter(job_id)
            tg.send_message(letter, html=False, reply_to=cb["message"]["message_id"])
            trace("letter_sent", f"job {job_id}")
    except Exception as e:
        traceback.print_exc()
        tg.send_message(f"לא הצלחתי להכין ({action}): {e}", html=False)
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
                try:  # a press older than ~1 minute can no longer be acknowledged; still serve it
                    tg.api("answerCallbackQuery", callback_query_id=cb["id"], text="מכין... זה לוקח כחצי דקה")
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


