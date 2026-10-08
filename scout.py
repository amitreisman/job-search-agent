"""Scout: scans company job boards for PM roles in Israel, stores them, alerts on Telegram.

Usage:  python scout.py [--dry-run]
Every decision is written to the `trace` table (feeds the public replay page later).
"""
import csv
import datetime as dt
import html
import json
import pathlib
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import assessor
import boards
import sources_extra
import tg

HERE = pathlib.Path(__file__).parent
import jprofile

P = jprofile.P
sources_extra.QUERY = P.get("search_query", "product manager")
DB_PATH = jprofile.DATA / "jobs.db"
MAX_AGE_DAYS = P["max_age_days"]
COLORS = ["🟦", "🟩", "🟨", "🟧", "🟥", "🟪", "🟫"]
SKIP_COMPANIES = {"Stripe", "Datadog", "Cloudflare", "Ramp", "Lemonade Israel"}  # little/no Israeli hiring

PM_RE = re.compile(P["title_include"], re.I)
EXCLUDE_RE = re.compile(P["title_exclude"], re.I)
SENIOR_RE = re.compile(P["seniority_flag"], re.I)
IL_RE = re.compile(P["location_regex"], re.I)


def fetch(company, ats, slug):
    return boards.fetch(company, ats, slug, lambda t: bool(PM_RE.search(t)) and not EXCLUDE_RE.search(t))


