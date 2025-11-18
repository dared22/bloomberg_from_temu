import tls_client
import requests
from bs4 import BeautifulSoup
import hashlib
import re
import time
import os

API_KEY = os.getenv("NEWSAPI_KEY")
NEWSDATA_KEY = os.getenv("NEWSDATA_KEY")


#cloudfare
session = tls_client.Session(
    client_identifier="chrome_120",
    random_tls_extension_order=True
)

DEBUG = True  



def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()

def debug_log(source, kw, status, text):
    """debug printing."""
    if not DEBUG:
        return
    print(f"\n[DEBUG] Source={source}, Keyword={kw}, Status={status}")
    print("----- BEGIN HTML SNIPPET -----")
    print(text[:300].replace("\n", " "))
    print("----- END HTML SNIPPET -----\n")



NBIM_KEYWORDS = [
    "NBIM",
    "Norges Bank Investment Management",
    "Government Pension Fund Global",
    "Norway sovereign wealth fund",
    "GPFG",
    "\"NBIM regulation\"",
]

def fetch_newsapi(kw, pages=2):
    results = []
    for p in range(1, pages+1):
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": kw,
                "apiKey": API_KEY,
                "language": "en",
                "pageSize": 50,
                "page": p,
                "sortBy": "publishedAt"
            }
        )

        debug_log("NewsAPI", kw, r.status_code, str(r.text))

        if r.status_code != 200:
            continue

        results.extend(r.json().get("articles", []))
        time.sleep(0.2)

    return [{
        "source": "NewsAPI",
        "title": clean(a.get("title")),
        "url": a.get("url")
    } for a in results if a.get("url")]

def fetch_nbim_press():
    url = "https://www.nbim.no/en/news-and-insights/the-press/press-releases/"
    r = session.get(url)

    debug_log("NBIM Press", "STATIC", r.status_code, r.text)

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.select("a.article-list_item")

    return [{
        "source": "NBIM",
        "title": clean(p.get_text()),
        "url": "https://www.nbim.no" + p.get("href")
    } for p in posts]


def fetch_responsible_investor(kw):
    url = f"https://www.responsible-investor.com/?s={kw}"
    r = session.get(url)

    debug_log("ResponsibleInvestor", kw, r.status_code, r.text)

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.select("h3.entry-title a")

    return [{
        "source": "ResponsibleInvestor",
        "title": clean(p.get_text()),
        "url": p.get("href")
    } for p in posts]


def fetch_ai_cio(kw):
    url = f"https://www.ai-cio.com/?s={kw}"
    r = session.get(url)

    debug_log("AI-CIO", kw, r.status_code, r.text)

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.select("h3.entry-title a")

    return [{
        "source": "AI-CIO",
        "title": clean(p.get_text()),
        "url": p.get("href")
    } for p in posts]

def fetch_top1000(kw):
    url = f"https://www.top1000funds.com/?s={kw}"
    r = session.get(url)

    debug_log("Top1000Funds", kw, r.status_code, r.text)

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.select("h3.entry-title a")

    return [{
        "source": "Top1000Funds",
        "title": clean(p.get_text()),
        "url": p.get("href")
    } for p in posts]

def fetch_newsdata(kw):
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_KEY}&q={kw}"
    r = requests.get(url)

    debug_log("NewsData", kw, r.status_code, str(r.text))

    if r.status_code != 200:
        return []

    data = r.json().get("results", [])

    return [{
        "source": "NewsData",
        "title": clean(a.get("title")),
        "url": a.get("link")
    } for a in data if a.get("link")]

def fetch_google_news(kw):
    url = f"https://news.google.com/rss/search?q={kw}"
    r = session.get(url)

    debug_log("GoogleNews", kw, r.status_code, r.text)

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "xml")
    items = soup.find_all("item")

    return [{
        "source": "GoogleNews",
        "title": clean(i.title.text),
        "url": clean(i.link.text)
    } for i in items]

def fetch_ddg(kw):
    url = f"https://duckduckgo.com/html/?q={kw}"
    r = session.get(url)

    debug_log("DuckDuckGo", kw, r.status_code, r.text)

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.select("a.result__a")

    return [{
        "source": "DuckDuckGo",
        "title": clean(a.get_text()),
        "url": a.get("href")
    } for a in links]

def fetch_all():
    items = []

    # NewsAPI
    for kw in NBIM_KEYWORDS:
        items += fetch_newsapi(kw)

    # NBIM press
    items += fetch_nbim_press()

    # Institutional
    for kw in NBIM_KEYWORDS:
        items += fetch_responsible_investor(kw)
        items += fetch_ai_cio(kw)
        items += fetch_top1000(kw)

    # Global sources
    for kw in NBIM_KEYWORDS:
        items += fetch_newsdata(kw)
        items += fetch_google_news(kw)
        items += fetch_ddg(kw)

    # Deduplicate
    uniq = {}
    for a in items:
        if a.get("url"):
            uniq[hash_url(a["url"])] = a

    return list(uniq.values())

articles = fetch_all()


for i, a in enumerate(articles):
    print(f"{i+1}. [{a['source']}] {a['title']}")
    print(a["url"])
    print()
