import asyncio
import json
import os
from html import escape
import streamlit as st
import tls_client
from openai import AsyncOpenAI
import altair as alt
import pandas as pd
import threading

from classifier import NewsClassifier
from fetch_news import NewsExtractor
from config import SYSTEM_PROMPT, JSON_SCHEMA, MAX_SNIPPET_LEN, HEADERS, KEYWORDS

CACHE_FILE = "regulatory_news.json"
VALID_SENTIMENTS = {"bearish", "neutral", "bullish"}

st.set_page_config(page_title="NBIM News", page_icon="./assets/favicon.ico", layout="wide")

if "thread_started" not in st.session_state:
    st.session_state.thread_started = False
if "done" not in st.session_state:
    st.session_state.done = False

with open("assets/style.css") as f: 
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {
        "North America": [],
        "Europe": [],
        "Asia Pacific": [],
        "Middle East": [],
        "Latin America": []
    }


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def normalize_sentiment(a):
    s = (a.get("nbimSentiment") or a.get("sentiment") or "neutral").lower().strip()
    return s if s in VALID_SENTIMENTS else "neutral"


cached = load_cache()

session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
extractor = NewsExtractor(snippet_len=MAX_SNIPPET_LEN, header=HEADERS, keywords=KEYWORDS, session=session)
articles = extractor.fetch_all()


async def run_classifier_async():
    client = AsyncOpenAI()
    classifier = NewsClassifier(
        client=client,
        json_schema=JSON_SCHEMA,
        prompt=SYSTEM_PROMPT,
        articles=articles,
        model="gpt-5-mini"
    )
    result = await classifier.main(batch_size=25, max_parallel=6)
    save_cache(result)


def background_runner():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_classifier_async())
    loop.close()
    st.session_state.done = True
    st.rerun()


if not st.session_state.done:
    if not st.session_state.thread_started:
        st.session_state.thread_started = True
        threading.Thread(target=background_runner, daemon=True).start()
    st.info("↻ Updating news in the background…")

else:
    cached = load_cache()


with open("assets/logo.svg") as f:
    logo_svg = f.read()

st.markdown(
    f"""
    <div class="page-header">
        <div class="nbim-logo">{logo_svg}</div>
        <div class="hero-text">
            <h1>GPT News</h1>
            <p>Regulatory news relevant to NBIM's five biggest markets classified by ChatGPT</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


rows = []
for region, items in cached.items():
    c = {"bearish": 0, "neutral": 0, "bullish": 0}
    for a in items:
        c[normalize_sentiment(a)] += 1
    for s, v in c.items():
        rows.append([region, s.capitalize(), v])

df = pd.DataFrame(rows, columns=["Region", "Sentiment", "Count"])
sent_colors = {"Bearish": "#e74c3c", "Neutral": "#9fa6b2", "Bullish": "#2563eb"}

st.markdown("<div class='section-title'>Sentiment Analysis by Region</div>", unsafe_allow_html=True)

chart = (
    alt.Chart(df)
    .mark_bar(size=40, cornerRadius=6)
    .encode(
        x=alt.X("Region:N", axis=alt.Axis(labelAngle=0)),
        y="Count:Q",
        color=alt.Color(
            "Sentiment:N",
            scale=alt.Scale(
                domain=list(sent_colors.keys()),
                range=list(sent_colors.values())
            ),
            legend=alt.Legend(orient="top", title=None),
        ),
        xOffset="Sentiment:N",
    )
    .properties(height=360, background="transparent")
    .configure_axis(
        domainColor="#dcd4c8",
        tickColor="#dcd4c8",
        labelColor="#4b5563",
        gridColor="#c7c7c7",
    )
    .configure_view(fill=None, strokeWidth=0)
)

st.altair_chart(chart, width="stretch")


col_search, col_region, col_sent = st.columns((5, 1.5, 1.5))
search = col_search.text_input("Search:", placeholder="Search by institution or title...")
region_filter = col_region.selectbox("Region:", ["All Regions"] + list(cached.keys()))
sent_filter = col_sent.selectbox("Sentiment:", ["All Sentiment", "bearish", "neutral", "bullish"])

articles_all = []
for region, items in cached.items():
    for a in items:
        x = a.copy()
        x["region"] = region
        x["sentiment"] = normalize_sentiment(a)
        articles_all.append(x)

q = (search or "").lower().strip()
filtered = []
for a in articles_all:
    text = " ".join([
        a.get("title", ""),
        a.get("summary", ""),
        a.get("whyItMatters") or a.get("why_it_matters") or "",
        a.get("source", ""),
        " ".join(a.get("tags") or []),
    ]).lower()

    if q and q not in text:
        continue
    if region_filter != "All Regions" and a["region"] != region_filter:
        continue
    if sent_filter != "All Sentiment" and a["sentiment"] != sent_filter:
        continue
    filtered.append(a)

st.markdown(f"<div class='article-section-title'>Latest Updates <span>({len(filtered)} articles)</span></div>", unsafe_allow_html=True)

for a in filtered:
    title = escape(a.get("title", ""))
    summary = escape(a.get("summary", ""))
    why = escape(a.get("whyItMatters") or a.get("why_it_matters") or "")
    region = escape(a.get("region", ""))
    date = escape(a.get("date", ""))
    source = escape(a.get("source", ""))
    url = escape(a.get("url", ""))
    sentiment = a["sentiment"]
    tags = a.get("tags") or []
    tags_html = "".join(f"<span class='tag-chip'>{escape(str(t))}</span>" for t in tags)
    why_html = f"<div class='article-why'><div class='label'>Why it matters</div><p>{why}</p></div>" if why else ""
    link_html = f"<a class='article-link' href='{url}' target='_blank'>Open article</a>" if url else ""

    st.markdown(
        f"""
        <div class="article-card">
            <div class="article-header">
                <div class="article-title">{title}</div>
                <span class="sentiment-pill" data-tone="{sentiment}">{sentiment}</span>
            </div>
            <div class="article-summary">{summary}</div>
            {why_html}
            <div class="article-meta">
                <span>🌍 {region}</span>
                <span>📅 {date}</span>
            </div>
            <div class="article-tags">{tags_html}</div>
            <div class="article-source">Source: {source}</div>
            {link_html}
        </div>
        """,
        unsafe_allow_html=True
    )

if not filtered:
    st.info("No matching articles found.")
