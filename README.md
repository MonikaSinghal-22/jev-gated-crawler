# Jev-Gated Web Crawler

A web crawler that uses [Jev](https://typesafe.ai/) (TypeSafe AI's System One model) as an intelligent gatekeeper. Instead of blindly following every link, Jev evaluates each discovered link for relevance, classifies its value, and scores content quality — so the crawler only follows links worth following.

## How It Works

```
Seed URL → Fetch page → Extract links
    → Jev evaluates each link:
        • Is this relevant to my topic? (yes/no with probability)
        • How valuable is it? (high-value / peripheral / off-topic)
        • What's the expected content quality? (scored 1-3)
    → Only follow approved links (high-value first)
    → Repeat until depth/page limit
```

Every decision is logged — both followed and rejected links — with full Jev scores and probabilities.

## Setup

### Prerequisites

- Python >= 3.10
- A [TypeSafe AI](https://typesafe.ai/) API key (or access via [Opper AI](https://opper.ai/) gateway)

### Install

```bash
pip install -e .
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```
TYPESAFE_API_KEY=your-api-key-here
```

To use the Opper gateway instead of TypeSafe direct:

```
TYPESAFE_API_KEY=your-opper-api-key
JEV_PROVIDER=opper
```

## Usage

### Streamlit Dashboard

```bash
streamlit run src/jev_crawler/app.py
```

Opens a browser with:
- Sidebar to configure seed URL, topic, depth, relevance threshold
- Live progress as the crawler runs
- Results dashboard with classification charts, filterable link decisions table, per-page details
- JSONL download button

### CLI

```bash
jev-crawler \
    --seed-url "https://en.wikipedia.org/wiki/Machine_learning" \
    --topic "machine learning frameworks and libraries" \
    --max-depth 2 \
    --max-pages 10
```

Or run as a module:

```bash
python -m jev_crawler \
    --seed-url "https://example.com" \
    --topic "your topic here"
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--seed-url` | *(required)* | Starting URL(s). Can be specified multiple times. |
| `--topic` | *(required)* | The topic Jev uses to judge link relevance. |
| `--max-depth` | `2` | Maximum crawl depth from seed. |
| `--max-pages` | `50` | Stop after N pages. |
| `--relevance-threshold` | `0.5` | Minimum Jev relevance score to follow a link (0-1). |
| `--delay` | `1.0` | Seconds between requests. |
| `--same-domain` | off | Only follow links on the same domain as the seed. |
| `--concurrency` | `5` | Max concurrent HTTP requests. |
| `--output` | `output/crawl_results.jsonl` | Output file path. |

## Output

Results are written to a JSONL file. Each line is a JSON object containing:

- **Page data** — URL, title, meta description, text snippet, all links found
- **Jev decisions** — For every discovered link: relevance score, classification (high-value/peripheral/off-topic), quality score, and whether it was followed
- **Crawl metadata** — Depth, timestamp

The final line is a summary with aggregate stats:

```json
{
  "_type": "summary",
  "topic": "machine learning frameworks",
  "pages_crawled": 10,
  "links_evaluated": 142,
  "links_followed": 23,
  "links_filtered": 119,
  "high_value_count": 15,
  "peripheral_count": 8,
  "off_topic_count": 119
}
```

## Jev Questions Per Link

The gatekeeper asks Jev three questions for every discovered link in a single API call:

1. **Noul (boolean):** "Is this link likely relevant to the given topic?" → returns probability 0-1
2. **Choice:** "How valuable is this link?" → `high_value` / `peripheral` / `off_topic` with full probability distribution
3. **Score:** "Expected content quality" → scored against a 3-level rubric (low/medium/high)

A link is followed only if `relevance >= threshold` AND `classification != off_topic`. High-value links are crawled before peripheral ones.
