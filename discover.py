"""Discovery: open each careers page in a real browser and list the JSON calls it makes.

Usage: python discover.py [name ...]    -> prints candidate job-list endpoints per site.
A candidate = JSON response whose URL/body looks like a job list. We then replay it with plain HTTP when possible.
"""
import json
import sys

from playwright.sync_api import sync_playwright

SITES = {
    "Wix": "https://careers.wix.com/jobs",
    "monday.com": "https://monday.com/careers",
    "Check Point": "https://careers.checkpoint.com/",
    "Playtika": "https://www.playtika.com/careers/",
    "Wiz": "https://www.wiz.io/careers",
    "Gong": "https://www.gong.io/careers",
    "Rapyd": "https://www.rapyd.net/company/careers/",
    "Fiverr": "https://www.fiverr.com/jobs",
    "Intuit": "https://jobs.intuit.com/search-jobs/Israel",
    "Google": "https://www.google.com/about/careers/applications/jobs/results?q=product%20manager&location=Israel",
    "Microsoft": "https://jobs.careers.microsoft.com/global/en/search?q=product%20manager&lc=Israel",
    "PayPal": "https://paypal.eightfold.ai/careers?query=product+manager&location=Israel",
    "Amdocs": "https://jobs.amdocs.com/careers?query=product+manager&location=Israel",
    "Cyera": "https://www.cyera.com/careers",
    "Tipalti": "https://tipalti.com/company/careers/",
    "Varonis": "https://www.varonis.com/careers",
    "CyberArk": "https://careers.cyberark.com/",
    "Armis": "https://www.armis.com/careers/",
}
KEYWORDS = ("job", "position", "career", "opening", "requisition", "posting", "search")


def probe(page, name, url):
    hits = []

    def on_response(r):
        try:
            ct = r.headers.get("content-type", "")
            if "json" not in ct or r.request.resource_type not in ("xhr", "fetch"):
                return
            body = r.text()
            if len(body) < 500:
                return
            low = body.lower()
            score = ("product" in low) + any(k in r.url.lower() for k in KEYWORDS) + ("israel" in low)
            if score >= 2:
                hits.append((score, r.request.method, r.url[:150], len(body), body[:150].replace("\n", " ")))
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  (load issue: {str(e)[:70]})")
    page.remove_listener("response", on_response)
    print(f"\n=== {name}  {page.url[:90]}")
    for h in sorted(hits, reverse=True)[:4]:
        print(f"  [{h[0]}] {h[1]} {h[2]}  ({h[3]} bytes)\n       {h[4]}")
    if not hits:
        print("  no JSON job endpoint seen (server-rendered page or blocked)")


if __name__ == "__main__":
    names = sys.argv[1:] or list(SITES)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36", locale="en-US")
        for n in names:
            pg = ctx.new_page()
            probe(pg, n, SITES[n])
            pg.close()
        b.close()
