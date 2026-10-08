"""Web app: serves the showcase page and the live API (upload a CV, get matches, generate a tailored CV / letter).

Run locally:   python -m uvicorn webapp:app --host 0.0.0.0 --port 8765
Hosted:        set ANTHROPIC_API_KEY (and optionally ALLOW_ORIGIN, DAILY_CALL_CAP, SESSIONS_PER_IP_HOUR, TRUST_PROXY=1).
"""
import asyncio
import os
import pathlib

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import webcore

HERE = pathlib.Path(__file__).parent
MAX_UPLOAD = 2 * 1024 * 1024
app = FastAPI(title="Job Search Agent", docs_url=None, redoc_url=None)

if os.environ.get("ALLOW_ORIGIN"):  # only needed when the page is hosted on a different origin than this API
    app.add_middleware(CORSMiddleware, allow_origins=[os.environ["ALLOW_ORIGIN"]], allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else resp.headers.get("Cache-Control", "no-cache")
    return resp


def client_ip(request):
    if os.environ.get("TRUST_PROXY"):
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def err(msg, code=400):
    return JSONResponse({"error": msg}, status_code=code)


@app.get("/")
async def index():
    return FileResponse(HERE / "site" / "index.html", media_type="text/html")


@app.get("/api/health")
async def health():
    return {"ok": True, "live": True, "llm": "api" if webcore.llm.USE_API else "local"}


@app.post("/api/profile")
async def profile(request: Request, file: UploadFile | None = File(None), text: str = Form(""), role: str = Form("")):
    try:
        if file is not None and file.filename:
            data = await file.read(MAX_UPLOAD + 1)
            if len(data) > MAX_UPLOAD:
                return err("The file is larger than 2 MB.", 413)
            cv_text = webcore.extract_text(file.filename, data)
        elif text.strip():
            if len(text) > webcore.MAX_TEXT * 2:
                return err("The pasted text is too long.", 413)
            cv_text = webcore.extract_text("", text.encode("utf-8"))
        else:
            return err("Upload a CV or paste its text.")
        sid, cv, query = await webcore.create_session(cv_text, role.strip()[:60], client_ip(request))
    except webcore.Limit as e:
        return err(str(e), 429 if "Limit" in str(e) or "budget" in str(e) else 400)
    except Exception:
        return err("Could not process this CV. Please try again.", 500)
    asyncio.create_task(webcore.run_matching(sid))  # start searching right away; the page polls for results
    return {"sid": sid, "query": query, "name": cv["name"], "title": cv["title_tag"], "roles": len(cv["roles"])}


@app.get("/api/matches/{sid}")
async def matches(sid: str):
    v = webcore.view(sid)
    return v if v else err("This session has expired. Please upload your CV again.", 404)


@app.post("/api/tailor/{sid}")
async def tailor_endpoint(sid: str, request: Request):
    body = await request.json()
    kind = body.get("kind")
    if kind not in ("cv", "letter"):
        return err("Unknown request.")
    try:
        return await webcore.tailor_job(sid, str(body.get("job_id")), kind)
    except webcore.Limit as e:
        return err(str(e), 429 if "budget" in str(e) else 400)
    except Exception:
        return err("Could not generate this right now. Please try again.", 500)


@app.delete("/api/session/{sid}")
async def delete_session(sid: str):
    webcore.SESSIONS.pop(sid, None)  # the visitor can erase their CV at any moment
    return {"deleted": True}
