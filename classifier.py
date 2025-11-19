import json
import asyncio
import backoff
import datetime

class NewsClassifier:
    def __init__(self, json_schema, prompt, articles, model, client):
        self.json_schema = json_schema
        self.prompt = prompt
        self.articles = articles
        self.model = model
        self.client = client

    def build_articles_payload(self, batch):
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
    async def classify_batch_async(self, batch):
        payload = self.build_articles_payload(batch)
        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_schema", "json_schema": self.json_schema},
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user",
                 "content": "Classify the following articles:\n\n" +
                            json.dumps({"articles": payload}, ensure_ascii=False)}
            ],
        )
        return json.loads(response.choices[0].message.content)

    def chunk(self, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    async def main(self, batch_size, max_parallel):
        for art in self.articles:
            art.setdefault("regionGuess", None)

        region_groups = {
            "North America": [],
            "Europe": [],
            "Asia": [],
            "Oceania": [],
            "Latin America": []
        }

        for art in self.articles:
            guess = art.get("regionGuess")
            if guess in region_groups:
                region_groups[guess].append(art)

        selected_articles = []

        for region, arts in region_groups.items():
            arts_sorted = sorted(
                arts,
                key=lambda x: x.get("date") or "",
                reverse=True
            )
            selected_articles.extend(arts_sorted[:25])

        for idx, art in enumerate(selected_articles):
            art["id"] = idx

        sem = asyncio.Semaphore(max_parallel)
        tasks = []

        async def sem_task(batch):
            async with sem:
                return await self.classify_batch_async(batch)

        for batch in self.chunk(selected_articles, batch_size):
            tasks.append(asyncio.create_task(sem_task(batch)))

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
            if not art.get("keep"):
                continue

            required = [
                "title", "summary", "date", "whyItMatters",
                "source", "tags", "url", "nbimSentiment", "region"
            ]
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

        return final
