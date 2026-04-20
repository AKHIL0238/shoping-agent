"""
tools/product_api.py — thin wrapper kept for backwards-compatibility.
New code should use agents.search.SearchAgent directly.
"""

from __future__ import annotations
from agents.search import SearchAgent

_agent = SearchAgent()


def search_products(query: str, max_price: float = None, max_results: int = 15) -> list:
    """Proxy to SearchAgent.search_products (uses env SERPAPI_API_KEY)."""
    return _agent.search_products(
        keywords=query,
        max_price=max_price,
        max_results=max_results,
    )