def load_env():
    env = {}
    for line in (HERE / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def telegram(env, text):
    data = urllib.parse.urlencode({"chat_id": env["TELEGRAM_CHAT_ID"], "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage", data=data, timeout=20)


def age_text(posted, now):
    m = int((now - posted).total_seconds() // 60)
    if m < 60:
        return f"לפני {max(m, 1)} דקות"
    if m < 60 * 24:
        return f"לפני {m // 60} שעות"
    return f"לפני {m // 1440} ימים"


def main(dry_run, force=False):
    DB_PATH.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, company TEXT, title TEXT, location TEXT, url TEXT,
        posted_at TEXT, first_seen TEXT, notified INTEGER DEFAULT 0, senior INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS trace (ts TEXT, run TEXT, company TEXT, event TEXT, detail TEXT);
    """)
    try:
        db.execute("ALTER TABLE jobs ADD COLUMN last_seen TEXT")  # when a scan last saw the job still open
    except sqlite3.OperationalError:
        pass
    now = dt.datetime.now(dt.timezone.utc)
    run = now.strftime("%Y%m%dT%H%M")
    stamp = now.isoformat()

    def log(company, event, detail=""):
        db.execute("INSERT INTO trace VALUES (?,?,?,?,?)", (now.isoformat(), run, company, event, detail))

    rows = [r for r in csv.DictReader(open(HERE / "probe_results.csv", encoding="utf-8-sig"))
            if int(r["total_jobs"]) > 0 and r["name"] not in SKIP_COMPANIES]
    rows += list(csv.DictReader(open(HERE / "companies_extra.csv", encoding="utf-8-sig")))

    def work(r):
        try:
            return r, fetch(r["name"], r["ats"], r["slug"]), None
        except Exception as e:  # one broken board must not stop the run
            return r, [], str(e)

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(work, rows))

    new = []
    for r, jobs, err in results:
        name = r["name"]
        if err:
            log(name, "fetch_error", err)
            db.execute("UPDATE jobs SET last_seen=? WHERE company=?", (stamp, name))  # a broken board must not erase its jobs from the report
            continue
        kept = 0
        for j in jobs:
            if not PM_RE.search(j["title"]) or EXCLUDE_RE.search(j["title"]):
                continue
            if not IL_RE.search(j["location"]):
                continue
            if (now - j["posted_at"]).days > MAX_AGE_DAYS:
                log(name, "skip_old", j["title"])
                continue
            key = f"{r['ats']}:{r['slug']}:{j['id']}"
            if db.execute("SELECT 1 FROM jobs WHERE key=?", (key,)).fetchone():
                db.execute("UPDATE jobs SET last_seen=? WHERE key=?", (stamp, key))
                continue
            senior = 1 if SENIOR_RE.search(j["title"]) else 0
            db.execute("INSERT INTO jobs (key,company,title,location,url,posted_at,first_seen,last_seen,senior) VALUES (?,?,?,?,?,?,?,?,?)",
                       (key, name, j["title"], j["location"].strip(), j["url"], j["posted_at"].isoformat(), stamp, stamp, senior))
            log(name, "new_job", f"{j['title']} | {j['location'].strip()} | senior={senior}")
            new.append((j["posted_at"], name, j, senior))
            kept += 1
        log(name, "scanned", f"{len(jobs)} jobs, {kept} new PM roles in Israel")
    if not dry_run:  # a dry run never commits: closing the connection discards everything it wrote
        db.commit()


    # --- Assess every unassessed job, then alert on the ones at/above threshold, youngest first ---
    ok = sum(1 for _, _, e in results if not e)
    print(f"Scanned {ok}/{len(results)} companies, {len(new)} new PM roles in Israel")
    assessor.ensure_tables(db)
    pending = db.execute("SELECT key, company, title, location FROM jobs WHERE key NOT IN (SELECT key FROM assessments) "
                         "ORDER BY posted_at DESC").fetchall()
    if P.get("max_assess"):  # demo profiles: assess only the newest N, to bound model cost
        pending = pending[:P["max_assess"]]
    for key, company, title, location in pending:
        try:
            r = assessor.assess(company, title, location, assessor.description(key))
        except Exception as e:  # an assessment failure must never drop a job silently
            log(company, "assess_error", f"{title}: {e}")
            continue
        db.execute("INSERT OR REPLACE INTO assessments VALUES (?,?,?,?,?,datetime('now'))",
                   (key, r["total"], r.get("hard_filter"), json.dumps(r, ensure_ascii=False), assessor.MODEL))
        log(company, "assessed", f"{title} -> {r['total']} {r['scores']} hard={r.get('hard_filter')}")
    if not dry_run:
        db.commit()
    if not P.get("notify", True):  # demo / secondary profiles: scan and assess only, never message anyone
        print(f"[{jprofile.NAME}] assessed {len(pending)} new jobs, no alert (notify=false)")
        db.close()
        return

    # A report always lists EVERY open matching job (seen open in this scan), newest first; new ones are marked.
    due = db.execute("""SELECT j.rowid, j.company, j.title, j.url, j.posted_at, a.total, a.result, j.first_seen
                        FROM jobs j LEFT JOIN assessments a ON a.key = j.key
                        WHERE j.last_seen = ? ORDER BY j.posted_at DESC""", (stamp,)).fetchall()
    passing = [d for d in due if d[5] is None or d[5] >= assessor.THRESHOLD]  # unassessed jobs are shown, never lost
    below = len(due) - len(passing)
    fresh = sum(1 for d in passing if d[7] == stamp)
    if not fresh and not force:  # nothing new since the last report: stay quiet instead of repeating the same list
        print(f"No new matching jobs ({len(passing)} open, {below} below threshold): no report sent")
        db.close()
        return
    header = f"<b>{len(passing)} משרות PM פתוחות בישראל מעל 50% התאמה</b> (מהחדשה לישנה)\n🆕 {fresh} חדשות מאז הדוח הקודם"
    if below:
        header += f"\nעוד {below} משרות נבדקו ונשארו מתחת לסף"
    items = []
    for jid, company, title, url, posted, total, result, first_seen in passing:
        age = age_text(dt.datetime.fromisoformat(posted), now)
        if total is None:
            score, why = "התאמה: לא נבדקה", ""
        else:
            score = f"התאמה {total}%"
            why = "\n" + html.escape(json.loads(result).get("one_line", ""))
        new_tag = "🆕 " if first_seen == stamp else ""
        text = f"{new_tag}<b>{html.escape(title)}</b>\n{html.escape(company)} | {age} | <b>{score}</b>{why}"
        buttons = [[{"text": "למשרה", "url": url}],
                   [{"text": "התאם קו\"ח", "callback_data": f"cv:{jid}"},
                    {"text": "COVER LETTER", "callback_data": f"cl:{jid}"}]]
        items.append((text, buttons))
    db.execute("CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, jobs INTEGER)")
    rid = db.execute("INSERT INTO reports (ts, jobs) VALUES (?,?)", (now.isoformat(), len(passing))).lastrowid
    local = now.astimezone().strftime("%d/%m %H:%M")
    bar = COLORS[rid % len(COLORS)] * 10  # colour rotates per report so consecutive reports never look alike
    top = f"{bar}\n<b>📋 דוח #{rid} | {local}</b>\n{header}"
    bottom = f"{bar}\n<b>סוף דוח #{rid}</b> | {len(passing)} משרות"
    if dry_run:
        db.rollback()
        print(top)
        for text, _ in items:
            print("\n" + text)
        print("\n" + bottom)
    else:
        db.commit()
        pin = tg.send_message(top)
        tg.pin_only(pin["result"]["message_id"])
        for text, buttons in items:  # one message per job: Telegram buttons belong to a whole message
            tg.send_message(text, buttons)
        tg.send_message(bottom)
        db.commit()
        print("Telegram alerts sent")
    db.close()


if __name__ == "__main__":
    main("--dry-run" in sys.argv, "--force" in sys.argv)









