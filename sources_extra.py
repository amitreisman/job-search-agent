"""Extra job sources for big companies that run their own careers site on a standard hiring system.

comeet : slug = "<company-uid>|<token>"   (both are public, embedded in the company's careers page)
workday: slug = "<host>|<tenant>|<site>"  (public /wday/cxs JSON endpoint)
amazon : slug = "israel"                  (amazon.jobs public search JSON)
Each fetcher returns dicts: id, title, location, url, posted_at (UTC).
"""
import datetime as dt
import json
import html as _htmlmod
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Accept-Language": "en"}
QUERY = "product manager"  # job-title search used by sources that need a keyword; Scout sets it from the profile
UTC = dt.timezone.utc
html_unescape = _htmlmod.unescape


def _req(url, data=None, headers=None):
    for attempt in range(3):
        try:
            r = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(r, timeout=25) as x:
                return json.load(x)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise
            time.sleep(6 * (attempt + 1))  # rate limited: back off and retry


def _post(url, body):
    return _req(url, json.dumps(body).encode(), {"Content-Type": "application/json"})


# ---------- Comeet ----------
def comeet(slug):
    uid, token = slug.split("|")
    out = []
    for j in _req(f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}&details=false"):
        loc = j.get("location") or {}
        out.append(dict(id=j["uid"], title=j["name"], location=f"{loc.get('name', '')} {loc.get('country', '')}",
                        url=j.get("url_comeet_hosted_page") or j.get("url_active_page"),
                        posted_at=dt.datetime.fromisoformat(j["time_updated"].replace("Z", "+00:00"))))  # last update, not first publish
    return out


def comeet_description(slug, pos_uid):
    uid, token = slug.split("|")
    d = _req(f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions/{pos_uid}?token={token}&details=true")
    return " ".join(x.get("value", "") for x in d.get("details", []))


# ---------- Workday ----------
def _wd_posted(text):
    now = dt.datetime.now(UTC)
    t = (text or "").lower()
    if "today" in t:
        return now
    if "yesterday" in t:
        return now - dt.timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*days", t)
    return now - dt.timedelta(days=int(m.group(1))) if m else now - dt.timedelta(days=30)


def workday(slug, is_pm):
    host, tenant, site = slug.split("|")
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    out, offset, total = [], 0, None
    while offset < 200:
        d = _post(f"{base}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": f"{QUERY} Israel"})
        total = d.get("total") if total is None else total  # Workday reports the total on the first page only
        for j in d.get("jobPostings", []):
            posted, loc = _wd_posted(j.get("postedOn")), j.get("locationsText", "")
            if is_pm(j["title"]):  # list view only says "2 Locations": read the detail page for the real places and date
                try:
                    info = _req(f"{base}{j['externalPath']}")["jobPostingInfo"]
                    loc = " ".join([info.get("location", ""), info.get("country", {}).get("descriptor", "")] +
                                   info.get("additionalLocations", []))
                    if info.get("startDate"):
                        posted = dt.datetime.fromisoformat(info["startDate"]).replace(tzinfo=UTC)
                except Exception:
                    pass
            out.append(dict(id=j["externalPath"], title=j["title"], location=loc,
                            url=f"https://{host}/en-US/{site}{j['externalPath']}", posted_at=posted))
        offset += 20
        if offset >= (total or 0) or not d.get("jobPostings"):
            break
    return out


def workday_description(slug, path):
    host, tenant, site = slug.split("|")
    return _req(f"https://{host}/wday/cxs/{tenant}/{site}{path}")["jobPostingInfo"].get("jobDescription", "")


# ---------- Amazon ----------
def amazon(slug):
    out, offset = [], 0
    while offset < 300:
        # the country filter only works with an empty query; titles are filtered by the Scout
        d = _req(f"https://www.amazon.jobs/en/search.json?base_query=&normalized_country_code[]=ISR&result_limit=50&offset={offset}")
        for j in d.get("jobs", []):
            when = dt.datetime.strptime(re.sub(r"\s+", " ", j["posted_date"]), "%B %d, %Y").replace(tzinfo=UTC)
            out.append(dict(id=j["id_icims"], title=j["title"], location=f"{j.get('normalized_location', '')} Israel",
                            url="https://www.amazon.jobs" + j["job_path"], posted_at=when))
        offset += 50
        if offset >= d.get("hits", 0):
            break
    return out


