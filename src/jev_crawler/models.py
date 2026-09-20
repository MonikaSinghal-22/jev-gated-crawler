from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LinkInfo:
    url: str
    anchor_text: str
    surrounding_text: str


@dataclass
class LinkDecision:
    url: str
    anchor_text: str
    relevance: float
    classification: str
    classification_probabilities: dict[str, float]
    quality_score: float
    quality_confidence: float
    follow: bool


@dataclass
class PageData:
    url: str
    title: str
    meta_description: str
    text_snippet: str
    links_found: list[LinkInfo]
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status_code: int = 0
    error: str | None = None


@dataclass
class CrawlResult:
    page: PageData
    decisions: list[LinkDecision]
    depth: int


@dataclass
class CrawlStats:
    pages_crawled: int = 0
    links_evaluated: int = 0
    links_followed: int = 0
    links_filtered: int = 0
    high_value_count: int = 0
    peripheral_count: int = 0
    off_topic_count: int = 0
    errors: int = 0
