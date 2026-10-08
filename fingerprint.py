"""Fingerprint which hiring system each big company's careers page is built on (read-only page fetch)."""
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SITES = {
    "Wix": "https://www.wix.com/jobs", "monday.com": "https://monday.com/careers",
    "Check Point": "https://careers.checkpoint.com", "CyberArk": "https://www.cyberark.com/careers/",
    "Amdocs": "https://jobs.amdocs.com", "Fiverr": "https://www.fiverr.com/jobs",
    "Playtika": "https://www.playtika.com/careers/", "Gong": "https://www.gong.io/careers",
    "Wiz": "https://www.wiz.io/careers", "Armis": "https://www.armis.com/careers/",
    "Rapyd": "https://www.rapyd.net/company/careers/", "eToro": "https://www.etoro.com/about/careers/",
    "Papaya Global": "https://www.papayaglobal.com/careers/", "Cellebrite": "https://cellebrite.com/en/careers/",
    "Verint": "https://www.verint.com/careers/", "Sapiens": "https://sapiens.com/careers/",
    "Mobileye": "https://www.mobileye.com/careers/", "HiBob": "https://www.hibob.com/careers/",
    "Unity": "https://careers.unity.com", "Kaltura": "https://corp.kaltura.com/careers/",
    "Navan": "https://navan.com/careers", "Next Insurance": "https://www.nextinsurance.com/careers/",
    "Global-e": "https://www.global-e.com/careers/", "Tipalti": "https://tipalti.com/careers/",
    "Cyera": "https://www.cyera.com/careers", "Lusha": "https://www.lusha.com/careers/",
    "Varonis": "https://www.varonis.com/careers", "Silverfort": "https://www.silverfort.com/careers/",
    "Pentera": "https://pentera.io/careers/", "Claroty": "https://claroty.com/careers",
    "Intuit": "https://jobs.intuit.com", "NVIDIA": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "Google": "https://www.google.com/about/careers/applications/", "Microsoft": "https://careers.microsoft.com",
    "Amazon": "https://www.amazon.jobs", "PayPal": "https://paypal.eightfold.ai/careers",
    "Visa": "https://corporate.visa.com/en/jobs.html", "Mastercard": "https://careers.mastercard.com",
    "Salesforce": "https://careers.salesforce.com", "Dynatrace": "https://careers.dynatrace.com",
    "SolarEdge": "https://www.solaredge.com/careers", "Meta": "https://www.metacareers.com",
    "Apple": "https://jobs.apple.com", "Cisco": "https://jobs.cisco.com", "Oracle": "https://careers.oracle.com",
    "SAP": "https://jobs.sap.com", "Samsung": "https://sec.wd3.myworkdayjobs.com/Samsung_Careers",
}
FINGERPRINTS = {
    "comeet": r"comeet\.(co|com)", "greenhouse": r"greenhouse\.io", "lever": r"lever\.co", "workday": r"myworkdayjobs\.com",
    "smartrecruiters": r"smartrecruiters\.com", "ashby": r"ashbyhq\.com", "workable": r"workable\.com",
    "bamboohr": r"bamboohr\.com", "jobvite": r"jobvite\.com", "icims": r"icims\.com", "taleo": r"taleo\.net",
    "successfactors": r"successfactors", "eightfold": r"eightfold\.ai", "phenom": r"phenom|phenompeople",
    "avature": r"avature\.net", "personio": r"personio\.", "recruitee": r"recruitee\.com",
}


def fetch(item):
    name, url = item
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
                                                   "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(1_500_000).decode("utf-8", "ignore")
            final = r.geturl()
        found = [k for k, rx in FINGERPRINTS.items() if re.search(rx, html + final, re.I)]
        return name, "OK", final, found
    except Exception as e:
        return name, f"ERR {str(e)[:40]}", url, []


if __name__ == "__main__":
    with ThreadPoolExecutor(8) as ex:
        for name, status, final, found in ex.map(fetch, SITES.items()):
            print(f"{name:16} {status:8} {','.join(found) or '-':32} {final[:70]}")
