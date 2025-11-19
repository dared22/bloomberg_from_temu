import hashlib
import os
import re
import time
import tls_client
from bs4 import BeautifulSoup
import json

FETCH_FULL_ARTICLE = False

NBIM_KEYWORDS = [
    "NBIM",
    "Norges Bank Investment Management",
    "Government Pension Fund Global",
    "Norway sovereign wealth fund",
    "GPFG",
]

session = tls_client.Session(
    client_identifier="chrome_120",
    random_tls_extension_order=True,
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "en-US,en;q=0.9",
}

def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()

def safe_get(url, *, params=None):
    try:
        return session.get(url, params=params or {}, headers=DEFAULT_HEADERS)
    except Exception:
        return None

def fetch_google_news(kw):
    params = {
        "q": kw,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
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
            "published": clean(i.pubDate.text) if i.pubDate else None,
            "content": clean(i.description.text) if i.description else None,
        }
        for i in items
    ]


def extract_article_body(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(chunk.strip() for chunk in soup.stripped_strings)
    return clean(text)[:5000]  

def fetch_article_content(url):
    r = safe_get(url)
    if not r or r.status_code != 200:
        return None
    return extract_article_body(r.text)


def fetch_all_google():
    items = []

    for kw in NBIM_KEYWORDS:
        items.extend(fetch_google_news(kw))
        time.sleep(0.2)

    uniq = {}
    for a in items:
        if a.get("url"):
            uniq[hash_url(a["url"])] = a

    articles = list(uniq.values())

    if FETCH_FULL_ARTICLE:
        for a in articles:
            body = fetch_article_content(a["url"])
            if body:
                a["content"] = body
            time.sleep(0.2)

    return articles


def write_output_json(articles, path="output_google_nbim.json"):
    """
    schema:

    {
        "id": int,
        "title": str,
        "date": str,
        "source": str,
        "url": str,
        "snippet": str
    }
    """

    formatted = []

    for idx, a in enumerate(articles):
        formatted.append({
            "id": idx,
            "title": a.get("title", ""),
            "date": a.get("published", ""),
            "source": a.get("source", ""),
            "url": a.get("url", ""),
            "snippet": a.get("content", "")[:800] if a.get("content") else ""
        })

    with open(path, "w") as f:
        json.dump(formatted, f, indent=2)

    return formatted


if __name__ == "__main__":
    articles = fetch_all_google()
    write_output_json(articles)

    for i, a in enumerate(articles):
        print(f"{i+1}. [{a['source']}] {a['title']}")
        print(a["url"])
        print()