def amazon_description(jid):
    for off in range(0, 200, 50):
        jobs = _req(f"https://www.amazon.jobs/en/search.json?base_query=&normalized_country_code[]=ISR&result_limit=50&offset={off}").get("jobs", [])
        for j in jobs:
            if str(j["id_icims"]) == str(jid):
                return " ".join(j.get(k, "") for k in ("description", "basic_qualifications", "preferred_qualifications"))
    return ""


# ---------- Eightfold "pcsx" (Microsoft, PayPal, Amdocs ...): slug = "<host>|<domain>" ----------
def pcsx(slug):
    host, domain = slug.split("|")
    out, start = [], 0
    while start < 150:
        d = _req(f"https://{host}/api/pcsx/search?domain={domain}&query={urllib.parse.quote(QUERY)}&location=Israel&start={start}&sort_by=timestamp")
        pos = d["data"].get("positions", [])
        for j in pos:
            out.append(dict(id=str(j["id"]), title=j["name"], location=" ".join(j.get("locations") or []),
                            url=f"https://{host}{j['positionUrl']}",
                            posted_at=dt.datetime.fromtimestamp(j.get("postedTs") or j.get("creationTs"), UTC)))
        if len(pos) < 10:
            break
        start += len(pos)
    return out


def pcsx_description(slug, pos_id):
    host, domain = slug.split("|")
    d = _req(f"https://{host}/api/pcsx/position_details?position_id={pos_id}&domain={domain}&hl=en")["data"]
    return d.get("jobDescription") or json.dumps(d)[:6000]

# ---------- Radancy / TalentBrew HTML (Intuit): slug = "<host>|<keywords>" ----------
def _html(url, ajax=False):
    h = {**UA, **({"X-Requested-With": "XMLHttpRequest"} if ajax else {})}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as x:
                return x.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise
            time.sleep(6 * (attempt + 1))


def radancy(slug):
    host = slug.split("|")[0]
    kw = QUERY
    out, pages = [], 1
    n = 1
    while n <= min(pages, 12):
        q = (f"ActiveFacetID=0&CurrentPage={n}&RecordsPerPage=50&TotalContentResults=0&Distance=50&RadiusUnitType=0"
             f"&Keywords={urllib.parse.quote_plus(kw)}&Location=Israel&ShowRadius=False&IsPagination=False&CustomFacetName="
             "&FacetTerm=&FacetType=0&SearchResultsModuleName=Search+Results&SortCriteria=0&SortDirection=0&SearchType=5"
             "&PostalCode=&fc=&fl=&fcf=&afc=&afl=&afcf=&TotalContentPages=NaN")
        res = json.loads(_html(f"https://{host}/search-jobs/results?{q}", ajax=True))["results"]
        m = re.search(r'data-total-pages="(\d+)"', res)
        pages = int(m.group(1)) if m else 1
        for li in re.findall(r"<li[^>]*data-intuit-jobid.*?</li>", res, re.S):
            href = re.search(r'href="(/job/[^"]+)"', li)
            title = re.search(r"<h2>(.*?)</h2>", li, re.S)
            loc = re.search(r'class="job-location">(.*?)<', li, re.S)
            if not (href and title and loc):
                continue
            location = html_unescape(loc.group(1)).strip()
            posted = dt.datetime.now(UTC)
            if "israel" in location.lower():  # only Israeli jobs need the detail page, for the real posting date
                try:
                    dp = re.search(r'"datePosted"\s*:\s*"([^"]+)"', _html(f"https://{host}{href.group(1)}"))
                    if dp:
                        posted = dt.datetime.fromisoformat(dp.group(1)[:10]).replace(tzinfo=UTC)
                except Exception:
                    pass
            out.append(dict(id=href.group(1), title=html_unescape(title.group(1)).strip(), location=location,
                            url=f"https://{host}{href.group(1)}", posted_at=posted))
        n += 1
    return out


def radancy_description(slug, path):
    host = slug.split("|")[0]
    page = _html(f"https://{host}{path}")
    m = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', page)
    return json.loads(f'"{m.group(1)}"') if m else re.sub(r"<[^>]+>", " ", page)[:6000]

