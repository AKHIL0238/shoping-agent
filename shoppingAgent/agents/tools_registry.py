"""
Tools Registry — all tools the ReAct agent can autonomously choose from.

13 tools grouped by capability:
  • Core:        parse_intent, search_products, refine_query
  • Power:       multi_search, find_alternatives
  • Analysis:    rank_and_filter, compare_products, get_market_insights, evaluate_results
  • Web:         web_search, fetch_page_content
  • Output:      generate_recommendation
  • Memory:      save_preference
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

import anthropic

from agents.intent_agent import IntentAgent
from agents.search       import SearchAgent
from agents.compare      import CompareAgent
from agents.recommend    import RecommendAgent


# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas  (Anthropic tool-use format)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS: List[Dict] = [

    # ── Core ─────────────────────────────────────────────────────────────────

    {
        "name": "parse_intent",
        "description": (
            "Parse the user's shopping query to extract clean search keywords, "
            "maximum budget in INR, product preferences, and category. "
            "Call this early so every subsequent tool has structured intent to work from."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user's shopping query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_products",
        "description": (
            "Search Google Shopping via SerpAPI for a SINGLE keyword string. "
            "Prefer multi_search when you want comprehensive coverage. "
            "Use this for targeted follow-up searches after multi_search."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords":    {"type": "string",  "description": "Product search keywords"},
                "max_price":   {"type": "number",  "description": "Max price filter in INR"},
                "max_results": {"type": "integer", "description": "Results to fetch (default 12, max 20)"},
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "refine_query",
        "description": (
            "Generate better search keywords when current results are insufficient. "
            "After calling this, call search_products or multi_search with the new keywords."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "original_query": {"type": "string", "description": "The original user query"},
                "problem":        {"type": "string", "description": "What is wrong with current results"},
                "strategy": {
                    "type": "string",
                    "enum": ["broader", "narrower", "synonyms", "category_specific"],
                    "description": "How to adjust the keywords",
                },
            },
            "required": ["original_query", "problem", "strategy"],
        },
    },

    # ── Power Search ─────────────────────────────────────────────────────────

    {
        "name": "multi_search",
        "description": (
            "Run 2-3 parallel searches with DIFFERENT keyword strategies simultaneously, "
            "then merge and deduplicate all results into a single enriched pool. "
            "This is the MOST POWERFUL search tool — always prefer it over a single search_products call. "
            "Example: to find gaming laptops comprehensively, provide queries like "
            "['gaming laptop RTX under 80000', 'best gaming laptop India 2024', 'high performance portable laptop']."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 varied keyword strings to search simultaneously",
                },
                "max_price": {
                    "type": "number",
                    "description": "Max price filter applied to all sub-searches (INR)",
                },
            },
            "required": ["queries"],
        },
    },
    {
        "name": "find_alternatives",
        "description": (
            "Proactively search for alternative products — budget, premium, or similar variants — "
            "relative to what is already in the pool. New results are MERGED in without replacing "
            "existing products, giving rank_and_filter more options to work with. "
            "Use when the current top result may be out of budget or the user could benefit "
            "from seeing a different price tier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search_for": {
                    "type": "string",
                    "description": "Keywords for the alternatives (e.g. 'budget wireless earbuds under 1500')",
                },
                "direction": {
                    "type": "string",
                    "enum": ["budget", "premium", "similar"],
                    "description": "Whether to look for cheaper, more expensive, or side-grade alternatives",
                },
            },
            "required": ["search_for", "direction"],
        },
    },

    # ── Analysis ─────────────────────────────────────────────────────────────

    {
        "name": "rank_and_filter",
        "description": (
            "Score and rank ALL products currently in the pool by value-for-money (0-100). "
            "Optionally filter by minimum rating or max price. "
            "Always call this after searching and before generating a recommendation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_rating": {
                    "type": "number",
                    "description": "Minimum rating threshold 0-5 (0 = no filter)",
                },
                "max_price": {
                    "type": "number",
                    "description": "Max price in INR (overrides budget from intent if provided)",
                },
                "preference_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords that give a scoring bonus (e.g. ['wireless', 'noise-cancelling'])",
                },
            },
        },
    },
    {
        "name": "compare_products",
        "description": (
            "Perform a detailed AI-powered head-to-head comparison of 2-3 specific products "
            "from the current ranked pool. Returns an analysis covering value, specs, "
            "pros/cons, and a clear winner for different use cases. "
            "Call this when 2+ products are closely matched and the user needs a clear verdict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 product names from current results to compare (partial names OK)",
                },
                "focus": {
                    "type": "string",
                    "description": "What to focus the comparison on (e.g. 'performance', 'value for money', 'battery life')",
                },
            },
            "required": ["product_names"],
        },
    },
    {
        "name": "get_market_insights",
        "description": (
            "Analyze the current product pool to map the price landscape: "
            "identify budget / mid-range / premium segments, best value pick in each segment, "
            "price range, and average. Use this to understand the market before recommending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Product category for context (e.g. 'laptop', 'headphones')",
                }
            },
        },
    },
    {
        "name": "evaluate_results",
        "description": (
            "Evaluate whether the current results adequately answer the user's query. "
            "Returns a quality score and recommended next action. "
            "Use when deciding whether to do more research or proceed to recommendation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_query": {"type": "string", "description": "The original user query"}
            },
            "required": ["user_query"],
        },
    },

    # ── Output ────────────────────────────────────────────────────────────────

    {
        "name": "generate_recommendation",
        "description": (
            "Generate a personalized 2-3 sentence recommendation based on the ranked products "
            "and user's memory context. Call after rank_and_filter. "
            "This is the final tool call before writing FINAL ANSWER."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "What to emphasize (e.g. 'best value', 'top rated', 'budget pick')",
                }
            },
        },
    },

    # ── Web Browsing ─────────────────────────────────────────────────────────

    {
        "name": "web_search",
        "description": (
            "Search the REAL OPEN WEB (not just shopping APIs) for product reviews, "
            "expert comparisons, benchmarks, specifications, YouTube reviews, and user opinions. "
            "Use this to find: 'best gaming laptop 2024 review', '[product] vs [product]', "
            "'[product] problems reddit', '[product] specifications'. "
            "Returns titles, URLs, and snippets of real web pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Web search query (e.g. 'Sony WH-1000XM5 review India 2024')",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5, max 8)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page_content",
        "description": (
            "Fetch and READ the actual content of a web page URL. "
            "Use this after web_search to read a full review article, spec sheet, "
            "or comparison post. Returns cleaned readable text from the page. "
            "Particularly useful for reading expert reviews on sites like NDTV Gadgets, "
            "91mobiles, GSMArena, Digit, or comparison articles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch (from web_search results)",
                },
            },
            "required": ["url"],
        },
    },

    # ── Memory ────────────────────────────────────────────────────────────────

    {
        "name": "save_preference",
        "description": (
            "Permanently save an explicit user preference to long-term memory so it influences "
            "future sessions. Use when the query reveals a strong preference, brand loyalty, "
            "or hard requirement (e.g. preferred_brand=Sony, must_have=backlit_keyboard, "
            "avoid_brand=Apple). The preference persists across app restarts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key":   {"type": "string", "description": "Preference category (e.g. 'preferred_brand', 'must_have_feature', 'avoid')"},
                "value": {"type": "string", "description": "The preference value"},
            },
            "required": ["key", "value"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# ToolExecutor — runs tools, maintains shared agent state within one run
# ─────────────────────────────────────────────────────────────────────────────

class ToolExecutor:
    def __init__(self, memory: Optional[Any] = None) -> None:
        self._intent_agent    = IntentAgent()
        self._search_agent    = SearchAgent()
        self._compare_agent   = CompareAgent()
        self._recommend_agent = RecommendAgent()
        self._memory          = memory
        self.state: Dict[str, Any] = {}

    def reset(self, query: str, memory_context: str = "") -> None:
        self.state = {
            "query":           query,
            "memory_context":  memory_context,
            "intent":          {},
            "raw_products":    [],
            "ranked_products": [],
            "recommendation":  "",
            "search_attempts": [],
            "tool_calls":      [],
        }

    # ── Public dispatch ────────────────────────────────────────────────────

    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        self.state["tool_calls"].append({"tool": tool_name, "input": tool_input})
        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if handler is None:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
            return handler(tool_input)
        except RuntimeError as exc:
            if "SERPAPI_QUOTA_EXCEEDED" in str(exc):
                raise   # let it surface to the UI with a clear message
            return json.dumps({"error": f"{tool_name} failed: {exc}"})
        except Exception as exc:
            return json.dumps({"error": f"{tool_name} failed: {exc}"})

    # ── Core tools ─────────────────────────────────────────────────────────

    def _tool_parse_intent(self, inp: Dict) -> str:
        query  = inp.get("query", self.state["query"])
        intent = self._intent_agent.parse_intent(query)
        self.state["intent"] = intent
        kw = intent.get("keywords", "")
        return json.dumps({
            "keywords":    kw,
            "max_price":   intent.get("max_price"),
            "preferences": intent.get("preferences", ""),
            "category":    intent.get("category", ""),
            "next_step":   f"Call multi_search with 2-3 variations of '{kw}'.",
        })

    def _tool_search_products(self, inp: Dict) -> str:
        keywords    = inp.get("keywords") or self.state["intent"].get("keywords") or self.state["query"]
        max_price   = inp.get("max_price") or self.state["intent"].get("max_price")
        max_results = min(int(inp.get("max_results", 12)), 20)

        self.state["search_attempts"].append(keywords)
        products = self._search_agent.search_products(
            keywords=keywords, max_price=max_price, max_results=max_results,
        )

        # Merge into pool (deduplicate)
        seen = {p["name"][:40].lower() for p in self.state["raw_products"]}
        new  = [p for p in products if p["name"][:40].lower() not in seen]
        self.state["raw_products"].extend(new)

        total = len(self.state["raw_products"])
        sample = [
            {"name": p["name"][:50], "price": p.get("price"), "rating": p.get("rating")}
            for p in products[:5]
        ]
        if total == 0:
            nxt = "No products found. Call refine_query then multi_search with different keywords."
        elif total < 6:
            nxt = f"Only {total} products. Consider refine_query + another search, then call rank_and_filter."
        else:
            nxt = f"{total} products in pool. Call rank_and_filter to score them."
        return json.dumps({
            "found":      len(products),
            "new_added":  len(new),
            "pool_total": total,
            "sample":     sample,
            "next_step":  nxt,
        })

    def _tool_refine_query(self, inp: Dict) -> str:
        original = inp.get("original_query", self.state["query"])
        problem  = inp.get("problem", "insufficient results")
        strategy = inp.get("strategy", "broader")
        tried    = ", ".join(self.state["search_attempts"][-3:])

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = (
            f"Generate better product search keywords.\n"
            f"Original query: '{original}'\nProblem: {problem}\n"
            f"Strategy: {strategy}\nAlready tried: {tried}\n\n"
            "Return ONLY the new keywords as a single line. No explanation."
        )
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=64,
                messages=[{"role": "user", "content": prompt}],
            )
            new_kw = msg.content[0].text.strip().strip('"')
        except Exception:
            words  = original.lower().split()
            new_kw = " ".join(words[:3]) if strategy == "broader" else original + " buy online India"

        return json.dumps({
            "new_keywords": new_kw,
            "next_step":    f"Call multi_search with queries including '{new_kw}'.",
        })

    # ── Power Search tools ─────────────────────────────────────────────────

    def _tool_multi_search(self, inp: Dict) -> str:
        queries   = inp.get("queries", [])[:3]
        max_price = inp.get("max_price") or self.state["intent"].get("max_price")

        if not queries:
            return json.dumps({"error": "Provide at least one query string."})

        seen    = {p["name"][:40].lower() for p in self.state["raw_products"]}
        summary = {}

        for q in queries:
            try:
                products = self._search_agent.search_products(
                    keywords=q, max_price=max_price, max_results=15,
                )
                self.state["search_attempts"].append(q)
                new = [p for p in products if p["name"][:40].lower() not in seen]
                for p in new:
                    seen.add(p["name"][:40].lower())
                self.state["raw_products"].extend(new)
                summary[q] = {"fetched": len(products), "new_added": len(new)}
            except RuntimeError as exc:
                if "SERPAPI_QUOTA_EXCEEDED" in str(exc):
                    raise
                summary[q] = {"error": str(exc)}
            except Exception as exc:
                summary[q] = {"error": str(exc)}

        total = len(self.state["raw_products"])
        if total == 0:
            nxt = "No products found across all queries. Call refine_query then try multi_search with broader terms."
        elif total < 6:
            nxt = f"Only {total} products. Call refine_query then search again, OR call rank_and_filter to proceed."
        else:
            nxt = f"Pool has {total} products. Call rank_and_filter to score them."
        return json.dumps({
            "pool_total": total,
            "per_query":  summary,
            "next_step":  nxt,
        })

    def _tool_find_alternatives(self, inp: Dict) -> str:
        search_for = inp.get("search_for", "")
        direction  = inp.get("direction", "similar")
        if not search_for:
            return json.dumps({"error": "search_for is required."})

        try:
            products = self._search_agent.search_products(keywords=search_for, max_results=10)
            self.state["search_attempts"].append(search_for)
            seen = {p["name"][:40].lower() for p in self.state["raw_products"]}
            new  = [p for p in products if p["name"][:40].lower() not in seen]
            self.state["raw_products"].extend(new)

            sample = [
                {"name": p["name"][:50], "price": p.get("price"), "rating": p.get("rating")}
                for p in new[:4]
            ]
            return json.dumps({
                "direction":   direction,
                "new_found":   len(new),
                "pool_total":  len(self.state["raw_products"]),
                "alternatives": sample,
            })
        except RuntimeError as exc:
            if "SERPAPI_QUOTA_EXCEEDED" in str(exc):
                raise
            return json.dumps({"error": f"Search failed: {exc}"})
        except Exception as exc:
            return json.dumps({"error": f"Search failed: {exc}"})

    # ── Analysis tools ─────────────────────────────────────────────────────

    def _tool_rank_and_filter(self, inp: Dict) -> str:
        products = list(self.state.get("raw_products", []))
        if not products:
            return json.dumps({"error": "No products to rank. Run a search first."})

        min_rating = float(inp.get("min_rating") or 0)
        max_price  = inp.get("max_price") or self.state["intent"].get("max_price")
        pref_kws   = inp.get("preference_keywords") or None

        filtered = [p for p in products if (p.get("rating") or 0) >= min_rating]
        if max_price:
            filtered = [p for p in filtered if not p.get("price") or p["price"] <= max_price]
        if not filtered:
            filtered = products  # loosen if too strict

        ranked = self._compare_agent.rank_products(
            filtered,
            max_price=float(max_price) if max_price else None,
            preference_keywords=pref_kws,
        )
        self.state["ranked_products"] = ranked

        top3 = [
            {
                "rank":   i + 1,
                "name":   p["name"][:50],
                "price":  p.get("price"),
                "rating": p.get("rating"),
                "score":  round(p.get("score", 0), 1),
            }
            for i, p in enumerate(ranked[:3])
        ]
        return json.dumps({
            "total_ranked": len(ranked),
            "top_3":        top3,
            "next_step":    "Products ranked. Call generate_recommendation now.",
        })

    def _tool_compare_products(self, inp: Dict) -> str:
        names = inp.get("product_names", [])[:3]
        focus = inp.get("focus", "overall value")

        pool  = self.state.get("ranked_products") or self.state.get("raw_products", [])
        found = []
        for name in names:
            nl = name.lower()
            for p in pool:
                if nl in p["name"].lower() or p["name"].lower()[:len(nl)] == nl:
                    if p not in found:
                        found.append(p)
                    break

        if len(found) < 2:
            return json.dumps({"error": "Need at least 2 matching products. Check names against pool."})

        items_text = "\n".join(
            f"{i+1}. {p['name']}\n"
            f"   Price: ₹{int(p.get('price') or 0):,} | "
            f"Rating: {p.get('rating') or 'N/A'} | "
            f"Score: {p.get('score', 0):.0f}/100"
            for i, p in enumerate(found)
        )
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = (
            f"Compare these products for an Indian buyer, focusing on {focus}:\n\n"
            f"{items_text}\n\n"
            "In 3-4 sentences: which is better value, who should buy each, and your clear winner. "
            "Be specific with prices. No markdown."
        )
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=220,
                messages=[{"role": "user", "content": prompt}],
            )
            comparison = msg.content[0].text.strip()
        except Exception:
            best = max(found, key=lambda x: x.get("score", 0))
            comparison = (
                f"{best['name'][:40]} leads with score {best.get('score',0):.0f}/100 "
                f"at ₹{int(best.get('price') or 0):,}."
            )
        return json.dumps({"comparison": comparison, "products_compared": len(found)})

    def _tool_get_market_insights(self, inp: Dict) -> str:
        pool = self.state.get("ranked_products") or self.state.get("raw_products", [])
        if not pool:
            return json.dumps({"error": "No products in pool. Run a search first."})

        prices = sorted(float(p.get("price") or 0) for p in pool if p.get("price"))
        if not prices:
            return json.dumps({"error": "No pricing data available."})

        n      = len(prices)
        seg1   = prices[n // 3]
        seg2   = prices[2 * n // 3]

        def _best(subset: List[Dict]) -> Optional[str]:
            if not subset:
                return None
            b = max(subset, key=lambda x: x.get("score", 0) or (x.get("rating") or 0) * 10)
            return f"{b['name'][:40]} — ₹{int(b.get('price') or 0):,}"

        budget_pool  = [p for p in pool if (p.get("price") or 0) <= seg1]
        mid_pool     = [p for p in pool if seg1 < (p.get("price") or 0) <= seg2]
        premium_pool = [p for p in pool if (p.get("price") or 0) > seg2]

        return json.dumps({
            "total_products": n,
            "price_range":   {"min": prices[0], "max": prices[-1],
                               "avg": round(sum(prices) / n), "median": prices[n // 2]},
            "segments": {
                "budget":  {"range": f"up to ₹{int(seg1):,}",
                            "count": len(budget_pool), "best": _best(budget_pool)},
                "mid":     {"range": f"₹{int(seg1):,}–₹{int(seg2):,}",
                            "count": len(mid_pool),    "best": _best(mid_pool)},
                "premium": {"range": f"above ₹{int(seg2):,}",
                            "count": len(premium_pool),"best": _best(premium_pool)},
            },
        })

    def _tool_evaluate_results(self, inp: Dict) -> str:
        ranked   = self.state.get("ranked_products") or self.state.get("raw_products", [])
        count    = len(ranked)
        searches = len(self.state["search_attempts"])
        avg_rat  = sum(p.get("rating") or 0 for p in ranked) / max(count, 1)

        if count == 0:
            return json.dumps({"quality": "poor",       "score": 0,
                               "action": "multi_search", "reason": "No products found"})
        if count < 4 and searches < 3:
            return json.dumps({"quality": "poor",       "score": 25,
                               "action": "multi_search",
                               "reason": f"Only {count} product(s) — run multi_search with broader queries"})
        if count < 8:
            return json.dumps({"quality": "acceptable", "score": 55, "action": "proceed",
                               "reason": f"{count} products, avg rating {avg_rat:.1f}"})
        return json.dumps({"quality": "good",           "score": 88, "action": "proceed",
                           "reason": f"{count} products, avg rating {avg_rat:.1f}"})

    # ── Output tools ───────────────────────────────────────────────────────

    def _tool_generate_recommendation(self, inp: Dict) -> str:
        ranked = self.state.get("ranked_products") or self.state.get("raw_products", [])
        if not ranked:
            return json.dumps({"error": "No products available. Run a search and rank first."})

        rec = self._recommend_agent.recommend(
            query=self.state["query"],
            ranked_products=ranked[:5],
            memory_context=self.state.get("memory_context", ""),
        )
        self.state["recommendation"] = rec
        return json.dumps({
            "recommendation": rec,
            "next_step":      "Recommendation ready. Write your FINAL ANSWER now.",
        })

    # ── Web Browsing tools ─────────────────────────────────────────────────

    def _tool_web_search(self, inp: Dict) -> str:
        from utils.web_fetcher import search_web
        query       = inp.get("query", "")
        num_results = min(int(inp.get("num_results", 5)), 8)
        if not query:
            return json.dumps({"error": "query is required."})
        results = search_web(query, num_results=num_results)
        if not results:
            return json.dumps({"found": 0, "message": "No web results. Check SERPAPI_API_KEY."})
        return json.dumps({"found": len(results), "results": results})

    def _tool_fetch_page_content(self, inp: Dict) -> str:
        from utils.web_fetcher import fetch_url
        url = inp.get("url", "")
        if not url:
            return json.dumps({"error": "url is required."})
        content = fetch_url(url)
        return json.dumps({"url": url, "content": content})

    # ── Memory tools ───────────────────────────────────────────────────────

    def _tool_save_preference(self, inp: Dict) -> str:
        key   = str(inp.get("key",   "")).strip()
        value = str(inp.get("value", "")).strip()
        if not key or not value:
            return json.dumps({"error": "Both key and value are required."})
        if self._memory:
            self._memory.save_preference(key, value)
            return json.dumps({"saved": True, "key": key, "value": value,
                               "message": f"'{key}: {value}' saved permanently to memory."})
        return json.dumps({"saved": False, "message": "Memory module not attached."})

    def _tool_recall_past_searches(self, inp: Dict) -> str:
        topic = inp.get("topic", "")
        if not self._memory or not self._memory.history:
            return json.dumps({
                "context":   "No history yet — this is a fresh session.",
                "next_step": "Call parse_intent to extract keywords from the query.",
            })
        similar = self._memory.get_similar_searches(topic)
        # Return ONLY personalisation signals — never actual product results.
        # Actual products must always come from multi_search / search_products.
        past_queries = [rec.query for rec in similar] if similar else []
        prefs = {k: v for k, v in self._memory.preferences.items()
                 if k in ("typical_budget", "keywords", "preferred_brand",
                          "must_have_feature", "avoid")}
        return json.dumps({
            "past_queries_on_topic": past_queries,
            "preferences":           prefs,
            "note":                  "This is personalisation context only. "
                                     "You still MUST call multi_search to get fresh products.",
            "next_step":             "Call parse_intent, then multi_search for fresh results.",
        })
