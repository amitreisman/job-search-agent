"""Probe which public job-board APIs each company in companies.csv exposes.

Writes probe_results.csv: name, ats, slug, total_jobs, pm_jobs, il_pm_jobs.
Public read-only endpoints only (Greenhouse, Lever, Ashby, Workable).
"""
import csv
import json
import pathlib
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "job-agent-probe/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def greenhouse(slug):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if not d or "jobs" not in d:
        return None
    return [(j["title"], (j.get("location") or {}).get("name", "")) for j in d["jobs"]]


def lever(slug):
    d = get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(d, list):
        return None
    return [(j["text"], (j.get("categories") or {}).get("location") or "") for j in d]


def ashby(slug):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not d or "jobs" not in d:
        return None
    return [(j["title"], j.get("location", "")) for j in d["jobs"]]


def workable(slug):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    if not d or "jobs" not in d:
        return None
    return [(j["title"], j.get("city", "") + " " + j.get("country", "")) for j in d["jobs"]]


ATS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable}


def is_pm(title):
    t = title.lower()
    return "product manager" in t or "product owner" in t or "head of product" in t


def probe(row):
    for slug in row["slugs"].split(";"):
        for ats, fn in ATS.items():
            jobs = fn(slug)
            if jobs is not None:
                pm = [j for j in jobs if is_pm(j[0])]
                il = [j for j in pm if any(k in j[1].lower() for k in ("israel", "tel aviv", "herzliya", "haifa", "ramat", "petah", "raanana", "jerusalem", "yokneam", "netanya", "rehovot"))]
                return [row["name"], ats, slug, len(jobs), len(pm), len(il)]
    return [row["name"], "", "", 0, 0, 0]


if __name__ == "__main__":
    rows = list(csv.DictReader(open(HERE / "companies.csv", encoding="utf-8")))
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(probe, rows))
    with open(HERE / "probe_results.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["name", "ats", "slug", "total_jobs", "pm_jobs", "il_pm_jobs"])
        w.writerows(results)
    hit = [r for r in results if r[1]]
    print(f"{len(hit)}/{len(results)} companies expose a public API")
    for r in hit:
        print(r)
    print("NO API:", ", ".join(r[0] for r in results if not r[1]))
