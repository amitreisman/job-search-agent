"""Generate the showcase artefacts for a demo persona: tailored CV (PNG preview) + cover letter for its best match.

Run with JOB_AGENT_PROFILE=<demo persona>:   python make_showcase.py
Writes data/showcase/<persona>.json. Uses the real Tailor, so what the site shows is real pipeline output.
"""
import base64
import json
import sqlite3

import fitz

import assessor
import jprofile
import tailor


def main():
    db = sqlite3.connect(assessor.DB_PATH)
    row = db.execute("""SELECT j.rowid, j.company, j.title, j.location, j.url FROM jobs j JOIN assessments a ON a.key = j.key
                        WHERE a.hard_filter IS NULL ORDER BY a.total DESC LIMIT 1""").fetchone()
    db.close()
    jid, company, title, location, url = row
    pdf, notes = tailor.make_cv(jid)
    letter = tailor.make_letter(jid)
    png = fitz.open(pdf)[0].get_pixmap(dpi=100).tobytes("png")
    out = jprofile.DATA.parent / "showcase"
    out.mkdir(exist_ok=True)
    (out / f"{jprofile.NAME}.json").write_text(json.dumps(dict(
        job=dict(company=company, title=title, location=location.strip(), url=url), letter=letter, notes=notes,
        cv_png="data:image/png;base64," + base64.b64encode(png).decode()), ensure_ascii=False), encoding="utf-8")
    print(jprofile.NAME, "->", company, "|", title, "| png KB:", len(png) // 1024)


if __name__ == "__main__":
    main()
