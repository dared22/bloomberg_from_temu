import hashlib
import re
import time
import json
import tls_client
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime


MAX_SNIPPET_LEN = 800

session = tls_client.Session(
    client_identifier="chrome_120",
    random_tls_extension_order=True,
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

REGULATORY_KEYWORDS = {
    "North America": [
        "US financial regulation",
        "US sanctions policy",
    ],
    "Europe": [
        "EU regulation",
        "EU sanctions policy",
    ],
    "Asia": [
        "Asia financial regulation",
        "Asia central bank policy",
    ],
    "Oceania": [
        "Australia financial regulation",
        "New Zealand financial regulation",
    ],
    "Latin America": [
        "Latin America financial regulation",
        "Brazil financial regulation",
    ],
}


def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()

def clean_html(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(" ", strip=True)

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()

def safe_get(url, *, params=None):
    try:
        return session.get(url, params=params or {}, headers=DEFAULT_HEADERS)
    except Exception:
        return None

def extract_article_body(html_text):
    """HTML->text"""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(chunk.strip() for chunk in soup.stripped_strings)
    return clean(text)


def fetch_google_news(kw):
    """Fetch from Google News RSS search."""
    params = {"q": kw, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = "https://news.google.com/rss/search"

    r = safe_get(url, params=params)
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "xml")
    items = soup.find_all("item")

    return [
        {
            "source": "GoogleNews",
            "title": clean(i.title.text),
            "url": clean(i.link.text),
            "published": clean(i.pubDate.text) if i.pubDate else "",
            "content": clean(i.description.text) if i.description else "",
        }
        for i in items
    ]



def parse_date_safe(d):
    try:
        return parsedate_to_datetime(d)
    except Exception:
        return None
    
def format_date_iso(d):
    dt = parse_date_safe(d)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d")


def fetch_all():
    collected = []

    for region, keywords in REGULATORY_KEYWORDS.items():
        for kw in keywords:
            articles = fetch_google_news(kw)
            for a in articles:
                a["regionGuess"] = region
            collected.extend(articles)
            time.sleep(0.15)  #rate control

    uniq = {}
    for a in collected:
        if a.get("url"):
            uniq[hash_url(a["url"])] = a

    enriched = []
    for a in uniq.values():

        snippet_html = a.get("content", "")
        snippet = clean(clean_html(snippet_html))[:MAX_SNIPPET_LEN]
        snippet = snippet[:MAX_SNIPPET_LEN]

        enriched.append({
            "title": a.get("title", ""),
            "date": format_date_iso(a.get("published", "")),
            "source": a.get("source", "GoogleNews"),
            "url": a.get("url", ""),
            "snippet": snippet,
            "regionGuess": a.get("regionGuess", None)
        })

    return enriched



def write_output_json(articles):
    articles_sorted = sorted(
        articles,
        key=lambda x: x.get("date", ""),
        reverse=True
    )

    final = []
    for idx, art in enumerate(articles_sorted):
        art["id"] = idx
        final.append(art)

    with open("regulatory_articles.json", "w") as f:
        json.dump(final, f, indent=2)

    return final




if __name__ == "__main__":
    arts = fetch_all()
    final = write_output_json(arts)
    print(f"Saved {len(final)} regulatory articles.")
