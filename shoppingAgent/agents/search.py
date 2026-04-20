"""
Search Agent — queries SerpAPI Google Shopping and returns a cleaned product list.
Retries up to MAX_RETRIES times on transient errors.
"""

from __future__ import annotations
import os
import re
import time
import requests
from typing import List, Dict, Optional
from utils.cache import cached_search

MAX_RETRIES = 2
RETRY_DELAY = 1.5   # seconds

_JUNK_TOKENS = {
    "food", "rice", "masala", "oil", "soap", "shampoo",
    "spice", "flour", "sugar", "salt", "biscuit", "drink",
}


def _extract_price(price_str: str) -> Optional[float]:
    if not price_str:
        return None
    clean = price_str.replace(",", "").strip()
    m = re.search(r"[\d.]+", clean)
    return float(m.group()) if m else None


def _is_junk(title: str) -> bool:
    tokens = set(title.lower().split())
    return bool(tokens & _JUNK_TOKENS)


class SearchAgent:
    def __init__(self):
        self._api_key: str | None = None

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            key = os.getenv("SERPAPI_API_KEY")
            if not key:
                raise RuntimeError("SERPAPI_API_KEY is not set in environment")
            self._api_key = key
        return self._api_key

    @cached_search
    def search_products(
        self,
        keywords: str,
        max_price: Optional[float] = None,
        max_results: int = 15,
    ) -> List[Dict]:
        """
        Returns a list of product dicts:
          name, price (float), rating (float), link, image
        """
        query = keywords
        if max_price:
            query += f" under {int(max_price)}"

        params = {
            "engine": "google_shopping",
            "q": query,
            "hl": "en",
            "gl": "in",
            "api_key": self.api_key,
        }

        data = self._fetch_with_retry(params)
        raw_items = data.get("shopping_results", [])

        products: List[Dict] = []
        seen_names: set[str] = set()

        for item in raw_items:
            name = (item.get("title") or "").strip()
            if not name or _is_junk(name):
                continue

            # Deduplicate by normalised name prefix
            key = name[:40].lower()
            if key in seen_names:
                continue
            seen_names.add(key)

            link = (
                item.get("link")
                or item.get("product_link")
                or item.get("serpapi_link")
            )
            if not link:
                continue

            price = _extract_price(item.get("price", ""))
            if max_price and price and price > max_price:
                continue

            rating_raw = item.get("rating", 0)
            try:
                rating = float(rating_raw)
            except (TypeError, ValueError):
                rating = 0.0

            products.append(
                {
                    "name":    name,
                    "price":   price,
                    "rating":  rating,
                    "link":    link,
                    "image":   item.get("thumbnail") or item.get("image") or "",
                    "source":  item.get("source", ""),
                    "reviews": item.get("reviews", 0),
                }
            )

            if len(products) >= max_results:
                break

        return products

    def _fetch_with_retry(self, params: dict) -> dict:
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.get(
                    "https://serpapi.com/search.json",
                    params=params,
                    timeout=15,
                )
                # Check for quota exhaustion before raise_for_status
                if resp.status_code == 429:
                    data = resp.json()
                    err_msg = data.get("error", "SerpAPI quota exceeded")
                    raise RuntimeError(f"SERPAPI_QUOTA_EXCEEDED: {err_msg}")
                resp.raise_for_status()
                return resp.json()
            except RuntimeError:
                raise   # don't retry quota errors
            except Exception as exc:
                last_err = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
        raise RuntimeError(f"SerpAPI request failed after {MAX_RETRIES+1} attempts: {last_err}")
