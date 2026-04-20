"""
Compare Agent — scores and ranks products by value-for-money.

Scoring formula (0-100):
  rating_component  = (rating / 5) * 55           # up to 55 pts
  price_component   = (1 - price/max_price) * 35  # up to 35 pts (if budget known)
  preference_bonus  = 10 if any pref keyword in name else 0
"""

from __future__ import annotations
from typing import List, Optional


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def score_product(
    product: dict,
    max_price: Optional[float] = None,
    preference_keywords: Optional[List[str]] = None,
) -> float:
    rating = _safe_float(product.get("rating"))
    price  = _safe_float(product.get("price"))

    rating_score = (rating / 5.0) * 55.0

    if max_price and max_price > 0 and price > 0:
        price_ratio  = min(price / max_price, 1.0)
        price_score  = (1.0 - price_ratio) * 35.0
    elif price > 0:
        # No budget given — reward cheaper products gently
        price_score = min(10_000 / price, 35.0)
    else:
        price_score = 0.0

    pref_bonus = 0.0
    if preference_keywords:
        name_lower = product.get("name", "").lower()
        if any(kw.lower() in name_lower for kw in preference_keywords):
            pref_bonus = 10.0

    return round(rating_score + price_score + pref_bonus, 2)


class CompareAgent:
    def rank_products(
        self,
        products: List[dict],
        max_price: Optional[float] = None,
        preference_keywords: Optional[List[str]] = None,
    ) -> List[dict]:
        """Return products sorted by score descending (score field added in-place)."""
        if not products:
            return []
        scored = []
        for p in products:
            p = dict(p)  # avoid mutating caller's list
            p["score"] = score_product(p, max_price, preference_keywords)
            scored.append(p)
        return sorted(scored, key=lambda x: x["score"], reverse=True)
