"""Re-assess every visible tracked job with the current (strict) rubric and store the new scores.

Each stored result keeps `previous_total` so the change is auditable. Jobs without enough posting text are left alone.
Run:  python rescore_all.py            (all visible jobs)
"""
import json
import sqlite3
import sys

import assessor

MIN_DESC = 300
d = sqlite3.connect(assessor.DB_PATH)
rows = d.execute("""SELECT j.key, j.company, j.title, j.location, a.total, j.rowid FROM jobs j JOIN assessments a ON a.key = j.key
                    WHERE (COALESCE(j.hidden, 0) = 0 OR ?) AND (j.last_seen IS NOT NULL) AND a.model NOT LIKE '%core-domain v2%' ORDER BY j.rowid""", (1 if "--all" in sys.argv else 0,)).fetchall()
print(f"re-assessing {len(rows)} jobs", flush=True)
changed = []
for key, company, title, loc, old, rid in rows:
    desc = assessor.description(key)
    if len(desc) < MIN_DESC:
        print(f"  #{rid:3} {company:14} skipped (posting text {len(desc)} chars)", flush=True)
        continue
    try:
        r = assessor.assess(company, title, loc, desc)
    except Exception as e:
        print(f"  #{rid:3} {company:14} ERROR {str(e)[:70]}", flush=True)
        continue
    r["previous_total"] = old
    d.execute("INSERT OR REPLACE INTO assessments VALUES (?,?,?,?,?,datetime('now'))",
              (key, r["total"], r.get("hard_filter"), json.dumps(r, ensure_ascii=False), "sonnet (core-domain v2)"))
    d.execute("INSERT INTO trace VALUES (datetime('now'),'assess',?,?,?)", (company, "reassessed", f"{title} -> {r['total']} (was {old}, strict rubric)"))
    d.commit()
    crit = len(r.get("critical_gaps") or [])
    flag = "" if (old >= 50) == (r["total"] >= 50) else "   <-- crosses the 50 line"
    print(f"  #{rid:3} {company:14} {title[:40]:40} {old:3d} -> {r['total']:3d}  critical gaps: {crit}{flag}", flush=True)
    changed.append((company, title, old, r["total"]))
up = sum(1 for *_, o, n in changed if n > o)
down = sum(1 for *_, o, n in changed if n < o)
print(f"\ndone: {len(changed)} re-assessed | lower: {down} | higher: {up} | "
      f"passing >=50 before: {sum(1 for *_, o, n in changed if o >= 50)} -> now: {sum(1 for *_, o, n in changed if n >= 50)}", flush=True)


