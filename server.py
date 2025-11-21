import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

try:
    import tls_client  # type: ignore
except ImportError:  # pragma: no cover
    tls_client = None
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from classifier import NewsClassifier
from config import SYSTEM_PROMPT, JSON_SCHEMA, MAX_SNIPPET_LEN, HEADERS, KEYWORDS
from fetch_news import NewsExtractor

CACHE_PATH = Path("regulatory_news.json")
CLASSIFIER_BATCH_SIZE = 25
CLASSIFIER_MAX_PARALLEL = 6


def load_cache() -> Dict[str, Any]:
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {
        "North America": [],
        "Europe": [],
        "Asia": [],
        "Oceania": [],
        "Latin America": [],
    }


def save_cache(data: Dict[str, Any]) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=2)


class ClassifierService:
    def __init__(self):
        self.running = False
        self.progress = {"processed": 0, "total": 0}
        self.error = None
        self.lock = threading.Lock()
        self.cache = load_cache()

    def last_updated(self):
        if CACHE_PATH.exists():
            return datetime.fromtimestamp(CACHE_PATH.stat().st_mtime).isoformat()
        return None

    def start(self):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.error = None

        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return True

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if tls_client:
            session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
        else:
            import requests

            session = requests.Session()

        extractor = NewsExtractor(snippet_len=MAX_SNIPPET_LEN, header=HEADERS, keywords=KEYWORDS, session=session)
        articles = extractor.fetch_all()

        self.progress = {"processed": 0, "total": len(articles)}

        client = AsyncOpenAI()
        classifier = NewsClassifier(
            client=client,
            json_schema=JSON_SCHEMA,
            prompt=SYSTEM_PROMPT,
            articles=articles,
            model="gpt-5-mini"
        )

        result = loop.run_until_complete(
            classifier.main(
                batch_size=CLASSIFIER_BATCH_SIZE,
                max_parallel=CLASSIFIER_MAX_PARALLEL,
            )
        )

        save_cache(result)
        self.cache = result
        self.progress = {"processed": len(articles), "total": len(articles)}

        with self.lock:
            self.running = False
            self.progress = {"processed": 0, "total": 0}

        loop.close()


service = ClassifierService()
app = FastAPI(title="NBIM News API")

app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


def response_base():
    return {
        "running": service.running,
        "progress": service.progress,
        "lastUpdated": service.last_updated(),
        "error": service.error,
    }


@app.get("/api/news")
async def api_news():
    service.cache = load_cache()
    return {**response_base(), "data": service.cache}


@app.post("/api/refresh", status_code=202)
async def api_refresh():
    service.start()
    return response_base()


@app.get("/api/status")
async def api_status():
    return response_base()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
