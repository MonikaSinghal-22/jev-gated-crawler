from __future__ import annotations

import asyncio
import os

import streamlit as st
from dotenv import load_dotenv

from jev_crawler.crawler import CrawlConfig, Crawler
from jev_crawler.models import CrawlResult, CrawlStats
from jev_crawler.storage import InMemoryStorage

load_dotenv()

st.set_page_config(page_title="Jev-Gated Web Crawler", page_icon="🔍", layout="wide")
st.title("Jev-Gated Web Crawler")
st.caption("Crawl the web freely — Jev (TypeSafe AI) decides which links are worth following")

# ── Sidebar: Configuration ──────────────────────────────────────────────────

with st.sidebar:
    st.header("Crawl Configuration")

    seed_url = st.text_input("Seed URL", placeholder="https://en.wikipedia.org/wiki/Web_crawler")
    topic = st.text_input("Topic", placeholder="web crawling and search engines")

    st.subheader("Limits")
    max_depth = st.slider("Max depth", 1, 5, 2)
    max_pages = st.slider("Max pages", 1, 100, 20)

    st.subheader("Jev Settings")
    relevance_threshold = st.slider("Relevance threshold", 0.0, 1.0, 0.5, 0.05)

    st.subheader("Crawl Settings")
    delay = st.slider("Delay between requests (s)", 0.0, 5.0, 1.0, 0.5)
    same_domain = st.checkbox("Same domain only")

    provider = os.environ.get("JEV_PROVIDER", "typesafe").capitalize()
    api_key = os.environ.get("TYPESAFE_API_KEY", "")
    if api_key:
        st.success(f"Provider: {provider}")
    else:
        st.error("TYPESAFE_API_KEY not set in .env")

    start_crawl = st.button("Start Crawl", type="primary", disabled=not (seed_url and topic and api_key))

# ── Session state init ───────────────────────────────────────────────────────

if "results" not in st.session_state:
    st.session_state.results = []
if "stats" not in st.session_state:
    st.session_state.stats = None
if "crawl_done" not in st.session_state:
    st.session_state.crawl_done = False
if "topic" not in st.session_state:
    st.session_state.topic = ""

# ── Run crawl ────────────────────────────────────────────────────────────────

if start_crawl:
    st.session_state.results = []
    st.session_state.stats = None
    st.session_state.crawl_done = False
    st.session_state.topic = topic

    config = CrawlConfig(
        seed_urls=[seed_url],
        topic=topic,
        max_depth=max_depth,
        max_pages=max_pages,
        relevance_threshold=relevance_threshold,
        delay=delay,
        same_domain=same_domain,
    )

    storage = InMemoryStorage()
    progress_bar = st.progress(0, text="Starting crawl...")
    status_text = st.empty()
    current_url_text = st.empty()
    stats_cols = st.columns(4)

    def on_progress(result: CrawlResult, stats: CrawlStats) -> None:
        pct = min(stats.pages_crawled / max_pages, 1.0)
        progress_bar.progress(pct, text=f"Crawling page {stats.pages_crawled} of {max_pages}...")
        current_url_text.code(result.page.url)
        stats_cols[0].metric("Pages", stats.pages_crawled)
        stats_cols[1].metric("Links Evaluated", stats.links_evaluated)
        stats_cols[2].metric("Followed", stats.links_followed)
        stats_cols[3].metric("Filtered", stats.links_filtered)

    crawler = Crawler(config, storage=storage, on_progress=on_progress)

    with st.spinner("Crawling..."):
        asyncio.run(crawler.run())

    st.session_state.results = storage.results
    st.session_state.stats = crawler.stats
    st.session_state.crawl_done = True

    progress_bar.progress(1.0, text="Crawl complete!")
    current_url_text.empty()

# ── Results ──────────────────────────────────────────────────────────────────

