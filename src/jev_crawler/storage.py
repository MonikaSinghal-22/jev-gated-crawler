from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from jev_crawler.models import CrawlResult, CrawlStats


class CrawlStorage:
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.output_path, "w", encoding="utf-8")

    def write_result(self, result: CrawlResult) -> None:
        self._file.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
        self._file.flush()

    def write_summary(self, stats: CrawlStats, topic: str) -> None:
        summary = {
            "_type": "summary",
            "topic": topic,
            **asdict(stats),
        }
        self._file.write(json.dumps(summary, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class InMemoryStorage:
    def __init__(self):
        self.results: list[CrawlResult] = []

    def write_result(self, result: CrawlResult) -> None:
        self.results.append(result)

    def write_summary(self, stats: CrawlStats, topic: str) -> None:
        pass

    def close(self) -> None:
        pass

    def to_jsonl(self, stats: CrawlStats, topic: str) -> str:
        lines = []
        for r in self.results:
            lines.append(json.dumps(asdict(r), ensure_ascii=False))
        summary = {"_type": "summary", "topic": topic, **asdict(stats)}
        lines.append(json.dumps(summary, ensure_ascii=False))
        return "\n".join(lines) + "\n"


def print_stats(stats: CrawlStats) -> None:
    print("\n--- Crawl Summary ---")
    print(f"Pages crawled:    {stats.pages_crawled}")
    print(f"Links evaluated:  {stats.links_evaluated}")
    print(f"Links followed:   {stats.links_followed}")
    print(f"Links filtered:   {stats.links_filtered}")
    print(f"  High-value:     {stats.high_value_count}")
    print(f"  Peripheral:     {stats.peripheral_count}")
    print(f"  Off-topic:      {stats.off_topic_count}")
    print(f"Errors:           {stats.errors}")
