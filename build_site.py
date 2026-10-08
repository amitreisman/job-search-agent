"""Build the public showcase page (docs/index.html) from real data.

PRIVACY: the public page is built ONLY from (a) aggregate counts of the real scan and (b) fictional demo personas run through
the real pipeline. Nothing of the owner's CV, applications, contact details, recruiters or tokens is read or exported.
Output is ONE self-contained HTML file (data inlined), so it can be hosted anywhere.
"""
import csv
import datetime as dt
import json
import os
import pathlib
import sqlite3

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
OUT = HERE / "docs"
PERSONAS = ("demo_backend", "demo_data", "demo_design")


def jobs_with_scores(db_path):
    db = sqlite3.connect(db_path)
    out = []
    for company, title, location, url, posted, result in db.execute(
            """SELECT j.company, j.title, j.location, j.url, j.posted_at, a.result
               FROM jobs j JOIN assessments a ON a.key = j.key ORDER BY json_extract(a.result,'$.total') DESC"""):
        r = json.loads(result)
        out.append(dict(company=company, title=title.strip(), location=" ".join(location.split()), url=url, posted=posted[:10],
                        total=r["total"], scores=r["scores"], hard=r.get("hard_filter"),
                        strengths=r.get("strengths", []), gaps=r.get("gaps", []), one_line=r.get("one_line", "")))
    db.close()
    return out


def count_companies():
    skip = {"Stripe", "Datadog", "Cloudflare", "Ramp", "Lemonade Israel"}
    n = sum(1 for r in csv.DictReader(open(HERE / "probe_results.csv", encoding="utf-8-sig"))
            if int(r["total_jobs"]) > 0 and r["name"] not in skip)
    return n + sum(1 for _ in csv.DictReader(open(HERE / "companies_extra.csv", encoding="utf-8-sig")))


def persona(name):
    prof = json.loads((HERE / "profiles" / f"{name}.json").read_text(encoding="utf-8-sig"))
    show = json.loads((DATA / "showcase" / f"{name}.json").read_text(encoding="utf-8"))
    return dict(id=name, display=prof["display"].replace(" (sample persona)", ""), role=prof["target_role"].replace("a ", "", 1),
                query=prof["search_query"], resume=(HERE / prof["resume_path"]).read_text(encoding="utf-8-sig"),
                jobs=jobs_with_scores(DATA / name / "jobs.db"), show=show,
                profile=json.dumps({k: prof[k] for k in ("search_query", "title_include", "target_role", "domain_focus",
                                                          "home", "threshold", "weights")}, indent=2))


def main():
    real = jobs_with_scores(DATA / "jobs.db")  # aggregate numbers only; no job or CV content is exported
    db = sqlite3.connect(DATA / "jobs.db")
    stats = dict(companies=count_companies(), hiring_systems=9, scans_per_day=4,
                 jobs_seen=db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
                 passing=sum(1 for j in real if j["total"] >= 50 and not j["hard"]), generated=dt.date.today().isoformat())
    db.close()
    payload = dict(stats=stats, personas=[persona(n) for n in PERSONAS])
    OUT.mkdir(exist_ok=True)
    tpl = (HERE / "site_template.html").read_text(encoding="utf-8")
    api = os.environ.get("JOBAGENT_API", "")  # base URL of the live API when the page is hosted elsewhere; empty = same origin
    html = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False)).replace("/*__API__*/", api)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    size = (OUT / "index.html").stat().st_size // 1024
    print("docs/index.html written:", size, "KB |", stats, "| persona jobs:", {p["id"]: len(p["jobs"]) for p in payload["personas"]})


if __name__ == "__main__":
    main()