if st.session_state.crawl_done and st.session_state.stats:
    stats: CrawlStats = st.session_state.stats
    results: list[CrawlResult] = st.session_state.results

    st.divider()
    st.header("Results")

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pages Crawled", stats.pages_crawled)
    m2.metric("Links Evaluated", stats.links_evaluated)
    m3.metric("Links Followed", stats.links_followed)
    m4.metric("Links Filtered", stats.links_filtered)

    # Classification breakdown
    col_chart, col_stats = st.columns([1, 1])

    with col_chart:
        st.subheader("Classification Distribution")
        import pandas as pd
        chart_data = pd.DataFrame({
            "Classification": ["High Value", "Peripheral", "Off Topic"],
            "Count": [stats.high_value_count, stats.peripheral_count, stats.off_topic_count],
        })
        chart_data = chart_data[chart_data["Count"] > 0]
        if not chart_data.empty:
            st.bar_chart(chart_data.set_index("Classification"))

    with col_stats:
        st.subheader("Crawl Stats")
        st.write(f"**Errors:** {stats.errors}")
        if stats.links_evaluated > 0:
            follow_rate = stats.links_followed / stats.links_evaluated * 100
            st.write(f"**Follow rate:** {follow_rate:.1f}%")
            st.write(f"**High-value rate:** {stats.high_value_count / stats.links_evaluated * 100:.1f}%")
            st.write(f"**Off-topic rate:** {stats.off_topic_count / stats.links_evaluated * 100:.1f}%")

    # All link decisions table
    st.subheader("All Link Decisions")

    all_decisions = []
    for r in results:
        for d in r.decisions:
            all_decisions.append({
                "URL": d.url,
                "Anchor Text": d.anchor_text[:60],
                "Relevance": round(d.relevance, 3),
                "Classification": d.classification,
                "Quality": round(d.quality_score, 3),
                "Followed": "Yes" if d.follow else "No",
                "Parent Page": r.page.title[:50],
            })

    if all_decisions:
        df = pd.DataFrame(all_decisions)

        filter_class = st.multiselect(
            "Filter by classification",
            options=df["Classification"].unique().tolist(),
            default=df["Classification"].unique().tolist(),
        )
        filtered_df = df[df["Classification"].isin(filter_class)]

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL", width="large"),
                "Relevance": st.column_config.ProgressColumn("Relevance", min_value=0, max_value=1),
                "Quality": st.column_config.NumberColumn("Quality", format="%.2f"),
            },
        )
    else:
        st.info("No link decisions recorded.")

    # Per-page details
    st.subheader("Crawled Pages")
    for r in results:
        page = r.page
        label = f"{page.title or page.url} (depth {r.depth}, {len(r.decisions)} links evaluated)"
        with st.expander(label):
            st.write(f"**URL:** {page.url}")
            st.write(f"**Title:** {page.title}")
            if page.meta_description:
                st.write(f"**Description:** {page.meta_description}")
            if page.text_snippet:
                st.text_area("Text snippet", page.text_snippet, height=100, disabled=True, key=f"snippet_{page.url}")
            if r.decisions:
                page_df = pd.DataFrame([
                    {
                        "URL": d.url,
                        "Relevance": round(d.relevance, 3),
                        "Classification": d.classification,
                        "Quality": round(d.quality_score, 3),
                        "Followed": "Yes" if d.follow else "No",
                    }
                    for d in r.decisions
                ])
                st.dataframe(page_df, use_container_width=True, hide_index=True)
            if page.error:
                st.error(f"Error: {page.error}")

    # Download
    st.divider()
    mem_storage = InMemoryStorage()
    mem_storage.results = results
    jsonl_content = mem_storage.to_jsonl(stats, st.session_state.topic)
    st.download_button(
        "Download Results (JSONL)",
        data=jsonl_content,
        file_name="crawl_results.jsonl",
        mime="application/jsonl",
    )

elif not start_crawl:
    st.info("Configure your crawl in the sidebar and click **Start Crawl** to begin.")
