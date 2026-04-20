"""
Planner Agent — decomposes a user query into an ordered list of steps
that the Executor will run.  Falls back to a static default plan on error.
"""

from __future__ import annotations
import os
import json
import re
from typing import List, Dict

import anthropic


_DEFAULT_PLAN = [
    {"step": 1, "action": "parse_intent",          "description": "Extract keywords, budget, and preferences from the query.", "tool": "intent_parser"},
    {"step": 2, "action": "search_products",        "description": "Search for matching products via SerpAPI.", "tool": "search_api"},
    {"step": 3, "action": "compare_products",       "description": "Score and rank products by value-for-money.", "tool": "comparator"},
    {"step": 4, "action": "generate_recommendation","description": "Generate a personalized AI recommendation.", "tool": "recommender"},
    {"step": 5, "action": "reflect",                "description": "Review and improve the recommendation quality.", "tool": "reflector"},
]


class PlannerAgent:
    """Uses Claude Haiku to build a dynamic search plan."""

    def __init__(self):
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    def create_plan(self, query: str, context: str = "") -> List[Dict]:
        """
        Returns a list of step dicts.  Each dict has keys:
          step (int), action (str), description (str), tool (str)
        """
        system = (
            "You are a planning agent for an AI shopping assistant.\n"
            "Given a user shopping query, return a JSON array of execution steps.\n"
            "Each step must be: {\"step\": int, \"action\": str, \"description\": str, \"tool\": str}\n"
            "Valid actions: parse_intent, search_products, filter_products, "
            "compare_products, generate_recommendation, reflect\n"
            "Return ONLY valid JSON. No prose."
        )
        user_msg = f"Query: {query}"
        if context:
            user_msg += f"\n\nContext:\n{context}"

        try:
            msg = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = msg.content[0].text
            # Extract JSON array from response
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass  # fall through to default

        # Annotate default plan with the actual query
        plan = [dict(s) for s in _DEFAULT_PLAN]
        plan[0]["description"] = f"Parse intent from: '{query}'"
        return plan
