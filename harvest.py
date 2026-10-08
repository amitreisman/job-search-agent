"""Harvest: open each company's careers page in a real browser and find the hiring system behind it, with its credentials.

For every domain in domains.csv it tries a few careers URLs, records the network requests/iframes/HTML, extracts Comeet
(company uid + token), Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee and HiBob identifiers, then VERIFIES each
candidate by fetching its jobs with the real adapters. Only boards that really return jobs in Israel are kept.
No model calls, so it costs nothing.   Usage: python harvest.py <part> <parts>   (run several parts in parallel)
"""
import csv
import datetime as dt
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

import boards
import sources_extra  # noqa: F401  (registers adapters used by boards.fetch)

HERE = pathlib.Path(__file__).parent
IL = re.compile(r"israel|tel[ -]?aviv|herzliya|haifa|ramat|petah|ra'?anana|jerusalem|yokneam|netanya|rehovot|kfar|hod hasharon|rosh ha|beer|lod|modi|\bIL\b", re.I)
PM = re.compile(r"product (manager|owner|lead)|head of product|director of product|group product|\bpm\b", re.I)
PATHS = ["/careers", "/careers/", "/company/careers", "/about/careers", "/jobs", "/company/jobs", "/about-us/careers", "/en/careers"]

PATTERNS = [  # (ats, regex, builder(match) -> slug)
    ("comeet", re.compile(r"comeet\.co/careers-api/2\.0/company/([\w.]+)/positions\?token=([0-9A-Fa-f]{16,})"), lambda m: f"{m.group(1)}|{m.group(2)}"),
    ("comeet", re.compile(r"comeet\.(?:co|com)/jobs/[^\"'\s]*?token=([0-9A-Fa-f]{16,})[^\"'\s]*?company-uid=([\w.]+)"), lambda m: f"{m.group(2)}|{m.group(1)}"),
    ("comeet", re.compile(r"company-uid=([\w.]+)[^\"'\s]*?token=([0-9A-Fa-f]{16,})"), lambda m: f"{m.group(1)}|{m.group(2)}"),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([\w-]+)"), lambda m: m.group(1)),
    ("greenhouse", re.compile(r"greenhouse\.io/embed/job_board[^\"'\s]*?for=([\w-]+)"), lambda m: m.group(1)),
    ("greenhouse", re.compile(r"(?:job-boards|boards)\.(?:eu\.)?greenhouse\.io/([\w-]+)(?:/|\?|\"|')"), lambda m: m.group(1)),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([\w-]+)"), lambda m: m.group(1)),
    ("lever", re.compile(r"jobs\.lever\.co/([\w-]+)"), lambda m: m.group(1)),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([\w-]+)"), lambda m: m.group(1)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([\w-]+)"), lambda m: m.group(1)),
    ("workable", re.compile(r"apply\.workable\.com/(?:api/v\d/(?:widget/)?accounts/)?([\w-]+)"), lambda m: m.group(1)),
    ("smartrecruiters", re.compile(r"(?:api|jobs)\.smartrecruiters\.com/(?:v1/companies/)?([\w-]+)"), lambda m: m.group(1)),
    ("hibob", re.compile(r"([\w-]+)\.careers\.hibob\.com"), lambda m: m.group(1)),
]
BAD_SLUGS = {"embed", "api", "v1", "v0", "widget", "accounts", "jobs", "boards", "j", "undefined", "careers"}


def detect(blob):
    found = {}
    for ats, rx, build in PATTERNS:
        for m in rx.finditer(blob):
            slug = build(m)
            if slug.split("|")[0].lower() in BAD_SLUGS:
                continue
            found[(ats, slug)] = True
    return list(found)


def verify(name, ats, slug):
    """Return (total_jobs, il_jobs, pm_il_jobs) if the board really lists jobs in Israel, else None."""
    try:
        jobs = boards.fetch(name, ats, slug, lambda t: bool(PM.search(t)))
    except Exception:
        return None
    il = [j for j in jobs if IL.search(j["location"])]
    if not il:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    return len(jobs), len(il), sum(1 for j in il if PM.search(j["title"]) and (now - j["posted_at"]).days <= 90)


def visit(ctx, domain):
    blobs = []
    for host in (f"https://www.{domain}", f"https://{domain}", f"https://careers.{domain}", f"https://jobs.{domain}"):
        for path in (PATHS if host.count(".") and host.split("//")[1].startswith(("www.", domain)) else [""]):
            page = ctx.new_page()
            seen = []
            page.on("request", lambda r: seen.append(r.url))
            try:
                resp = page.goto(host + path, wait_until="domcontentloaded", timeout=25000)
                if not resp or resp.status >= 400:
                    page.close(); continue
                page.wait_for_timeout(5500)
                html = page.content()
                frames = " ".join(f.url for f in page.frames)
                blob = " ".join(seen) + " " + frames + " " + html
                links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                blob += " " + " ".join(links)
                page.close()
                found = detect(blob)
                if found:
                    return found
                blobs.append(blob)
            except Exception:
                try: page.close()
                except Exception: pass
            if len(blobs) >= 3:
                return []
    return []


if __name__ == "__main__":
    part, parts = int(sys.argv[1]), int(sys.argv[2])
    rows = list(csv.DictReader(open(HERE / "domains.csv", encoding="utf-8-sig")))
    known = {(r["ats"], r["slug"]) for r in boards.board_rows()}
    mine = [r for i, r in enumerate(rows) if i % parts == part]
    out = HERE / "data" / f"harvest_{part}.csv"
    out.parent.mkdir(exist_ok=True)
    with sync_playwright() as p, open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["name", "ats", "slug", "total", "il", "pm_il", "status"])
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36", locale="en-US")
        for r in mine:
            try:
                cands = visit(ctx, r["domain"])
            except Exception as e:
                print(f"[{part}] {r['name']}: error {str(e)[:50]}", flush=True); continue
            ok = False
            for ats, slug in cands:
                if (ats, slug) in known:
                    print(f"[{part}] {r['name']:20} already scanned ({ats})", flush=True); ok = True; break
                v = verify(r["name"], ats, slug)
                if v:
                    w.writerow([r["name"], ats, slug, *v, "new"]); f.flush(); ok = True
                    print(f"[{part}] {r['name']:20} NEW {ats:14} jobs={v[0]:4} IL={v[1]:3} PM-IL={v[2]}", flush=True); break
            if not ok:
                print(f"[{part}] {r['name']:20} -", ("candidates failed verification: " + str([c[0] for c in cands])) if cands else "no hiring system found", flush=True)
        b.close()
    print(f"[{part}] done", flush=True)
