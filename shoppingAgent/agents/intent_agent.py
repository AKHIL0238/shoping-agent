"""
Intent Agent — parses natural-language shopping queries into structured intent.
Uses Claude Haiku (fast + cheap).  Regex fallback if API fails.
"""

from __future__ import annotations
import os
import re
import json
from typing import Dict, Any

import anthropic


_STOP_WORDS = {
    "buy", "get", "find", "search", "looking", "for", "a", "an", "the",
    "best", "good", "need", "want", "me", "i", "please", "show", "top",
}

_PRICE_PATTERNS = [
    r"(?:under|below|less than|upto|up to|within)\s*(?:rs\.?|inr|₹)?\s*([\d,]+)",
    r"(?:rs\.?|inr|₹)\s*([\d,]+)",
    r"([\d,]+)\s*(?:rs|inr|rupees)",
    r"budget\s*(?:of|is|:)?\s*(?:rs\.?|inr|₹)?\s*([\d,]+)",
    r"(\d+)\s*k\b",   # "50k" → 50000
]


def _clean_keywords(query: str) -> str:
    tokens = re.findall(r'\b\w+\b', query.lower())
    return " ".join(t for t in tokens if t not in _STOP_WORDS)


def _extract_price(text: str) -> float | None:
    text_lower = text.lower()
    # Handle "50k" shorthand
    k_match = re.search(r'(\d+)\s*k\b', text_lower)
    if k_match:
        return float(k_match.group(1)) * 1000

    for pattern in _PRICE_PATTERNS[:-1]:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


class IntentAgent:
    def __init__(self):
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    def parse_intent(self, query: str) -> Dict[str, Any]:
        """
        Returns:
          {
            "keywords": str,
            "max_price": float | None,
            "preferences": str,
            "category": str,
          }
        """
        system = (
            "You are a shopping intent parser.\n"
            "Return ONLY a JSON object with these exact keys:\n"
            "  keywords   (string: clean search keywords)\n"
            "  max_price  (number or null: maximum budget in INR)\n"
            "  preferences (string: brand/quality/feature requirements, '' if none)\n"
            "  category   (string: product category, e.g. Electronics, Clothing)\n"
            "No markdown, no extra text — raw JSON only."
        )
        try:
            msg = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=system,
                messages=[{"role": "user", "content": query}],
            )
            text = re.sub(r"```(?:json)?", "", msg.content[0].text).strip("` \n")
            intent = json.loads(text)
            intent.setdefault("keywords", _clean_keywords(query))
            intent.setdefault("max_price", _extract_price(query))
            intent.setdefault("preferences", "")
            intent.setdefault("category", "")
            return intent
        except Exception:
            return {
                "keywords": _clean_keywords(query),
                "max_price": _extract_price(query),
                "preferences": "",
                "category": "",
            }
