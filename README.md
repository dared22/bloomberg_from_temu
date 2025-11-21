# NBIM Regulatory News Dashboard

I started by figuring out NBIM’s top five markets in `top_5_markets.ipynb`, and then built a small pipeline to surface regulatory news for those markets.

## What this code does
- `fetch_news.py` pulls Google News RSS for region-specific keywords, cleans the HTML, deduplicates by hashed URL, and keeps the newest items first.
- `classifier.py` batches the articles and calls the OpenAI chat API with a strict JSON schema to decide `keep=true/false`, region, summary, why it matters for NBIM, tags, and NBIM sentiment. It trims how many articles per region are sent (configurable) to keep latency down. (It is still pretty slow though)
- `config.py` holds the system prompt, JSON schema, search keywords, headers, and snippet length limit.
- `app.py` is a Streamlit dashboard that:
  - loads cached classifications from `regulatory_news.json` immediately,
  - On refresh button starts up scraping and classification. 
  - shows filters, sentiment bars, and article cards with tags and source links.
- `assets/style.css` adjusts the look of the dashboard to mimic NBIM style.

## How the pipeline flows
1) Fetch: Google News RSS for each region keyword, basic HTML cleaning, dedupe by URL hash, sort newest first.
2) Select: batch-size (how many articles to send to chatgpt in one go), max_parallel (how many batches to send in paralell). Also feel free to change change prompt/keywords in config.py
3) Classify: send batches to OpenAI with the prompt/schema, drop `keep=false`, and bucket by region.
4) Cache: write to `regulatory_news.json` so the UI can render instantly on next run.
5) Update: Simply click "Refresh data" button in the UI to get the newest data (it might take it 2-3 min to run through the whole pipeline).

## Run it
```bash
pip install -r requirements.txt 
export OPENAI_KEY=your_key_here
streamlit run app.py
```
Or check out the online version at:
https://nbim-dashboard-6d3a6c69b30e.herokuapp.com/

## Stuff That Needs Fixing
- The openai pipline is very slow. Even after paralellising it takes forever to run. 
- ChatGPT also hallusinates too much to be used in production
- The outputs arn't determenistic, especially the sentiment ones. 
- Streamlit won't update results in real time. 
- But all of the above can be solved in the future, if I have time and motivation. 
- So stay tuned for Bloomerg from Temu v.2 (hooray!)