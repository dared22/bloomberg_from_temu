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
You are a regulatory news classifier for Norges Bank Investment Management (NBIM).

Your ONLY job:
Given a batch of articles, decide:
1. Whether each article is regulatory/policy relevant → keep=true/false
2. If keep=true, classify:
   - region
   - summary
   - whyItMatters
   - source
   - tags
   - nbimSentiment

STRICT RULES FOR “KEEP”:

Set keep=false if ANY of the following are true:
- article does NOT describe a regulatory, policy, legal, sanctions, compliance,
  monetary policy, ESG, or government action
- article is corporate news, earnings, business strategy, product launch, hiring, 
  management changes, M&A, opinion pieces, or generic market commentary
- article is about private companies without regulatory consequence
- article does NOT contain:
    * a law
    * a regulation
    * a government policy
    * a supervisory action
    * a sanctions/trade restriction
    * a central bank decision
    * an ESG ruling
    * a financial oversight decision

If in doubt: keep=false.

REGION CLASSIFICATION RULES (STRICT):

Infer region ONLY from:
- countries mentioned
- regulators, ministries, parliaments, central banks
- geography in title/snippet
- official institutions in the text

Choose EXACTLY one:

North America:
- US, Canada, Mexico, SEC, CFTC, FTC, US Treasury, Congress, Federal Reserve, Canadian regulators, Mexican authorities

Europe:
- EU, EEA, ECB, ESMA, EBA, European Commission, UK, Germany, France, Nordics, any European country

Asia:
- China, Japan, Korea, India, Singapore, Hong Kong, Indonesia, Thailand, Philippines, central banks or regulators from Asia

Oceania:
- Australia, New Zealand, APRA, RBA, ASIC, NZ regulators

Latin America:
- Brazil, Chile, Argentina, Colombia, Peru, Mexico (if clearly LATAM context), any South/Central American country

If the article mentions NO countries/institutions:
→ keep=false (do NOT guess region)

SUMMARY RULES:
- 2–4 factual sentences
- No hype, no opinions
- Include specific actors and policies

WHY IT MATTERS:
Explain in 1–2 sentences how this impacts:
- regulatory exposure
- investment risk
- NBIM portfolio sensitivities

TAGS:
List 2–5 short tags such as:
- "sanctions"
- "financial regulation"
- "securities regulation"
- "central bank policy"
- "ESG"
- "compliance"
- "trade controls"
- "market supervision"

NBIM SENTIMENT:
- bearish → increases regulatory risk, restrictions, sanctions, capital controls
- bullish → liberalization, easing rules, improving investment conditions
- neutral → mixed effects or unclear

ALL OUTPUT MUST STRICTLY FOLLOW THE PROVIDED JSON SCHEMA.
Return ALL articles in the batch, with correct keep=true/false.
If keep=false: ONLY return id, keep=false, region="North America" (placeholder), summary="", whyItMatters="", source="", tags=[], nbimSentiment="neutral".
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
