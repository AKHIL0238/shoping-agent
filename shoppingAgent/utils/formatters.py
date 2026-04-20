"""Formatting helpers used across UI and agents."""

import time
from typing import Union


def format_price(price: Union[int, float, str, None]) -> str:
    """Return ₹-prefixed formatted price or 'N/A'."""
    if price is None:
        return "N/A"
    try:
        val = float(str(price).replace(",", "").replace("₹", "").strip())
        return f"₹{int(val):,}"
    except (ValueError, TypeError):
        return "N/A"


def format_rating(rating: Union[int, float, str, None]) -> str:
    """Return star string and numeric rating."""
    if rating is None:
        return "N/A"
    try:
        val = float(rating)
        stars = "⭐" * min(5, int(val))
        return f"{stars} {val}/5"
    except (ValueError, TypeError):
        return "N/A"


def time_ago(ts: float) -> str:
    """Convert a Unix timestamp to a human-readable 'X ago' string."""
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


def truncate(text: str, max_len: int = 60, suffix: str = "…") -> str:
    return text[:max_len] + suffix if len(text) > max_len else text
