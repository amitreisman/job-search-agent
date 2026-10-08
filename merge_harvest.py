"""Merge verified boards found by harvest.py into companies_extra.csv (the list the Scout scans). No duplicates."""
import csv
import glob
import pathlib

HERE = pathlib.Path(__file__).parent
extra = HERE / "companies_extra.csv"
rows = list(csv.DictReader(open(extra, encoding="utf-8-sig")))
known = {(r["ats"], r["slug"]) for r in rows}
import boards  # noqa: E402
known |= {(r["ats"], r["slug"]) for r in boards.board_rows()}
added = []
for f in sorted(glob.glob(str(HERE / "data" / "harvest_*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        if r["status"] != "new" or (r["ats"], r["slug"]) in known:
            continue
        known.add((r["ats"], r["slug"]))
        added.append(r)
with open(extra, "a", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    for r in added:
        w.writerow([r["name"], r["ats"], r["slug"]])
pm = sum(int(r["pm_il"]) for r in added)
print(f"added {len(added)} companies | PM roles in Israel at them: {pm}")
for r in sorted(added, key=lambda r: -int(r["pm_il"])):
    print(f"  {r['name']:20} {r['ats']:16} jobs={r['total']:>4} IL={r['il']:>3} PM-IL={r['pm_il']}")
print("companies scanned per run now:", len(boards.board_rows()))
