from __future__ import annotations

from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup

from jev_crawler.models import LinkInfo, PageData

SKIP_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".css", ".js", ".zip", ".tar", ".gz", ".mp3", ".mp4",
    ".avi", ".mov", ".wmv", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".exe", ".dmg", ".iso",
}

MAX_TEXT_LENGTH = 2000
MAX_SURROUNDING_TEXT = 200


def _normalize_url(base_url: str, href: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    absolute = urljoin(base_url, href)
    clean, _ = urldefrag(absolute)
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https"):
        return None
    suffix = parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""
    if f".{suffix}" in SKIP_EXTENSIONS:
        return None
    return clean


def _extract_surrounding_text(tag) -> str:
    parts = []
    for sibling in [tag.previous_sibling, tag.next_sibling]:
        if sibling and hasattr(sibling, "get_text"):
            parts.append(sibling.get_text(strip=True))
        elif isinstance(sibling, str):
            parts.append(sibling.strip())
    text = " ".join(parts)
    return text[:MAX_SURROUNDING_TEXT]


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[LinkInfo]:
    seen: set[str] = set()
    links: list[LinkInfo] = []
    for tag in soup.find_all("a", href=True):
        url = _normalize_url(base_url, tag["href"])
        if url is None or url in seen:
            continue
        seen.add(url)
        anchor = tag.get_text(strip=True) or ""
        surrounding = _extract_surrounding_text(tag)
        links.append(LinkInfo(url=url, anchor_text=anchor, surrounding_text=surrounding))
    return links


async def fetch_page(client: httpx.AsyncClient, url: str) -> PageData:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return PageData(
                url=url, title="", meta_description="",
                text_snippet="", links_found=[], status_code=resp.status_code,
                error=f"Non-HTML content type: {content_type}",
            )

        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"]

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)[:MAX_TEXT_LENGTH]

        links = _extract_links(soup, url)

        return PageData(
            url=url, title=title, meta_description=meta_desc,
            text_snippet=text, links_found=links, status_code=resp.status_code,
        )
    except Exception as e:
        return PageData(
            url=url, title="", meta_description="",
            text_snippet="", links_found=[],
            error=str(e),
        )
