"""For big companies with their own careers site: how are jobs actually listed? (read-only page loads)"""
import re
import sys
from collections import Counter
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SITES = {
    "monday.com": "https://monday.com/careers/jobs", "Wix": "https://careers.wix.com/jobs", "Check Point": "https://careers.checkpoint.com/",
    "Rapyd": "https://www.rapyd.net/company/careers/", "Lusha": "https://www.lusha.com/careers/", "Papaya Global": "https://www.papayaglobal.com/careers/",
    "HiBob": "https://www.hibob.com/careers/", "Pentera": "https://pentera.io/careers/", "Silverfort": "https://www.silverfort.com/careers/",
    "Varonis": "https://www.varonis.com/careers", "Kaltura": "https://corp.kaltura.com/company/careers/", "Verint": "https://www.verint.com/careers/",
    "Mobileye": "https://careers.mobileye.com/", "Unity": "https://unity.com/careers", "Navan": "https://navan.com/careers",
    "Next Insurance": "https://www.nextinsurance.com/careers/", "Hailo": "https://hailo.ai/company-overview/careers/", "Dynatrace": "https://careers.dynatrace.com/",
    "SolarEdge": "https://www.solaredge.com/careers", "Cyera": "https://www.cyera.com/careers", "Claroty": "https://claroty.com/careers",
    "Google": "https://www.google.com/about/careers/applications/jobs/results?q=product%20manager&location=Israel",
    "Check Point2": "https://www.checkpoint.com/careers/",
}
ATS_HINT = re.compile(r"greenhouse|comeet|lever\.co|ashby|workable|smartrecruiters|bamboohr|jobvite|breezy|recruitee|rippling|personio|teamtailor|icims|taleo|successfactors|workday|phenom|eightfold|avature", re.I)


def inspect(page, name, url):
    hosts, apis = Counter(), []
    page.on("request", lambda r: hosts.update([urlparse(r.url).netloc]) if ATS_HINT.search(r.url) else None)

    def on_resp(r):
        try:
            if r.request.resource_type in ("xhr", "fetch") and "json" in r.headers.get("content-type", "") and re.search(r"job|position|career|opening", r.url, re.I):
                body = r.text()
                if len(body) > 800 and ("product" in body.lower() or "engineer" in body.lower()):
                    apis.append((r.request.method, r.url[:130], len(body)))
        except Exception:
            pass
    page.on("response", on_resp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(7000)
    except Exception as e:
        print(f"  ({name}: load issue {str(e)[:50]})")
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => [e.innerText.trim().slice(0,50), e.href])")
    jobl = [l for l in links if re.search(r"/job|/position|/opening|/vacanc|gh_jid|comeet\.com/jobs|/careers/[^/?#]+/[^/?#]+", l[1], re.I) and l[0]]
    frames = [f.url for f in page.frames if ATS_HINT.search(f.url)]
    print(f"\n=== {name}  -> {page.url[:80]}")
    print(f"  job-like links: {len(jobl)} | sample: {[l[0][:30] for l in jobl[:3]]}")
    if hosts: print("  ATS hosts contacted:", dict(hosts))
    if frames: print("  ATS iframes:", frames[:2])
    for a in apis[:3]: print("  JSON api:", a)
    if not (jobl or hosts or frames or apis): print("  nothing job-like found (needs deeper work)")


if __name__ == "__main__":
    names = sys.argv[1:] or list(SITES)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36", locale="en-US")
        for n in names:
            pg = ctx.new_page(); inspect(pg, n, SITES[n]); pg.close()
        b.close()
