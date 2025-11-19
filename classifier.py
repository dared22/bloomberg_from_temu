import json
import asyncio
import aiohttp
from openai import AsyncOpenAI
import backoff
from email.utils import parsedate_to_datetime
import datetime

client = AsyncOpenAI() 

SYSTEM_PROMPT = """
You are a regulatory news filter for Norges Bank Investment Management (NBIM).

Task:
Given a list of news articles (title, snippet, date, source, url), decide:
1) Is this REGULATORY / POLICY relevant for NBIM's investments?
Return ONLY events that clearly qualify as:
    - financial regulation
    - securities/market regulation
    - government policy changes
    - laws or legislation
    - sanctions or trade restrictions
    - compliance actions
    - monetary policy with market impact
    - ESG/ethical investment rulings
    - cross-border investment rules
    - geopolitical events that affect investment risk or regulatory exposure

Exclude:
    - generic business news
    - press releases without regulatory consequence
    - opinion pieces
    - irrelevant financial reports
    - articles lacking policy/regulation angle
    
If NOT clearly regulatory or policy-related: mark keep=false.

If YES:
- classify region as one of:
  "North America", "Europe", "Asia", "Oceania", "Latin America".
- write a 2–4 sentence summary.
- explain briefly why this matters from a regulatory/investment risk perspective.
- infer a more specific source name from title/snippet.
- set relevant policy/ESG/market/regulation tags.
- classify nbimSentiment: bullish / neutral / bearish.

Be concise, factual, non-speculative.
"""

def build_articles_payload(batch):
    return [
        {
            "id": art["id"],
            "title": art["title"],
            "date": art.get("date") or "",
            "source": art.get("source") or "",
            "url": art["url"],
            "snippet": art.get("snippet") or ""
        }
        for art in batch
    ]

JSON_SCHEMA = {
    "name": "RegulatoryClassification",
    "schema": {
        "type": "object",
        "properties": {
            "articles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "keep": {"type": "boolean"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "date": {"type": "string"},
                        "whyItMatters": {"type": "string"},
                        "region": {
                            "type": "string",
                            "enum": [
                                "North America",
                                "Europe",
                                "Asia",
                                "Oceania",
                                "Latin America"
                            ]
                        },
                        "source": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "url": {"type": "string"},
                        "nbimSentiment": {
                            "type": "string",
                            "enum": ["bullish", "neutral", "bearish"]
                        }
                    },
                    "required": [
                        "id", "keep", "title", "region",
                        "summary", "date", "whyItMatters",
                        "source", "tags", "url", "nbimSentiment"
                    ]
                }
            }
        },
        "required": ["articles"]
    }
}


@backoff.on_exception(backoff.expo, Exception, max_tries=5)
async def classify_batch_async(batch):
    payload = build_articles_payload(batch)

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={
            "type": "json_schema",
            "json_schema": JSON_SCHEMA
        },
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Classify the following articles:\n\n" +
                    json.dumps({"articles": payload}, ensure_ascii=False)
                ),
            },
        ],
    )

    return json.loads(response.choices[0].message.content)


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def parse_date_safe(d):
    if not d:
        return None
    try:
        return parsedate_to_datetime(d)
    except Exception:
        return None


async def main():
    with open("output_google_nbim.json", "r") as file:
        loaded = json.load(file)

    # Parse dates 
    for art in loaded:
        art["_parsed_date"] = parse_date_safe(art.get("date"))

    loaded_sorted = sorted(
        loaded,
        key=lambda x: x["_parsed_date"] or datetime.min,
        reverse=True
    )

    #100 newest
    all_articles = loaded_sorted[:100]
    BATCH_SIZE = 25      
    MAX_PARALLEL = 6     #concurrency

    tasks = []

    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def sem_task(batch):
        async with sem:
            return await classify_batch_async(batch)

    for batch in chunk(all_articles, BATCH_SIZE):
        tasks.append(asyncio.create_task(sem_task(batch)))

    # concurrent results
    raw_results = await asyncio.gather(*tasks)

    results = []
    for r in raw_results:
        results.extend(r["articles"])

    final = {
        "North America": [],
        "Europe": [],
        "Asia": [],
        "Oceania": [],
        "Latin America": [],
        "Global": []
    }

    for art in results:
        if not isinstance(art, dict):
            continue
        if not art.get("keep"):
            continue

        region = art.get("region")

        if region not in final:
            region = "Global"

        # double check gpt
        required = ["title", "summary", "date", "whyItMatters", "source", "tags", "url", "nbimSentiment"]
        if not all(k in art for k in required):
            continue

        final[region].append({
            "title": art["title"],
            "summary": art["summary"],
            "date": art["date"],
            "whyItMatters": art["whyItMatters"],
            "region": region,
            "source": art["source"],
            "tags": art["tags"],
            "url": art["url"],
            "nbimSentiment": art["nbimSentiment"],
        })


    with open("nbim_regulatory_news_by_region.json", "w") as f:
        json.dump(final, f, indent=2)

    print("DONE — wrote nbim_regulatory_news_by_region.json")

asyncio.run(main())
