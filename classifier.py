import json
import asyncio
from openai import AsyncOpenAI
import backoff
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
    - irrelevant financial or corporate earnings
    - articles lacking policy/regulation angle
    
If NOT clearly regulatory: mark keep=false.

If YES:
- classify region as one of:
  "North America", "Europe", "Asia", "Oceania", "Latin America".
- write a 2–4 sentence factual summary.
- explain why this matters from a regulatory/investment risk perspective.
- infer correct source (e.g., Reuters, Bloomberg, AP, FT, Gov press release).
- set meaningful tags.
- classify nbimSentiment: bullish / neutral / bearish.

Always include ALL required fields, even if keep=false.
"""

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
                                "Latin America",
                                "Global"
                            ],
                        },
                        "source": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "url": {"type": "string"},
                        "nbimSentiment": {
                            "type": "string",
                            "enum": ["bullish", "neutral", "bearish"],
                        },
                    },
                    "required": [
                        "id", "keep", "title", "region", "summary", "date",
                        "whyItMatters", "source", "tags", "url", "nbimSentiment",
                    ],
                },
            }
        },
        "required": ["articles"],
    },
}



def build_articles_payload(batch):
    return [
        {
            "id": art["id"],
            "title": art["title"],
            "date": art.get("date") or "",
            "source": art.get("source") or "",
            "url": art["url"],
            "snippet": art.get("snippet") or "",
            "regionGuess": art.get("regionGuess") or ""
        }
        for art in batch
    ]



@backoff.on_exception(backoff.expo, Exception, max_tries=5)
async def classify_batch_async(batch):
    payload = build_articles_payload(batch)
    response = await client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_schema", "json_schema": JSON_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": "Classify the following articles:\n\n" +
                        json.dumps({"articles": payload}, ensure_ascii=False)}
        ],
    )
    return json.loads(response.choices[0].message.content)


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


async def main():

    # Load scraped articles
    with open("regulatory_articles.json", "r") as f:
        loaded = json.load(f)

    # Ensure regionGuess exists
    for art in loaded:
        art.setdefault("regionGuess", None)

    # Group by regionGuess
    region_groups = {
        "North America": [],
        "Europe": [],
        "Asia": [],
        "Oceania": [],
        "Latin America": []
    }

    for art in loaded:
        guess = art.get("regionGuess")
        if guess in region_groups:
            region_groups[guess].append(art)

    #top 25 for each region
    selected_articles = []

    for region, arts in region_groups.items():
        arts_sorted = sorted(
            arts, key=lambda x: x["date"] or datetime.datetime.min, reverse=True
        )

        top_25 = arts_sorted[:25]
        selected_articles.extend(top_25)

    for idx, art in enumerate(selected_articles):
        art["id"] = idx
        if "_parsed_date" in art:
            del art["_parsed_date"]

    #feed chat with batches
    BATCH_SIZE = 25
    MAX_PARALLEL = 6

    sem = asyncio.Semaphore(MAX_PARALLEL)
    tasks = []

    async def sem_task(batch):
        async with sem:
            return await classify_batch_async(batch)

    for batch in chunk(selected_articles, BATCH_SIZE):
        tasks.append(asyncio.create_task(sem_task(batch)))

    raw_results = await asyncio.gather(*tasks)

    # Flatten
    results = []
    for r in raw_results:
        results.extend(r["articles"])

    # Final aggregation
    final = {
        "North America": [],
        "Europe": [],
        "Asia": [],
        "Oceania": [],
        "Latin America": [],
        "Global" : []
    }

    for art in results:
        if not isinstance(art, dict):
            continue
        if not art.get("keep"):
            continue

        required = ["title", "summary", "date", "whyItMatters",
                    "source", "tags", "url", "nbimSentiment", "region"]
        if not all(k in art for k in required):
            continue

        region = art["region"]  

        if region not in final:
            region = "Global"

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

    with open("regulatory_news.json", "w") as f:
        json.dump(final, f, indent=2)

    print("New regulatory_news.json generated")


asyncio.run(main())
