"""
Recommend Agent — generates a concise, personalized shopping recommendation
using Claude Haiku.  Includes memory context for personalization.
"""

from __future__ import annotations
import os
import json
from typing import List, Dict

import anthropic


class RecommendAgent:
    def __init__(self):
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    def recommend(
        self,
        query: str,
        ranked_products: List[Dict],
        memory_context: str = "",
    ) -> str:
        if not ranked_products:
            return "No products found. Try adjusting your search or budget."

        top5 = ranked_products[:5]
        products_text = "\n".join(
            f"#{i+1}  {p.get('name','?')[:60]}  |  "
            f"₹{int(p.get('price') or 0):,}  |  "
            f"Rating: {p.get('rating','N/A')}  |  "
            f"Score: {p.get('score', 0):.1f}"
            for i, p in enumerate(top5)
        )

        system = (
            "You are a friendly, expert shopping assistant.\n"
            "Write a 2-3 sentence recommendation that:\n"
            "  • Names the top pick explicitly\n"
            "  • Mentions its price and rating\n"
            "  • Gives one concrete reason it's the best choice\n"
            "Be direct and helpful.  No filler words."
        )

        user_msg = f'User searched for: "{query}"\n\nTop products:\n{products_text}'
        if memory_context:
            user_msg += f"\n\nUser context:\n{memory_context}"

        try:
            msg = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            return msg.content[0].text.strip()
        except Exception as exc:
            if top5:
                p = top5[0]
                return (
                    f"Top pick: **{p.get('name','?')[:50]}** at "
                    f"₹{int(p.get('price') or 0):,} "
                    f"(rating: {p.get('rating','N/A')}/5). "
                    "Highest value-for-money in the results."
                )
            return "Unable to generate recommendation at this time."
