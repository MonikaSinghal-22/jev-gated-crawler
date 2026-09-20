from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlparse

import httpx

from jev_crawler.fetcher import fetch_page
from jev_crawler.gatekeeper import JevGatekeeper
from jev_crawler.models import CrawlResult, CrawlStats
from jev_crawler.storage import CrawlStorage, print_stats


class StorageBackend(Protocol):
    def write_result(self, result: CrawlResult) -> None: ...
    def write_summary(self, stats: CrawlStats, topic: str) -> None: ...
    def close(self) -> None: ...


@dataclass
class CrawlConfig:
    seed_urls: list[str]
    topic: str
    max_depth: int = 2
    max_pages: int = 50
    relevance_threshold: float = 0.5
    delay: float = 1.0
    same_domain: bool = False
    concurrency: int = 5
    output: str = "output/crawl_results.jsonl"


class Crawler:
    def __init__(
        self,
        config: CrawlConfig,
        storage: StorageBackend | None = None,
        on_progress: Callable[[CrawlResult, CrawlStats], None] | None = None,
    ):
        self.config = config
        self.gatekeeper = JevGatekeeper(
            topic=config.topic,
            relevance_threshold=config.relevance_threshold,
        )
        self.visited: set[str] = set()
        self.stats = CrawlStats()
        self.seed_domains: set[str] = set()
        self._storage = storage
        self._on_progress = on_progress

    def _is_allowed_domain(self, url: str) -> bool:
        if not self.config.same_domain:
            return True
        parsed = urlparse(url)
        return parsed.netloc in self.seed_domains

    async def _process_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        depth: int,
        storage: StorageBackend,
    ) -> list[tuple[str, int]]:
        """Fetch a page, evaluate its links with Jev, return approved links with depth."""
        print(f"[depth={depth}] Crawling: {url}")
        page = await fetch_page(client, url)

        if page.error:
            self.stats.errors += 1
            print(f"  Error: {page.error}")
            result = CrawlResult(page=page, decisions=[], depth=depth)
            storage.write_result(result)
            return []

        self.stats.pages_crawled += 1
        print(f"  Title: {page.title}")
        print(f"  Links found: {len(page.links_found)}")

        domain_filtered = [
            link for link in page.links_found
            if link.url not in self.visited and self._is_allowed_domain(link.url)
        ]

        if not domain_filtered:
            result = CrawlResult(page=page, decisions=[], depth=depth)
            storage.write_result(result)
            return []

        print(f"  Evaluating {len(domain_filtered)} links with Jev...")
        decisions = self.gatekeeper.evaluate_links(domain_filtered, page.title)

        self.stats.links_evaluated += len(decisions)
        next_urls: list[tuple[str, int]] = []

        high_value_urls: list[tuple[str, int]] = []
        peripheral_urls: list[tuple[str, int]] = []

        for d in decisions:
            if d.classification == "high_value":
                self.stats.high_value_count += 1
            elif d.classification == "peripheral":
                self.stats.peripheral_count += 1
            elif d.classification == "off_topic":
                self.stats.off_topic_count += 1

            if d.follow and depth + 1 <= self.config.max_depth:
                self.stats.links_followed += 1
                entry = (d.url, depth + 1)
                if d.classification == "high_value":
                    high_value_urls.append(entry)
                else:
                    peripheral_urls.append(entry)
            else:
                self.stats.links_filtered += 1

            status = "FOLLOW" if d.follow else "SKIP"
            print(
                f"  [{status}] {d.classification} "
                f"(relevance={d.relevance:.2f}, quality={d.quality_score:.2f}) "
                f"{d.url[:80]}"
            )

        next_urls = high_value_urls + peripheral_urls

        result = CrawlResult(page=page, decisions=decisions, depth=depth)
        storage.write_result(result)

        if self._on_progress:
            self._on_progress(result, self.stats)

        return next_urls

    async def run(self) -> CrawlStats:
        for url in self.config.seed_urls:
            self.seed_domains.add(urlparse(url).netloc)

        storage = self._storage or CrawlStorage(self.config.output)
        queue: list[tuple[str, int]] = [(url, 0) for url in self.config.seed_urls]
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async with httpx.AsyncClient(
            headers={"User-Agent": "JevCrawler/0.1 (+https://github.com/jev-crawler)"},
        ) as client:
            while queue and self.stats.pages_crawled < self.config.max_pages:
                url, depth = queue.pop(0)

                if url in self.visited:
                    continue
                self.visited.add(url)

                async with semaphore:
                    next_urls = await self._process_page(client, url, depth, storage)

                for entry in next_urls:
                    if entry[0] not in self.visited:
                        queue.append(entry)

                if self.config.delay > 0:
                    await asyncio.sleep(self.config.delay)

        storage.write_summary(self.stats, self.config.topic)
        storage.close()
        print_stats(self.stats)

        return self.stats
