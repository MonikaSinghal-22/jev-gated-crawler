from __future__ import annotations

import os
import time

import httpx

from jev_crawler.models import LinkDecision, LinkInfo

TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
OPPER_ENDPOINT = "https://api.opper.ai/v3/compat/v1/systemone"


def _build_questions() -> dict:
    return {
        "is_relevant": {
            "type": "noul",
            "instructions": "Is this link likely relevant to the given topic?",
        },
        "value": {
            "type": "choice",
            "instructions": "How valuable is this link for the given topic?",
            "criteria": {
                "high_value": "Directly about the topic, authoritative source",
                "peripheral": "Tangentially related, might have some useful info",
                "off_topic": "Unrelated to the topic",
            },
        },
        "quality": {
            "type": "score",
            "instructions": "Expected content quality based on URL and context",
            "criteria": [
                "Low quality — spam, ads, thin content",
                "Medium quality — some useful content",
                "High quality — authoritative, detailed, trustworthy",
            ],
        },
    }


class JevGatekeeper:
    def __init__(self, topic: str, relevance_threshold: float = 0.5):
        self.topic = topic
        self.relevance_threshold = relevance_threshold

        self.api_key = os.environ.get("TYPESAFE_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY environment variable is not set")

        provider = os.environ.get("JEV_PROVIDER", "typesafe").lower()
        if provider == "opper":
            self.endpoint = OPPER_ENDPOINT
            self.model = os.environ.get("JEV_MODEL", "typesafe/jev-1.13.0")
        else:
            self.endpoint = TYPESAFE_ENDPOINT
            self.model = os.environ.get("JEV_MODEL", "jev-latest")

        self.http = httpx.Client(timeout=30.0)

    def _call_jev(self, state: str, max_retries: int = 3) -> dict:
        for attempt in range(max_retries):
            resp = self.http.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "state": state,
                    "questions": _build_questions(),
                },
            )
            if resp.status_code in (429, 502, 503, 529):
                wait = 2 ** attempt
                print(f"  [Jev] {resp.status_code} — retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return {}

    def evaluate_link(
        self,
        link: LinkInfo,
        parent_title: str,
    ) -> LinkDecision:
        state = (
            f"Topic: {self.topic}\n"
            f"Parent page: {parent_title}\n"
            f"Link URL: {link.url}\n"
            f"Anchor text: {link.anchor_text}\n"
            f"Surrounding text: {link.surrounding_text}"
        )

        data = self._call_jev(state)
        answers = data["answers"]

        relevance = answers["is_relevant"]["noul"]
        value_choice = answers["value"]["choice"]
        value_probs = answers["value"].get("probabilities", {})
        quality_score = answers["quality"]["score"]
        quality_confidence = answers["quality"].get("confidence", 0.0)

        follow = (
            relevance >= self.relevance_threshold
            and value_choice != "off_topic"
        )

        return LinkDecision(
            url=link.url,
            anchor_text=link.anchor_text,
            relevance=relevance,
            classification=value_choice,
            classification_probabilities=value_probs,
            quality_score=quality_score,
            quality_confidence=quality_confidence,
            follow=follow,
        )

    def evaluate_links(
        self,
        links: list[LinkInfo],
        parent_title: str,
    ) -> list[LinkDecision]:
        decisions = []
        for link in links:
            try:
                decision = self.evaluate_link(link, parent_title)
            except Exception as e:
                decision = LinkDecision(
                    url=link.url,
                    anchor_text=link.anchor_text,
                    relevance=0.0,
                    classification="error",
                    classification_probabilities={},
                    quality_score=0.0,
                    quality_confidence=0.0,
                    follow=False,
                )
                print(f"  [Jev error] {link.url}: {e}")
            decisions.append(decision)
        return decisions
