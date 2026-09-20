from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from jev_crawler.crawler import CrawlConfig, Crawler


def parse_args(argv: list[str] | None = None) -> CrawlConfig:
    parser = argparse.ArgumentParser(
        prog="jev-crawler",
        description="Web crawler with Jev (TypeSafe AI) gatekeeper for intelligent link filtering",
    )
    parser.add_argument(
        "--seed-url",
        required=True,
        action="append",
        dest="seed_urls",
        help="Starting URL(s). Can be specified multiple times.",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="The topic Jev uses to judge link relevance.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum crawl depth from seed (default: 2).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Stop after N pages (default: 50).",
    )
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=0.5,
        help="Minimum Jev relevance score to follow a link (default: 0.5).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between requests (default: 1.0).",
    )
    parser.add_argument(
        "--same-domain",
        action="store_true",
        help="Only follow links on the same domain as the seed URL(s).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent HTTP requests (default: 5).",
    )
    parser.add_argument(
        "--output",
        default="output/crawl_results.jsonl",
        help="Output JSONL file path (default: output/crawl_results.jsonl).",
    )

    args = parser.parse_args(argv)
    return CrawlConfig(
        seed_urls=args.seed_urls,
        topic=args.topic,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        relevance_threshold=args.relevance_threshold,
        delay=args.delay,
        same_domain=args.same_domain,
        concurrency=args.concurrency,
        output=args.output,
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    config = parse_args(argv)

    print(f"Jev Crawler starting")
    print(f"  Topic:      {config.topic}")
    print(f"  Seed URLs:  {config.seed_urls}")
    print(f"  Max depth:  {config.max_depth}")
    print(f"  Max pages:  {config.max_pages}")
    print(f"  Threshold:  {config.relevance_threshold}")
    print(f"  Output:     {config.output}")
    print()

    crawler = Crawler(config)
    asyncio.run(crawler.run())


if __name__ == "__main__":
    main()
