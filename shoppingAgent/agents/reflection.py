"""
Reflection Agent — takes the initial recommendation and improves it:
  • checks factual consistency with the actual product list
  • adds concrete details (price, top pick name)
  • trims vague filler language
Uses Groq Llama for low latency.
"""

from __future__ import annotations
import os
import json
from typing import List, Dict

import groq


class ReflectionAgent:
    def __init__(self):
        self._client: groq.Groq | None = None

    @property
    def client(self) -> groq.Groq:
        if self._client is None:
            self._client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
        return self._client

    def reflect(
        self,
        query: str,
        products: List[Dict],
        recommendation: str,
    ) -> str:
        """
        Returns an improved recommendation string.
        Falls back to the original if anything goes wrong.
        """
        if not recommendation or not products:
            return recommendation

        top5 = products[:5]
        product_summary = json.dumps(
            [
                {
                    "name": p.get("name", "")[:60],
                    "price": p.get("price"),
                    "rating": p.get("rating"),
                }
                for p in top5
            ],
            ensure_ascii=False,
        )

        system = (
            "You are a quality-review agent for a shopping assistant.\n"
            "Given the original recommendation and the actual product data, "
            "rewrite the recommendation to be:\n"
            "  1. Concise (2-4 sentences max)\n"
            "  2. Specific — mention the top product name and its price\n"
            "  3. Actionable — tell the user exactly what to do\n"
            "  4. Honest — only reference products that are actually in the list\n"
            "Return ONLY the improved recommendation text, no labels or headers."
        )

        user_msg = (
            f"User query: {query}\n\n"
            f"Top products:\n{product_summary}\n\n"
            f"Original recommendation:\n{recommendation}"
        )

        try:
            msg = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=256,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
            )
            improved = msg.choices[0].message.content.strip()
            return improved if improved else recommendation
        except Exception:
            return recommendation
