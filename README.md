# NBIM Regulatory News Dashboard

I started by figuring out NBIM’s top five markets in `top_5_markets.ipynb`, and then built a small pipeline to surface regulatory news for those markets.

## What this code does
- `fetch_news.py` pulls Google News RSS for region-specific keywords, cleans the HTML, deduplicates by hashed URL, and keeps the newest items first.
- `classifier.py` batches the articles and calls the OpenAI chat API with a strict JSON schema to decide `keep=true/false`, region, summary, why-it-matters, tags, and NBIM sentiment. It trims how many articles per region are sent (configurable) to keep latency down.
- `config.py` holds the system prompt, JSON schema, search keywords, headers, and snippet length limit.
- `app.py` is a Streamlit dashboard that:
  - loads cached classifications from `regulatory_news.json` immediately,
  - kicks off a background refresh (fetch + classify),
  - shows filters, sentiment bars, and article cards with tags and source links.
- `assets/style.css` adjusts the look of the dashboard.

## How the pipeline flows
1) Fetch: Google News RSS for each region keyword, basic HTML cleaning, dedupe by URL hash, sort newest first.
2) Select: batch-size (how many articles to send to chatgpt in one go), max_parallel (how many batches to send in paralell). Also feel free to change change prompt/keywords in config.py
3) Classify: send batches to OpenAI with the prompt/schema, drop `keep=false`, and bucket by region.
4) Cache: write to `regulatory_news.json` so the UI can render instantly on next run.
5) Display: Streamlit shows cached data while the classifier refreshes in the background.

## Run it
```bash
pip install -r requirements.txt 
export OPENAI_KEY=your_key_here
streamlit run app.py
```


