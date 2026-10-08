"""Fetch job lists from company job boards (public APIs). No Telegram, no candidate profile: safe to import anywhere."""
import csv
import datetime as dt
import json
import pathlib
import urllib.request

import sources_extra

HERE = pathlib.Path(__file__).parent
SKIP_COMPANIES = {"Stripe", "Datadog", "Cloudflare", "Ramp", "Lemonade Israel"}  # little/no Israeli hiring


def board_rows():
    """Companies to scan: [{name, ats, slug}]."""
    rows = [r for r in csv.DictReader(open(HERE / "probe_results.csv", encoding="utf-8-sig"))
            if int(r["total_jobs"]) > 0 and r["name"] not in SKIP_COMPANIES]
    return rows + list(csv.DictReader(open(HERE / "companies_extra.csv", encoding="utf-8-sig")))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "job-agent/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def fetch(company, ats, slug, is_pm=lambda t: True):
    """Return list of dicts: id, title, location, url, posted_at (UTC)."""
    out = []
    if ats == "greenhouse":
        for j in get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")["jobs"]:
            out.append(dict(id=str(j["id"]), title=j["title"], location=(j.get("location") or {}).get("name", ""),
                            url=j["absolute_url"], posted_at=iso(j.get("first_published") or j["updated_at"])))
    elif ats == "lever":
        for j in get(f"https://api.lever.co/v0/postings/{slug}?mode=json"):
            loc = (j.get("categories") or {}).get("location") or ""
            if j.get("country") == "IL":
                loc += " Israel"
            out.append(dict(id=j["id"], title=j["text"], location=loc, url=j["hostedUrl"],
                            posted_at=dt.datetime.fromtimestamp(j["createdAt"] / 1000, dt.timezone.utc)))
    elif ats == "ashby":
        for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")["jobs"]:
            country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry", "")
            out.append(dict(id=j["id"], title=j["title"].strip(), location=f"{j.get('location','')} {country}",
                            url=j["jobUrl"], posted_at=iso(j["publishedAt"])))
    elif ats == "workable":
        for j in get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")["jobs"]:
            out.append(dict(id=j["shortcode"], title=j["title"], location=f"{j.get('city','')} {j.get('country','')}",
                            url=j["url"], posted_at=dt.datetime.fromisoformat(j["published_on"]).replace(tzinfo=dt.timezone.utc)))
    elif ats in ("comeet", "workday", "amazon", "pcsx", "radancy", "smartrecruiters", "hibob", "teamme"):
        out = sources_extra.fetch(ats, slug, is_pm)
    return out



