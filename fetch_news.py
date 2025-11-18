import hashlib
import os
import re
import time
import requests
import tls_client
from bs4 import BeautifulSoup
import json

API_KEY = os.getenv("NEWSAPI_KEY")
NEWSDATA_KEY = os.getenv("NEWSDATA_KEY")

# Cloudflare-friendly session
session = tls_client.Session(
    client_identifier="chrome_120",
    random_tls_extension_order=True,
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

DEBUG = False


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


def safe_get(url, *, params=None, parser_source="", kw=""):
    """Session GET with headers & debug + exception handling."""
    try:
        resp = session.get(url, params=params or {}, headers=DEFAULT_HEADERS)
    except Exception as exc:
        debug_log(parser_source, kw, "EXC", str(exc))
        return None

    debug_log(parser_source, kw, resp.status_code, resp.text)
    return resp


def fetch_newsapi(kw, pages=2):
    results = []
    for p in range(1, pages + 1):
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": kw,
                "apiKey": API_KEY,
                "language": "en",
                "pageSize": 50,
                "page": p,
                "sortBy": "publishedAt",
            },
            timeout=20,
        )

        debug_log("NewsAPI", kw, r.status_code, str(r.text))

        if r.status_code == 429:
            # hit rate limit; stop trying more pages/keywords for now
            break
        if r.status_code != 200:
            continue

        results.extend(r.json().get("articles", []))
        time.sleep(0.2)

    return [
        {
            "source": "NewsAPI",
            "title": clean(a.get("title")),
            "url": a.get("url"),
            "published": a.get("publishedAt"),
            "content": a.get("content") or a.get("description"),
        }
        for a in results
        if a.get("url")
    ]


def fetch_nbim_press():
    url = "https://www.nbim.no/en/news-and-insights/the-press/press-releases/"
    r = safe_get(url, parser_source="NBIM Press", kw="STATIC")

    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    posts = soup.select("a.article-list_item")

    return [
        {
            "source": "NBIM",
            "title": clean(p.get_text()),
            "url": "https://www.nbim.no" + p.get("href"),
            "published": None,
            "content": None,
        }
        for p in posts
    ]


def fetch_wordpress_search(base_url, selector, source, kw, pages=3):
    """Handles paginated WP search pages to pull more results."""
    results = []
    for page in range(1, pages + 1):
        url = f"{base_url}?s={kw}&paged={page}"
        r = safe_get(url, parser_source=source, kw=kw)
        if not r or r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        posts = soup.select(selector)
        if not posts:
            break

        results.extend(
            [
                {
                    "source": source,
                    "title": clean(p.get_text()),
                    "url": p.get("href"),
                    "published": None,
                    "content": None,
                }
                for p in posts
            ]
        )

        time.sleep(0.2)

    return results


def fetch_responsible_investor(kw):
    return fetch_wordpress_search(
        "https://www.responsible-investor.com/",
        "h3.entry-title a",
        "ResponsibleInvestor",
        kw,
        pages=4,
    )


def fetch_ai_cio(kw):
    return fetch_wordpress_search(
        "https://www.ai-cio.com/",
        "h3.entry-title a",
        "AI-CIO",
        kw,
        pages=4,
    )


def fetch_newsdata(kw, pages=3):
    results = []
    next_page = None
    for _ in range(pages):
        params = {
            "apikey": NEWSDATA_KEY,
            "q": kw,
            "language": "en",
        }
        if next_page:
            params["page"] = next_page

        r = requests.get("https://newsdata.io/api/1/news", params=params, timeout=20)
        debug_log("NewsData", kw, r.status_code, str(r.text))
        if r.status_code != 200:
            break

        payload = r.json()
        data = payload.get("results", [])
        results.extend(data)

        next_page = payload.get("nextPage")
        if not next_page:
            break

        time.sleep(0.2)

    return [
        {
            "source": "NewsData",
            "title": clean(a.get("title")),
            "url": a.get("link"),
            "published": a.get("pubDate"),
            "content": a.get("description"),
        }
        for a in results
        if a.get("link")
    ]


def fetch_google_news(kw):
    params = {
        "q": kw,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    url = "https://news.google.com/rss/search"
    r = safe_get(url, parser_source="GoogleNews", kw=kw, params=params)

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


def fetch_ddg(kw):
    url = f"https://duckduckgo.com/html/?q={kw}"
    r = safe_get(url, parser_source="DuckDuckGo", kw=kw)

    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.select("a.result__a")

    return [
        {
            "source": "DuckDuckGo",
            "title": clean(a.get_text()),
            "url": a.get("href"),
            "published": None,
            "content": None,
        }
        for a in links
    ]


def extract_article_body(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(chunk.strip() for chunk in soup.stripped_strings)
    return clean(text)[:5000]  # trim to avoid huge payloads


def fetch_article_content(url):
    r = safe_get(url, parser_source="ArticleFetch", kw=url)
    if not r or r.status_code != 200:
        return None, None

    body = extract_article_body(r.text)

    soup = BeautifulSoup(r.text, "html.parser")
    # time tags with datetime
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        pub = clean(time_tag.get("datetime"))
    elif time_tag and time_tag.get_text():
        pub = clean(time_tag.get_text())
    else:
        pub = None

    return body, pub


def fetch_all():
    items = []

    for kw in NBIM_KEYWORDS:
        items += fetch_newsapi(kw)

    items += fetch_nbim_press()

    for kw in NBIM_KEYWORDS:
        items += fetch_responsible_investor(kw)
        items += fetch_ai_cio(kw)

    for kw in NBIM_KEYWORDS:
        items += fetch_newsdata(kw)
        items += fetch_google_news(kw)
        items += fetch_ddg(kw)

    uniq = {}
    for a in items:
        if a.get("url"):
            uniq[hash_url(a["url"])] = a

    enriched = []
    for a in uniq.values():
        body, pub = fetch_article_content(a["url"])
        if body:
            a["content"] = body
        if pub and not a.get("published"):
            a["published"] = pub
        enriched.append(a)

    return enriched


def write_output_json(articles, path="output_scrape.json"):
    records = []
    for a in articles:
        record = {
            "title": a.get("title") or "",
            "date": a.get("published") or "",
            "source": a.get("source") or "",
            "tags": ["sovereign wealth", "NBIM"],
            "content": a.get("content") or "",
            "url": a.get("url") or "",
        }
        records.append(record)

    with open(path, "w") as f:
        json.dump(records, f, indent=2)

    return records


if __name__ == "__main__":
    articles = fetch_all()

    write_output_json(articles)

    for i, a in enumerate(articles):
        print(f"{i+1}. [{a['source']}] {a['title']}")
        print(a["url"])
        print()