# ---------- SmartRecruiters: slug = company id ----------
def smartrecruiters(slug):
    out, offset = [], 0
    while offset < 300:
        d = _req(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}")
        for j in d.get("content", []):
            loc = j.get("location") or {}
            out.append(dict(id=j["id"], title=j["name"], location=f"{loc.get('city', '')} {loc.get('country', '')}".replace(" il", " Israel"),
                            url=f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
                            posted_at=dt.datetime.fromisoformat(j["releasedDate"].replace("Z", "+00:00"))))
        offset += 100
        if offset >= d.get("totalFound", 0):
            break
    return out


def smartrecruiters_description(slug, jid):
    d = _req(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{jid}")
    secs = ((d.get("jobAd") or {}).get("sections") or {})
    return " ".join((s or {}).get("text", "") for s in secs.values())

# ---------- HiBob careers: slug = company identifier, e.g. "hibob-fa0ad69d0cb34a" ----------
_hibob_cache = {}


def _hibob_list(slug):
    d = _req(f"https://{slug}.careers.hibob.com/api/job-ad", headers={"companyIdentifier": slug})
    _hibob_cache[slug] = {j["id"]: j for j in d.get("jobAdDetails", [])}
    return list(_hibob_cache[slug].values())


def hibob(slug):
    return [dict(id=j["id"], title=j["title"], location=f"{j.get('site', '')} {j.get('country', '')}",
                 url=f"https://{slug}.careers.hibob.com/jobs/{j['id']}", posted_at=dt.datetime.fromisoformat(j["publishedAt"].replace("Z", "+00:00")))
            for j in _hibob_list(slug)]


def hibob_description(slug, jid):
    j = (_hibob_cache.get(slug) or {}).get(jid)
    if j is None:
        _hibob_list(slug)
        j = _hibob_cache[slug].get(jid, {})
    return " ".join(str(j.get(k) or "") for k in ("description", "responsibilities", "requirements"))


# ---------- TeamMe (Comeet-backed career pages, e.g. Silverfort, Claroty): slug = "<project id>|<comeet company>/<uid>" ----------
_teamme_urls = {}


def teamme(slug):
    pid, _ = slug.split("|")
    d = _req(f"https://teamme.link/api/projects/{pid}/positions")
    rows = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list) and v and isinstance(v[0], dict) and "title" in v[0]), [])
    _teamme_urls[pid] = {j["id"]: j.get("applyUrl") for j in rows}
    return [dict(id=j["id"], title=j["title"], location=str(j.get("location") or ""), url=j.get("applyUrl") or "",
                 posted_at=dt.datetime.fromisoformat(j["lastModified"].replace("Z", "+00:00"))) for j in rows]  # last update, not first publish


def teamme_description(slug, jid):
    pid, _ = slug.split("|")
    if jid not in _teamme_urls.get(pid, {}):
        teamme(slug)  # refill the id -> url map
    url = _teamme_urls.get(pid, {}).get(jid)
    if not url:
        return ""
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as x:
        page = x.read().decode("utf-8", "ignore")
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))[:8000]


def fetch(ats, slug, is_pm):
    if ats == "comeet":
        return comeet(slug)
    if ats == "workday":
        return workday(slug, is_pm)
    if ats == "amazon":
        return amazon(slug)
    if ats == "pcsx":
        return pcsx(slug)
    if ats == "radancy":
        return radancy(slug)
    if ats == "smartrecruiters":
        return smartrecruiters(slug)
    if ats == "hibob":
        return hibob(slug)
    if ats == "teamme":
        return teamme(slug)
    raise ValueError(ats)


def description(ats, slug, jid):
    if ats == "comeet":
        return comeet_description(slug, jid)
    if ats == "workday":
        return workday_description(slug, jid)
    if ats == "amazon":
        return amazon_description(jid)
    if ats == "pcsx":
        return pcsx_description(slug, jid)
    if ats == "radancy":
        return radancy_description(slug, jid)
    if ats == "smartrecruiters":
        return smartrecruiters_description(slug, jid)
    if ats == "hibob":
        return hibob_description(slug, jid)
    if ats == "teamme":
        return teamme_description(slug, jid)
    return ""




