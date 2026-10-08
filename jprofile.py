"""Candidate profile: everything that used to be hard-coded for one person (target roles, location, rubric, resume).

Select with the JOB_AGENT_PROFILE env var (default "amit"). Each profile gets its own data directory,
so scans, assessments and reports of different candidates never mix.
"""
import json
import os
import pathlib

HERE = pathlib.Path(__file__).parent
NAME = os.environ.get("JOB_AGENT_PROFILE") or ("amit" if (HERE / "profiles" / "amit.json").exists() else "demo_backend")
P = json.loads((HERE / "profiles" / f"{NAME}.json").read_text(encoding="utf-8-sig"))
DATA = HERE / "data" if NAME == "amit" else HERE / "data" / NAME
DATA.mkdir(parents=True, exist_ok=True)
RESUME_PATH = HERE / P["resume_path"]


