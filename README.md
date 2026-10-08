# Job Search Agent

An agent-based system that watches company job boards, scores every role against a CV with an explainable breakdown, and prepares a tailored one-page CV and cover letter on request. It never applies or messages anyone by itself.

**Public demo:** a recorded walkthrough of the full flow plus three fictional sample candidates (real pipeline output, no backend, no cost). The live version, where you upload your own CV, runs the same code locally; it is not open to the public because every visit calls the model and CVs are personal data.

## How it works

```
Job boards (9 hiring systems, public APIs) -> Scout (filter, dedupe, track open roles)
  -> Assessor (LLM, 5-part weighted score, hard filters) -> Report (Telegram / web)
  -> human gate: tap "Tailor CV" or "Cover letter" -> Tailor (one-page PDF + letter)
```

- **Scout** (`scout.py`, `boards.py`, `sources_extra.py`): Greenhouse, Lever, Ashby, Workable, Comeet, Workday, Eightfold, Amazon and Radancy adapters. Rules filter by title, location and age first; the model only sees survivors.
- **Assessor** (`assessor.py`): role/seniority, domain, skills, experience and location, each with strengths and gaps that must cite the CV. Director-level roles are a hard filter.
- **Tailor** (`tailor.py`): builds the CV from verified facts only. Names, titles, dates and education are fixed in code, so the model writes bullets and nothing else. Output is a one-page PDF.
- **Telegram bot** (`bot.py`) and **scheduled scans** (`register_tasks.ps1`, Windows) for personal use.
- **Web demo** (`webapp.py`, `webcore.py`): FastAPI. A visitor uploads a CV, gets matches from the same boards, and can generate a tailored CV and letter.

## Design decisions

- **Human in the loop.** The agent drafts; the person decides. Applying and recruiter outreach stay manual.
- **Grounded generation.** A facts file with a "do not claim" list. Unverified inferences must not be stated as fact (a real catch: "probably Dynamics 365" once became a stated fact).
- **Failures never hide a job.** A broken board does not stop a run; a failed score shows as "not assessed".
- **Cost control.** Rules first, model second; no new jobs means no report and no model calls.
- **Privacy in the web demo.** A CV lives only in memory for one session (60 min by default), is never written to disk or logged, and can be erased on demand. Per-IP rate limit and a daily model-call ceiling.
- **Deliberately not built:** LinkedIn scraping and automated messaging (platform terms, and it damages the relationship it is meant to start).

## Run it

```bash
pip install -r requirements-web.txt
# local, no API key: uses the Claude Code login through the Claude Agent SDK
python -m uvicorn webapp:app --port 8765
# hosted: set ANTHROPIC_API_KEY (optional: DAILY_CALL_CAP, SESSIONS_PER_IP_HOUR, ALLOW_ORIGIN)
```

Everything person-specific lives in `profiles/<name>.json` (target roles, location, rubric, CV layout). Select it with `JOB_AGENT_PROFILE`. Three fictional personas are included.

## Limits

Scores come from model judgement against a written rubric and are not yet calibrated against human labels. Coverage is companies whose boards expose a public API. Some boards only expose a last-updated time, so a refreshed old job can look newer than it is.

Built with the Claude Agent SDK, Python, FastAPI, SQLite and PyMuPDF.
