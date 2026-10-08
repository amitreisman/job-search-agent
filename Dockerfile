# Public live demo: serves the showcase page and the live API. Contains NO private data:
# only the web modules, the public company list, the three fictional demo profiles and the built page.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-liberation && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt
COPY webapp.py webcore.py assessor.py boards.py sources_extra.py tailor.py llm.py jprofile.py probe_results.csv companies_extra.csv ./
COPY profiles/demo_backend.json profiles/demo_backend.resume.txt ./profiles/
COPY docs/index.html ./docs/
# Set at deploy time: ANTHROPIC_API_KEY (required), optionally DAILY_CALL_CAP, SESSIONS_PER_IP_HOUR, ALLOW_ORIGIN
ENV JOB_AGENT_PROFILE=demo_backend TRUST_PROXY=1 CV_FONT_DIR=/usr/share/fonts/truetype/liberation
CMD ["sh", "-c", "uvicorn webapp:app --host 0.0.0.0 --port ${PORT:-8000}"]
