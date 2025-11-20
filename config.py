MAX_SNIPPET_LEN = 800

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

KEYWORDS = {
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
- infer correct source.
- set tags.
- classify nbimSentiment.

Always include ALL required fields.
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
                                "Latin America"
                            ],
                        },
                        "source": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
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
