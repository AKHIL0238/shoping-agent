"""
ReActAgent — Truly Autonomous AI Shopping Agent.

What makes this genuinely agentic:
  • No fixed pipeline — Groq Llama plans its own sequence of tools every run
  • 12 tools across 5 categories (search, analysis, comparison, memory, output)
  • Multi-search strategy for comprehensive product coverage
  • Persistent memory: recalls past searches, saves preferences permanently
  • Market insights + product comparison before recommending
  • Up to 15 iterations — fully uses the tool set to find the best answer
"""

from __future__ import annotations
import json
import os
from typing import Any, Callable, Dict, List, Optional

import groq

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
        self._client: Optional[groq.Groq] = None
        self.executor = ToolExecutor()

    @property
    def client(self) -> groq.Groq:
        if self._client is None:
            self._client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
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
        user_msg = f'Find me: "{query}"'
        if filters.get("max_price"):
            user_msg += f"\nBudget: max ₹{int(filters['max_price']):,}"
        if filters.get("min_rating"):
            user_msg += f"\nMin rating: {filters['min_rating']}"
        if memory_context:
            pref_lines = [
                ln for ln in memory_context.splitlines()
                if any(kw in ln for kw in ("budget", "Budget", "Interest", "preference", "Goal"))
            ]
            if pref_lines:
                user_msg += "\n\nKnown preferences:\n" + "\n".join(pref_lines[:5])

        # Groq uses system message inside the messages list
        messages: List[Dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ]
        final_text: str = ""
        iteration:  int = 0

        tool_use_retries = 0

        while iteration < max_iterations:
            iteration += 1

            if callback:
                callback("thinking", "running", {"iteration": iteration})

            try:
                response = self.client.chat.completions.create(
                    model      = "llama-3.3-70b-versatile",
                    max_tokens = 2048,
                    tools      = TOOL_SCHEMAS,
                    messages   = messages,
                )
            except groq.APIStatusError as exc:
                # Groq/Llama occasionally emits malformed tool-call JSON, surfaced
                # as a 400 'tool_use_failed'. Nudge the model and retry a couple
                # times instead of crashing the whole search.
                is_tool_use_failed = (
                    getattr(exc, "status_code", None) == 400
                    and "tool_use_failed" in str(exc)
                )
                if is_tool_use_failed and tool_use_retries < 2:
                    tool_use_retries += 1
                    iteration -= 1  # don't count this as a real iteration
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your last tool call had invalid arguments and could not be "
                            "processed. Call ONE tool at a time with valid, complete JSON "
                            "arguments matching its schema exactly."
                        ),
                    })
                    if callback:
                        callback("thinking", "retry", {"reason": "tool_use_failed"})
                    continue
                # Out of retries or a different error — stop the loop gracefully
                # so the caller still gets whatever products were found so far.
                if callback:
                    callback("thinking", "error", {"error": str(exc)})
                break

            choice = response.choices[0]
            assistant_msg = choice.message

            # Build a serialisable assistant message dict
            asst_dict: Dict[str, Any] = {
                "role":    "assistant",
                "content": assistant_msg.content or "",
            }
            if assistant_msg.tool_calls:
                asst_dict["tool_calls"] = [
                    {
                        "id":   tc.id,
                        "type": "function",
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_msg.tool_calls
                ]
            messages.append(asst_dict)

            # ── Agent finished ─────────────────────────────────────────────
            if choice.finish_reason == "stop":
                final_text = assistant_msg.content or ""
                if callback:
                    callback("thinking", "complete", {"text": final_text})
                break

            # ── Tool calls ─────────────────────────────────────────────────
            if choice.finish_reason == "tool_calls" and assistant_msg.tool_calls:
                for tc in assistant_msg.tool_calls:
                    tool_name  = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except Exception:
                        tool_input = {}

                    if callback:
                        callback(tool_name, "running", tool_input)

                    result_str = self.executor.execute(tool_name, tool_input)

                    if callback:
                        callback(tool_name, "complete", {"result": result_str, "input": tool_input})

                    # Each tool result is a separate message in OpenAI/Groq format
                    messages.append({
                        "role":         "tool",
                        "tool_call_id": tc.id,
                        "content":      result_str,
                    })
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
