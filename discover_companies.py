"""Find more companies whose job boards expose a public API and have roles in Israel.

Reads candidates.txt, tries several slug spellings on Greenhouse, Lever, Ashby, Workable, SmartRecruiters and Recruitee,
and writes discovered.csv (name, ats, slug, total_jobs, il_jobs, pm_il_jobs). No model calls, so it costs nothing.
"""
import csv
import json
import pathlib
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Accept": "application/json"}
IL = re.compile(r"israel|tel[ -]?aviv|herzliya|haifa|ramat|petah|ra'?anana|jerusalem|yokneam|netanya|rehovot|kfar|hod hasharon|rosh ha|beer|lod|modi|\bIL\b", re.I)
PM = re.compile(r"product (manager|owner|lead)|head of product|director of product|group product|\bpm\b", re.I)


def get(url, timeout=12):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def gh(s):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs")
    return None if not d or "jobs" not in d else [(j["title"], (j.get("location") or {}).get("name", "")) for j in d["jobs"]]


def lever(s):
    d = get(f"https://api.lever.co/v0/postings/{s}?mode=json")
    return None if not isinstance(d, list) else [(j["text"], str((j.get("categories") or {}).get("location") or "") + (" Israel" if j.get("country") == "IL" else "")) for j in d]


def ashby(s):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{s}")
    return None if not d or "jobs" not in d else [(j["title"], f"{j.get('location', '')} {((j.get('address') or {}).get('postalAddress') or {}).get('addressCountry', '')}") for j in d["jobs"]]


def workable(s):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{s}")
    return None if not d or not d.get("jobs") else [(j["title"], f"{j.get('city', '')} {j.get('country', '')}") for j in d["jobs"]]


def smartrecruiters(s):
    d = get(f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=100")
    if not d or not d.get("totalFound"):
        return None
    return [(j["name"], f"{(j.get('location') or {}).get('city', '')} {(j.get('location') or {}).get('country', '')}") for j in d["content"]]


def recruitee(s):
    d = get(f"https://{s}.recruitee.com/api/offers/")
    return None if not d or not d.get("offers") else [(j["title"], f"{j.get('city', '')} {j.get('country', '')} {j.get('location', '')}") for j in d["offers"]]


ATS = [("greenhouse", gh), ("lever", lever), ("ashby", ashby), ("workable", workable), ("smartrecruiters", smartrecruiters), ("recruitee", recruitee)]


def variants(name):
    base = re.sub(r"[^a-z0-9 ]", "", name.lower().replace("-", " ").replace(".", "")).split()
    out = ["".join(base), "-".join(base)]
    if len(base) > 1:
        out.append(base[0])
    return list(dict.fromkeys(v for v in out if v))


def probe(name):
    for slug in variants(name):
        for ats, fn in ATS:
            jobs = fn(slug)
            if jobs:
                il = [j for j in jobs if IL.search(j[1])]
                if il:  # only companies that actually hire in Israel
                    return [name, ats, slug, len(jobs), len(il), sum(1 for j in il if PM.search(j[0]))]
    return None


if __name__ == "__main__":
    names = list(dict.fromkeys(l.strip() for l in (HERE / "candidates.txt").read_text(encoding="utf-8").splitlines() if l.strip()))
    with ThreadPoolExecutor(10) as ex:
        res = [r for r in ex.map(probe, names) if r]
    with open(HERE / "discovered.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["name", "ats", "slug", "total_jobs", "il_jobs", "pm_il_jobs"])
        w.writerows(res)
    print(f"{len(res)} of {len(names)} candidates expose a public board with jobs in Israel")
    for r in sorted(res, key=lambda r: -r[5]):
        print(f"  {r[0]:22} {r[1]:16} {r[2]:22} total={r[3]:4} IL={r[4]:3} PM-IL={r[5]}")
