import hashlib
import json
import re
import time
import tls_client
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime


class NewsExtractor:

    def __init__(self, snippet_len, header, keywords, session):
        self.snippet_len = snippet_len
        self.header = header
        self.keywords = keywords
        self.session = session

    def clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()
    
    def clean_html(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        return self.clean_text(text)

    def hash_url(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def safe_get(self, url: str, *, params=None):
        try:
            return self.session.get(url, params=params or {}, headers=self.header)
        except Exception:
            return None
    
    def parse_date_safe(self, d):
        try:
            return parsedate_to_datetime(d)
        except Exception:
            return None
    
    def format_date_iso(self, d):
        dt = self.parse_date_safe(d)
        if not dt:
            return ""
        return dt.strftime("%Y-%m-%d")
    
    def fetch_google_news(self, query: str):
        url = "https://news.google.com/rss/search"
        params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}

        r = self.safe_get(url, params=params)
        if not r or r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")

        results = []
        for item in items:
            results.append({
                "source": "GoogleNews",
                "title": self.clean_text(item.title.text),
                "url": self.clean_text(item.link.text),
                "published": self.clean_text(item.pubDate.text) if item.pubDate else "",
                "content": item.description.text if item.description else "",
            })
        return results
    
    def fetch_all(self):
        collected = []
    
        for region, keywords in self.keywords.items():
            for kw in keywords:
                articles = self.fetch_google_news(kw)
                for art in articles:
                    art["regionGuess"] = region
                collected.extend(articles)
                time.sleep(0.15)
    
        uniq = {}
        for a in collected:
            if a.get("url"):
                uniq[self.hash_url(a["url"])] = a
    
        enriched = []
        for a in uniq.values():
            snippet_raw = a.get("content", "")
            snippet = self.clean_html(snippet_raw)[:self.snippet_len]
    
            enriched.append({
                "title": a.get("title", ""),
                "date": self.format_date_iso(a.get("published", "")),
                "source": a.get("source", "GoogleNews"),
                "url": a.get("url", ""),
                "snippet": snippet,
                "regionGuess": a.get("regionGuess"),
            })

        articles_sorted = sorted(
            enriched,
            key=lambda x: x.get("date", ""),
            reverse=True
        )

        for idx, art in enumerate(articles_sorted):
            art["id"] = idx

        print(f"Saved {len(articles_sorted)} regulatory articles.")

        return articles_sorted



