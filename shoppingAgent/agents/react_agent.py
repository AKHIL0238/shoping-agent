"""
ReActAgent — Truly Autonomous AI Shopping Agent.

What makes this genuinely agentic:
  • No fixed pipeline — Claude plans its own sequence of tools every run
  • 12 tools across 5 categories (search, analysis, comparison, memory, output)
  • Multi-search strategy for comprehensive product coverage
  • Persistent memory: recalls past searches, saves preferences permanently
  • Market insights + product comparison before recommending
  • Up to 15 iterations — fully uses the tool set to find the best answer
"""

from __future__ import annotations
import os
from typing import Any, Callable, Dict, List, Optional

import anthropic

from agents.tools_registry import TOOL_SCHEMAS, ToolExecutor


StepCallback = Callable[[str, str, Any], None]   # (tool_name, status, data)

_SYSTEM_PROMPT = """\
You are ShopMind — a truly autonomous AI shopping agent for Indian e-commerce.
Your mission: find the BEST products and deliver an expert recommendation.

━━ YOUR 13 TOOLS ━━
MEMORY    • save_preference       — permanently store a detected preference
INTENT    • parse_intent          — extract keywords, budget, category
SEARCH    • multi_search          — 2-3 parallel searches (PRIMARY search tool)
          • search_products       — single targeted follow-up search
          • refine_query          — better keywords when results are poor
          • find_alternatives     — budget or premium alternatives
WEB       • web_search            — search the open web for reviews/specs (OPTIONAL enrichment)
          • fetch_page_content    — read a review article URL (OPTIONAL enrichment)
ANALYSIS  • rank_and_filter       — score products by value-for-money (REQUIRED before output)
          • compare_products      — head-to-head comparison of 2-3 close products
          • get_market_insights   — price segment map of current pool
          • evaluate_results      — quality check, decide next action
OUTPUT    • generate_recommendation — final personalised recommendation (call last)

━━ MANDATORY SEQUENCE — follow this every time ━━

1. parse_intent(query)  — extract keywords + budget.

2. multi_search(queries=[...]) — THIS is where actual products come from. ALWAYS call it.
   • Use 2-3 creative keyword variations.
   • Example: ["gaming laptop RTX 4060", "best gaming laptop India 2024", "portable gaming laptop i7"]
   • If pool_total < 6, call refine_query then multi_search again with different terms.

3. rank_and_filter()    — MUST call this. Products will NOT be shown without it.

4. generate_recommendation() — write the recommendation.

5. Write FINAL ANSWER.

━━ OPTIONAL ENRICHMENT (between steps 2 and 3) ━━
• get_market_insights()  — understand price segments (useful when pool > 10 products)
• find_alternatives()    — add budget/premium options
• compare_products()     — when top 2-3 products are very close in price/score
• web_search() + fetch_page_content() — read a real expert review for deeper insight
• save_preference()      — if query reveals brand loyalty or hard requirements

━━ CRITICAL RULES ━━
• rank_and_filter MUST be called before generate_recommendation. No exceptions.
• multi_search is your PRIMARY search tool. Use search_products only for targeted follow-ups.
• web_search is OPTIONAL enrichment — only call it if you have budget iterations left.
• If multi_search returns pool_total=0, immediately call refine_query then multi_search again.
• Never end without calling rank_and_filter + generate_recommendation.

━━ FINAL ANSWER FORMAT ━━
After generate_recommendation, write:

FINAL ANSWER:
<2-3 sentences naming the top product, its price, and why it wins. Be specific.>\
"""


class ReActAgent:
    def __init__(self) -> None:
        self._client: Optional[anthropic.Anthropic] = None
        self.executor = ToolExecutor()

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    # ── Main entry point ───────────────────────────────────────────────────

    def run(
        self,
        query:          str,
        memory_context: str = "",
        callback:       Optional[StepCallback] = None,
        max_iterations: int = 15,
        filters:        Optional[Dict] = None,
        memory:         Optional[Any]  = None,
    ) -> Dict[str, Any]:
        """
        Returns a result dict:
          query, intent, products, ranked_products, recommendation,
          tool_calls, search_history, iterations, error
        """
        # Attach persistent memory so tools can read/write it
        if memory is not None:
            self.executor._memory = memory
        self.executor.reset(query, memory_context)
        filters = filters or {}

        # Build the opening user message.
        # Memory context is intentionally kept brief here — detailed history
        # is fetched via recall_past_searches so Claude knows it's context-only.
        user_msg = f'Find me: "{query}"'
        if filters.get("max_price"):
            user_msg += f"\nBudget: max ₹{int(filters['max_price']):,}"
        if filters.get("min_rating"):
            user_msg += f"\nMin rating: {filters['min_rating']}"
        if memory_context:
            # Only pass lightweight preference signals, not full search history
            pref_lines = [
                ln for ln in memory_context.splitlines()
                if any(kw in ln for kw in ("budget", "Budget", "Interest", "preference", "Goal"))
            ]
            if pref_lines:
                user_msg += "\n\nKnown preferences:\n" + "\n".join(pref_lines[:5])

        messages:   List[Dict] = [{"role": "user", "content": user_msg}]
        final_text: str        = ""
        iteration:  int        = 0

        while iteration < max_iterations:
            iteration += 1

            if callback:
                callback("thinking", "running", {"iteration": iteration})

            response = self.client.messages.create(
                model      = "claude-sonnet-4-6",
                max_tokens = 2048,
                system     = _SYSTEM_PROMPT,
                tools      = TOOL_SCHEMAS,
                messages   = messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            # ── Agent finished ─────────────────────────────────────────────
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        final_text = block.text
                if callback:
                    callback("thinking", "complete", {"text": final_text})
                break

            # ── Tool calls ─────────────────────────────────────────────────
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name  = block.name
                    tool_input = block.input

                    if callback:
                        callback(tool_name, "running", tool_input)

                    result_str = self.executor.execute(tool_name, tool_input)

                    if callback:
                        callback(tool_name, "complete", {"result": result_str, "input": tool_input})

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result_str,
                    })

                messages.append({"role": "user", "content": tool_results})
            else:
                break

        # ── Safety fallback: if agent never called rank_and_filter, do it now ─
        state = self.executor.state
        if not state.get("ranked_products") and state.get("raw_products"):
            try:
                self.executor._tool_rank_and_filter({})
            except Exception:
                pass

        # ── Assemble result ────────────────────────────────────────────────
        recommendation = state.get("recommendation", "")
        if not recommendation:
            if "FINAL ANSWER:" in final_text:
                recommendation = final_text.split("FINAL ANSWER:", 1)[1].strip()
            else:
                recommendation = final_text.strip()

        ranked   = state.get("ranked_products") or state.get("raw_products", [])
        products = state.get("raw_products", [])

        return {
            "query":           query,
            "intent":          state.get("intent", {}),
            "products":        products,
            "ranked_products": ranked,
            "recommendation":  recommendation,
            "tool_calls":      state.get("tool_calls", []),
            "search_history":  state.get("search_attempts", []),
            "iterations":      iteration,
            "error":           None if ranked else "No products found",
        }
