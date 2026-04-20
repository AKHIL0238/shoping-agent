"""
ShopMind AI — True Agentic AI Shopping Assistant
UI: Streamlit + glassmorphism dark theme
Architecture: ReAct loop — Claude autonomously selects tools, replans on failure,
              and loops until it produces a satisfactory answer.
"""

# ── imports ────────────────────────────────────────────────────────────────
import streamlit as st
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Page config must be the FIRST Streamlit call
st.set_page_config(
    page_title="ShopMind AI",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "ShopMind AI — Powered by Claude & SerpAPI"},
)

import json
import uuid
from typing import Any

import streamlit.components.v1 as components

from agents.memory       import MemoryModule
from utils.cart          import Cart
from utils.ui_components import get_css, render_product_card_html
from utils.formatters    import format_price, format_rating, time_ago


# ── CSS injection ──────────────────────────────────────────────────────────
st.markdown(get_css(), unsafe_allow_html=True)


# ── Session-state bootstrapping ────────────────────────────────────────────
_DEFAULTS = {
    "page":              "Home",
    "wishlist":          [],
    "search_history":    [],
    "last_results":      None,
    "memory":            None,
    "cart":              None,
    "orders":            [],
    "cart_step":         "cart",
    "payment_done":      False,
    "payment_id":        "",
    "ship_info":         {},
    "last_order":        {},
    "show_payment":      False,
    "ai_order_review":   "",
    "search_query":      "",
    "auto_search":       False,
    "preferences":       {"max_results": 12, "enable_reflection": True},
    "pipeline_status":   {},
    "filters":           {"max_price": None, "min_rating": 3.0, "max_results": 12},
    "price_drop_alerts": [],   # list of drop dicts from PriceMonitor.check_all()
    "last_price_check":  0,    # unix timestamp of last auto price check
}


def _init() -> None:
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state.memory is None:
        st.session_state.memory = MemoryModule()
    if st.session_state.cart is None:
        st.session_state.cart = Cart()


_init()


# ── Proactive price monitoring — runs once per hour automatically ──────────

def _auto_price_check() -> None:
    from utils.price_monitor import PriceMonitor
    from agents.search       import SearchAgent
    monitor = PriceMonitor()
    if not monitor.watches:
        st.session_state.last_price_check = time.time()
        return
    sa    = SearchAgent()
    drops = monitor.check_all(sa)
    if drops:
        st.session_state.price_drop_alerts = drops
        from utils.email_sender import send_price_alert_email
        for drop in drops:
            if drop.get("alert_email"):
                send_price_alert_email(drop)
    st.session_state.last_price_check = time.time()


# Run auto-check if more than 1 hour since last check
if (time.time() - st.session_state.get("last_price_check", 0)) > 3600:
    _auto_price_check()


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

def render_sidebar() -> None:
    with st.sidebar:
        # Brand
        st.markdown(
            """
            <div style="text-align:center;padding:20px 0 12px;">
              <div style="font-size:2.6rem;">🛍️</div>
              <div style="font-size:1.25rem;font-weight:800;
                          background:linear-gradient(135deg,#7c6bf3,#b06ef3);
                          -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                          background-clip:text;">ShopMind AI</div>
              <div style="font-size:0.72rem;color:rgba(255,255,255,0.35);margin-top:4px;">
                Powered by Claude
              </div>
            </div>
            <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:8px 0 14px;">
            """,
            unsafe_allow_html=True,
        )

        # Navigation
        st.markdown(
            "<div style='font-size:0.72rem;font-weight:700;color:rgba(255,255,255,0.35);"
            "text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>Navigation</div>",
            unsafe_allow_html=True,
        )
        alert_count = len(st.session_state.get("price_drop_alerts", []))
        alert_label = f"🔔 Alerts ({alert_count})" if alert_count else "🔔 Alerts"
        nav_options = ["🏠 Home", "🔍 Search", "🛒 Cart", "📦 Orders",
                       "⭐ Recommendations", "📜 History",
                       alert_label, "🎯 Goals", "⚙️ Settings"]
        _page_map   = {o: o.split(" ", 1)[1].split(" (")[0] for o in nav_options}

        # Apply any pending programmatic navigation BEFORE the radio widget is
        # created.  Page functions cannot write nav_radio directly (widget
        # already rendered), so they write _nav_target instead.
        if st.session_state.get("_nav_target"):
            st.session_state.nav_radio = st.session_state._nav_target
            del st.session_state["_nav_target"]

        if "nav_radio" not in st.session_state:
            st.session_state.nav_radio = "🏠 Home"

        selected = st.radio(
            "nav", nav_options,
            label_visibility="collapsed", key="nav_radio"
        )
        st.session_state.page = _page_map[selected]

        st.markdown("---")

        # Filters
        st.markdown(
            "<div style='font-size:0.72rem;font-weight:700;color:rgba(255,255,255,0.35);"
            "text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;'>🎛️ Filters</div>",
            unsafe_allow_html=True,
        )
        max_price  = st.slider("Max Price (₹)", 0, 150_000, 50_000, step=1_000, key="filter_price")
        min_rating = st.slider("Min Rating ⭐", 0.0, 5.0, 3.0, step=0.5, key="filter_rating")
        max_res    = st.slider("Max Results", 5, 20, 12, step=1, key="filter_max_results")
        st.session_state.filters = {
            "max_price":   max_price if max_price < 150_000 else None,
            "min_rating":  min_rating,
            "max_results": max_res,
        }

        st.markdown("---")

        # Cart mini-summary
        cart = st.session_state.cart
        cart_count = cart.count if cart else 0
        badge_html = f'<span class="cart-badge">{cart_count}</span>' if cart_count else ""
        st.markdown(
            f"<div style='font-size:0.72rem;font-weight:700;color:rgba(255,255,255,0.35);"
            f"text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>"
            f"🛒 Cart{badge_html}</div>",
            unsafe_allow_html=True,
        )
        if cart and cart.count:
            for item in cart.items[-3:]:
                st.markdown(
                    f"<div style='font-size:0.78rem;color:rgba(255,255,255,0.55);"
                    f"padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04);'>"
                    f"• {item.name[:28]}… × {item.quantity}</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"<div style='font-size:0.82rem;font-weight:700;color:#a09df5;margin-top:6px;'>"
                f"Total: {format_price(cart.total)}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:0.78rem;color:rgba(255,255,255,0.3);'>Cart is empty.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Agent toggle
        st.markdown(
            "<div style='font-size:0.72rem;font-weight:700;color:rgba(255,255,255,0.35);"
            "text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;'>⚙️ Agent</div>",
            unsafe_allow_html=True,
        )
        reflection_on = st.toggle("✨ Reflection layer", value=True, key="pref_reflection")
        st.session_state.preferences["enable_reflection"] = reflection_on

        st.markdown(
            "<div style='text-align:center;padding:20px 0 8px;"
            "color:rgba(255,255,255,0.22);font-size:0.72rem;'>Claude · SerpAPI · LangGraph</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_home() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>Find Your Perfect Product</h1>
          <p>AI-powered assistant that plans, searches, compares and recommends — step by step.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 4, 1])
    with mid:
        q  = st.text_input(
            "hq", placeholder="🔍 Try: best gaming laptop under 80000",
            label_visibility="collapsed", key="home_search_input"
        )
        go = st.button("Search with AI 🚀", key="home_go", use_container_width=True)

    if go and q:
        st.session_state._nav_target = "🔍 Search"
        st.session_state.search_query = q
        st.session_state.search_main_input = q
        st.session_state.auto_search = True
        st.rerun()

    st.markdown("---")

    # Feature cards
    features = [
        ("🧠", "AI Planning",   "Query decomposition & multi-step reasoning"),
        ("🔍", "Deep Search",   "Real-time product search via SerpAPI"),
        ("⚖️",  "Smart Ranking", "Value-for-money scoring algorithm"),
        ("💡", "Personalised", "Memory-backed, preference-aware results"),
    ]
    cols = st.columns(4)
    for col, (icon, title, desc) in zip(cols, features):
        with col:
            st.markdown(
                f"""<div class="glass-card" style="text-align:center;padding:28px 14px;">
                  <div style="font-size:1.9rem;margin-bottom:10px;">{icon}</div>
                  <div style="font-weight:700;font-size:0.93rem;margin-bottom:7px;">{title}</div>
                  <div style="font-size:0.78rem;color:rgba(255,255,255,0.48);line-height:1.55;">{desc}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.8rem;font-weight:700;color:rgba(255,255,255,0.35);"
        "text-transform:uppercase;letter-spacing:1.2px;margin-bottom:10px;'>✨ Quick searches</div>",
        unsafe_allow_html=True,
    )
    suggestions = [
        "best gaming laptop under 80000",
        "wireless earbuds under 2000",
        "running shoes for men under 3000",
        "smart tv 43 inch under 30000",
        "ergonomic office chair",
    ]
    s_cols = st.columns(len(suggestions))
    for col, sug in zip(s_cols, suggestions):
        with col:
            if st.button(f"💡 {sug[:26]}", key=f"sug_{sug}", use_container_width=True):
                st.session_state._nav_target = "🔍 Search"
                st.session_state.search_query = sug
                st.session_state.search_main_input = sug
                st.session_state.auto_search = True
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# SEARCH PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_search() -> None:
    st.markdown("### 🔍 Product Search")

    q_col, btn_col = st.columns([5, 1])
    with q_col:
        query = st.text_input(
            "sq",
            placeholder="What are you looking for?",
            label_visibility="collapsed", key="search_main_input"
        )
    with btn_col:
        search_btn = st.button("Search 🚀", key="main_search_btn", use_container_width=True)

    # Quick suggestions
    if not query:
        suggestions = [
            "best laptop under 60000",
            "noise cancelling headphones",
            "smartphone under 15000",
            "smartwatch under 5000",
        ]
        st.markdown(
            "<div style='color:rgba(255,255,255,0.35);font-size:0.82rem;margin:4px 0 8px;'>Try:</div>",
            unsafe_allow_html=True,
        )
        sc = st.columns(len(suggestions))
        for col, sug in zip(sc, suggestions):
            with col:
                if st.button(f"💡 {sug[:24]}", key=f"ssug_{sug}", use_container_width=True):
                    st.session_state.search_main_input = sug
                    st.session_state.search_query = sug
                    st.session_state.auto_search = True
                    st.rerun()

    trigger = search_btn or st.session_state.get("auto_search", False)
    if trigger and query:
        st.session_state.auto_search = False
        st.session_state.search_query = query
        _execute_search(query)
    elif (
        st.session_state.last_results
        and st.session_state.last_results.get("query") == st.session_state.search_query
        and st.session_state.last_results.get("ranked_products")
    ):
        _display_results(st.session_state.last_results)


# ─── ReAct search executor ────────────────────────────────────────────────

# Map tool names → display info
_TOOL_META = {
    "thinking":               ("🧠", "Agent Reasoning"),
    "parse_intent":           ("🎯", "Parse Intent"),
    "search_products":        ("🔍", "Search Products"),
    "multi_search":           ("🔎", "Multi-Search"),
    "refine_query":           ("✏️",  "Refine Query"),
    "find_alternatives":      ("🔄", "Find Alternatives"),
    "rank_and_filter":        ("⚖️",  "Rank & Filter"),
    "compare_products":       ("⚔️",  "Compare Products"),
    "get_market_insights":    ("📈", "Market Insights"),
    "evaluate_results":       ("📊", "Evaluate Results"),
    "generate_recommendation":("💡", "Generate Recommendation"),
    "save_preference":        ("💾", "Save Preference"),
    "web_search":             ("🌐", "Web Search"),
    "fetch_page_content":     ("📄", "Read Web Page"),
}


def _execute_search(query: str) -> None:
    from agents.react_agent import ReActAgent
    from utils.cache import _search_cache
    _search_cache.clear()          # always hit SerpAPI fresh

    filters = st.session_state.get("filters", {})
    mem_ctx = st.session_state.memory.get_context()

    # ── Human-in-the-loop budget check ────────────────────────────────────
    prev_budget = st.session_state.memory.preferences.get("typical_budget")
    max_p = filters.get("max_price")
    if prev_budget and max_p and max_p > prev_budget * 2.5:
        st.markdown(
            f"""<div class="confirm-box">
              <div class="confirm-box-hdr">⚠️ Budget Check</div>
              <div class="confirm-box-body">
                Your typical budget is ~{format_price(prev_budget)}, but the current
                filter is set to {format_price(max_p)}. Continue?
              </div>
            </div>""",
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 5])
        with c1:
            if not st.button("✅ Continue", key="hitl_yes"):
                return
        with c2:
            if st.button("✏️ Adjust", key="hitl_adj"):
                return

    # ── Agent trace UI ─────────────────────────────────────────────────────
    st.markdown(
        """<div style="font-size:0.78rem;font-weight:700;color:rgba(255,255,255,0.35);
           text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px;">
           🤖 Agent Trace</div>""",
        unsafe_allow_html=True,
    )
    trace_ph   = st.empty()   # live trace log
    status_ph  = st.empty()   # current action status line

    trace_entries: list[dict] = []   # {icon, label, detail, status}

    def _render_trace() -> None:
        rows = []
        for e in trace_entries[-10:]:
            icon   = e["icon"]
            label  = e["label"]
            detail = e.get("detail", "")
            s      = e["status"]   # running | complete | error
            color  = {"running": "#a09df5", "complete": "#4caf87", "error": "#f05050"}.get(s, "#888")
            dot    = {"running": "●", "complete": "✓", "error": "✗"}.get(s, "•")
            rows.append(
                f'<div style="padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
                f'<span style="color:{color};font-weight:700;">{dot} {icon} {label}</span>'
                + (f'<span style="color:rgba(255,255,255,0.38);font-size:0.78rem;"> — {detail}</span>' if detail else "")
                + "</div>"
            )
        html = (
            '<div style="background:rgba(0,0,0,0.28);border:1px solid rgba(255,255,255,0.07);'
            'border-radius:10px;padding:12px 16px;font-size:0.83rem;font-family:monospace;'
            'max-height:260px;overflow-y:auto;">'
            + "".join(rows)
            + "</div>"
        )
        trace_ph.markdown(html, unsafe_allow_html=True)

    def callback(tool: str, status: str, data: Any) -> None:
        icon, label = _TOOL_META.get(tool, ("🔧", tool))

        # Build a one-line detail from the data
        detail = ""
        if status == "running" and isinstance(data, dict):
            if "keywords"  in data: detail = f"keywords: \"{data['keywords']}\""
            elif "query"   in data: detail = f"\"{data['query']}\""
            elif "iteration" in data: detail = f"iteration {data['iteration']}"
            elif "problem" in data: detail = data["problem"]
        elif status == "complete" and isinstance(data, dict):
            res = data.get("result", "")
            try:
                r = json.loads(res)
                if "pool_total"      in r: detail = f"{r['pool_total']} products in pool"
                elif "count"         in r: detail = f"{r['count']} products found"
                elif "total_ranked"  in r: detail = f"{r['total_ranked']} products ranked"
                elif "new_keywords"  in r: detail = f"new keywords: \"{r['new_keywords']}\""
                elif "recommendation" in r: detail = "recommendation ready ✓"
                elif "quality"       in r: detail = f"quality: {r['quality']} — {r.get('action','')}"
                elif "keywords"      in r: detail = f"keywords: \"{r.get('keywords','')}\""
                elif "comparison"    in r: detail = "comparison complete ✓"
                elif "segments"      in r: detail = f"market mapped — {r.get('total_products',0)} products"
                elif "found"         in r and "past_searches" in r: detail = f"{r['found']} past searches recalled"
                elif "saved"         in r: detail = f"preference saved: {r.get('key','')}"
                elif "new_found"     in r: detail = f"{r['new_found']} alternatives added"
            except Exception:
                pass

        # Find existing entry for this tool or add new one
        existing = next((e for e in trace_entries if e["tool"] == tool and e["status"] == "running"), None)
        if existing and status != "running":
            existing["status"] = status
            if detail:
                existing["detail"] = detail
        else:
            trace_entries.append({"tool": tool, "icon": icon, "label": label,
                                   "detail": detail, "status": status})

        _render_trace()

        # Brief status line below trace
        if status == "running":
            status_ph.markdown(
                f'<div style="color:rgba(255,255,255,0.45);font-size:0.82rem;margin-top:4px;">'
                f'{icon} {label}…</div>',
                unsafe_allow_html=True,
            )

    # ── Run the ReAct agent ────────────────────────────────────────────────
    agent = ReActAgent()
    try:
        result = agent.run(
            query          = query,
            memory_context = mem_ctx,
            callback       = callback,
            max_iterations = 15,
            filters        = filters,
            memory         = st.session_state.memory,
        )
    except Exception as exc:
        trace_ph.empty()
        status_ph.empty()
        err_type = type(exc).__name__
        if "APIConnectionError" in err_type or "Connection" in str(exc):
            msg = (
                "**🌐 Connection Error** — Could not reach the Anthropic API.\n\n"
                "**Possible causes:**\n"
                "- No internet connection\n"
                "- Firewall or proxy blocking `api.anthropic.com`\n"
                "- VPN interfering with outbound HTTPS\n\n"
                "**Fix:** Check your network, then try again."
            )
        elif "AuthenticationError" in err_type or "401" in str(exc):
            msg = (
                "**🔑 Authentication Error** — Your `ANTHROPIC_API_KEY` is missing or invalid.\n\n"
                "Check your `.env` file and restart the app."
            )
        elif "SERPAPI_QUOTA_EXCEEDED" in str(exc):
            msg = (
                "**🔍 SerpAPI Quota Exhausted** — Your SerpAPI account has run out of free searches.\n\n"
                "**Fix options:**\n"
                "- **Get a new free key:** Sign up at [serpapi.com](https://serpapi.com) with a different email "
                "(100 free searches/month), update `SERPAPI_API_KEY` in `.env`, then restart the app.\n"
                "- **Upgrade:** SerpAPI paid plans start at $50/month for 5,000 searches.\n"
                "- **Wait:** Free quota resets on your billing date."
            )
        elif "RateLimitError" in err_type or "429" in str(exc):
            msg = "**⏳ Rate Limit** — Too many requests. Wait a moment and try again."
        else:
            msg = f"**❌ Agent Error:** `{exc}`"
        st.markdown(
            f'<div class="notif notif-err">{msg}</div>',
            unsafe_allow_html=True,
        )
        return

    # Client-side filters (belt-and-suspenders)
    ranked = result.get("ranked_products", [])
    if filters.get("min_rating"):
        ranked = [p for p in ranked if (p.get("rating") or 0) >= filters["min_rating"]]
    if filters.get("max_price"):
        ranked = [p for p in ranked if not p.get("price") or p["price"] <= filters["max_price"]]
    result["ranked_products"] = ranked

    # Tag products that satisfy an active goal
    st.session_state.memory.match_goals(ranked)

    # Persist
    st.session_state.last_results = result
    st.session_state.memory.add_search(
        query          = query,
        intent         = result.get("intent", {}),
        results        = ranked,
        recommendation = result.get("recommendation", ""),
    )
    _push_history(query, result)

    time.sleep(0.4)
    status_ph.empty()

    # Show agent trace summary as a collapsed expander
    tool_calls    = result.get("tool_calls", [])
    search_hist   = result.get("search_history", [])
    iterations    = result.get("iterations", 0)
    _render_agent_summary(trace_ph, tool_calls, search_hist, iterations)

    _display_results(result)


def _render_agent_summary(placeholder, tool_calls: list, search_history: list, iterations: int) -> None:
    """Replace the live trace with a compact post-run summary."""
    tools_used = list(dict.fromkeys(t["tool"] for t in tool_calls))   # dedup, preserve order
    searched   = " → ".join(f'"{k}"' for k in search_history) if search_history else "—"
    pills = "".join(
        f'<span style="background:rgba(124,107,243,0.18);border:1px solid rgba(124,107,243,0.3);'
        f'border-radius:20px;padding:2px 10px;font-size:0.72rem;margin:2px;display:inline-block;">'
        f'{_TOOL_META.get(t,("🔧",t))[0]} {_TOOL_META.get(t,("🔧",t))[1]}</span>'
        for t in tools_used
    )
    html = (
        f'<div style="background:rgba(124,107,243,0.06);border:1px solid rgba(124,107,243,0.18);'
        f'border-radius:10px;padding:12px 16px;font-size:0.8rem;margin-bottom:12px;">'
        f'<div style="font-weight:700;color:rgba(255,255,255,0.55);margin-bottom:8px;">'
        f'🤖 Agent completed in {iterations} iteration(s)</div>'
        f'<div style="margin-bottom:6px;">{pills}</div>'
        f'<div style="color:rgba(255,255,255,0.35);font-size:0.75rem;">Searched: {searched}</div>'
        f'</div>'
    )
    placeholder.markdown(html, unsafe_allow_html=True)


def _push_history(query: str, result: dict) -> None:
    entry   = {"query": query, "count": len(result.get("ranked_products", [])), "timestamp": time.time()}
    history = [h for h in st.session_state.search_history if h["query"] != query]
    history.insert(0, entry)
    st.session_state.search_history = history[:20]


# ─── results display ──────────────────────────────────────────────────────

def _display_results(result: dict) -> None:
    products       = result.get("ranked_products", [])
    recommendation = result.get("recommendation", "")
    query          = result.get("query", "")
    intent         = result.get("intent", {})

    if result.get("error") and not products:
        st.markdown(
            f'<div class="notif notif-err">❌  {result["error"]}</div>',
            unsafe_allow_html=True,
        )
        return

    if not products:
        st.markdown(
            """<div class="empty-state">
              <div class="empty-icon">🔍</div>
              <div class="empty-title">No products found</div>
              <div class="empty-desc">Try different keywords or relax your filters.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # Metrics
    prices  = [p["price"]  for p in products if isinstance(p.get("price"),  (int, float)) and p["price"]  > 0]
    ratings = [p["rating"] for p in products if isinstance(p.get("rating"), (int, float)) and p["rating"] > 0]

    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Products Found", len(products))
    with m2: st.metric("Best Price",     format_price(min(prices))              if prices  else "N/A")
    with m3: st.metric("Avg Price",      format_price(sum(prices)/len(prices))  if prices  else "N/A")
    with m4: st.metric("Avg Rating",     f"{sum(ratings)/len(ratings):.1f} ⭐"   if ratings else "N/A")

    # Intent keyword tags
    kws = intent.get("keywords", "")
    if kws:
        tokens = kws.split() if isinstance(kws, str) else kws
        tags   = " ".join(f"<span class='tag'>{t}</span>" for t in tokens[:8])
        st.markdown(f"<div style='margin:12px 0;'>{tags}</div>", unsafe_allow_html=True)

    # AI Recommendation
    if recommendation:
        st.markdown(
            f"""<div class="rec-card">
              <div class="rec-header">
                <div class="rec-icon">🤖</div>
                <div class="rec-title">AI Recommendation</div>
              </div>
              <div class="rec-body">{recommendation}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="sec-div"><span class="sec-title">Search Results</span></div>',
        unsafe_allow_html=True,
    )

    # Sort controls
    sort_col, _ = st.columns([2, 4])
    with sort_col:
        sort_by = st.selectbox(
            "Sort", ["Relevance", "Price: Low → High", "Price: High → Low", "Rating"],
            label_visibility="collapsed", key="sort_sel"
        )

    if sort_by == "Price: Low → High":
        products = sorted(products, key=lambda p: p.get("price") or 999_999)
    elif sort_by == "Price: High → Low":
        products = sorted(products, key=lambda p: p.get("price") or 0, reverse=True)
    elif sort_by == "Rating":
        products = sorted(products, key=lambda p: p.get("rating") or 0, reverse=True)

    # Product grid
    _render_grid(products[:9], offset=0)
    if len(products) > 9:
        with st.expander(f"Show {len(products) - 9} more products"):
            _render_grid(products[9:], offset=9)

    # CSV download
    csv_rows = ["Name,Price,Rating,Link"] + [
        f'"{p.get("name","")}",{p.get("price","N/A")},{p.get("rating","N/A")},{p.get("link","")}'
        for p in products
    ]
    st.download_button(
        "⬇️  Download Results (CSV)",
        data="\n".join(csv_rows),
        file_name=f"shopmind_{query[:20].replace(' ','_')}.csv",
        mime="text/csv",
        key="dl_csv",
    )


def _render_grid(products: list, offset: int = 0) -> None:
    cols = st.columns(3)
    for i, product in enumerate(products):
        with cols[i % 3]:
            _render_card(product, i + offset)


def _render_card(product: dict, rank: int) -> None:
    st.markdown(render_product_card_html(product, rank), unsafe_allow_html=True)
    name = product.get("name", "")
    cart = st.session_state.cart

    # ── Row 1: primary purchase actions ───────────────────────────────────
    p1, p2 = st.columns(2)
    with p1:
        in_cart = cart.is_in_cart(name)
        label   = f"🛒 In Cart ({cart.get_qty(name)})" if in_cart else "🛒 Add to Cart"
        if st.button(label, key=f"cart_{rank}_{name[:14]}", use_container_width=True):
            cart.add(product)
            st.rerun()
    with p2:
        if st.button("⚡ Buy Now", key=f"buy_{rank}_{name[:14]}", use_container_width=True,
                     help="Add to cart and go straight to checkout"):
            cart.add(product)
            st.session_state.cart_step      = "checkout"
            st.session_state.show_payment   = False
            st.session_state.ai_order_review = ""
            st.session_state._nav_target    = "🛒 Cart"
            st.rerun()

    # ── Row 2: Watch Price + Quick View ───────────────────────────────────
    s1, s2 = st.columns(2)
    with s1:
        in_wl = any(w.get("name") == name for w in st.session_state.wishlist)
        if st.button(
            "❤️ Saved" if in_wl else "🤍 Wishlist",
            key=f"wl_{rank}_{name[:14]}", use_container_width=True,
        ):
            if in_wl:
                st.session_state.wishlist = [
                    w for w in st.session_state.wishlist if w.get("name") != name
                ]
            else:
                st.session_state.wishlist.append({
                    "name":   name,
                    "price":  product.get("price"),
                    "image":  product.get("image", ""),
                    "rating": product.get("rating"),
                    "source": product.get("source", ""),
                    "link":   product.get("link", ""),
                })
            st.rerun()
    with s2:
        if st.button("👁️ Quick View", key=f"view_{rank}_{name[:14]}", use_container_width=True):
            st.session_state[f"qv_{rank}"] = not st.session_state.get(f"qv_{rank}", False)
            st.rerun()

    # ── Row 3: Watch Price ─────────────────────────────────────────────────
    from utils.price_monitor import PriceMonitor
    monitor    = PriceMonitor()
    is_watch   = monitor.is_watching(name)
    watch_lbl  = "🔕 Unwatch" if is_watch else "🔔 Watch Price"
    if st.button(watch_lbl, key=f"watch_{rank}_{name[:14]}", use_container_width=True):
        if is_watch:
            monitor.unwatch(name)
            st.rerun()
        else:
            st.session_state[f"watch_form_{rank}"] = True
            st.rerun()

    if st.session_state.get(f"watch_form_{rank}"):
        with st.container():
            mem_email = st.session_state.memory.preferences.get("alert_email", "")
            ord_email = (st.session_state.get("ship_info") or {}).get("email", "")
            default_email = mem_email or ord_email
            cur_price = int(product.get("price") or 0)
            ae  = st.text_input("Alert email", value=default_email,
                                 placeholder="you@email.com", key=f"ae_{rank}")
            tgt = st.number_input("Alert when price drops to (₹)",
                                   min_value=1, max_value=cur_price,
                                   value=max(1, int(cur_price * 0.9)),
                                   key=f"tgt_{rank}")
            wc1, wc2 = st.columns(2)
            with wc1:
                if st.button("Set Alert ✅", key=f"set_w_{rank}", use_container_width=True):
                    if ae:
                        st.session_state.memory.save_preference("alert_email", ae)
                    monitor.watch(product, float(tgt), ae)
                    del st.session_state[f"watch_form_{rank}"]
                    st.markdown(
                        '<div class="notif notif-ok">🔔 Price alert set!</div>',
                        unsafe_allow_html=True,
                    )
                    st.rerun()
            with wc2:
                if st.button("Cancel ✕", key=f"canc_w_{rank}", use_container_width=True):
                    del st.session_state[f"watch_form_{rank}"]
                    st.rerun()

    # ── Goal match badge ───────────────────────────────────────────────────
    if product.get("goal_match"):
        st.markdown(
            f'<div class="notif notif-ok" style="padding:5px 10px;font-size:0.78rem;margin-top:4px;">'
            f'🎯 Matches your goal: <b>{product["goal_match"][:50]}</b></div>',
            unsafe_allow_html=True,
        )

    # ── Quick view expander ────────────────────────────────────────────────
    if st.session_state.get(f"qv_{rank}", False):
        with st.expander("Quick View", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                if product.get("image"):
                    st.image(product["image"], use_container_width=True)
            with c2:
                st.markdown(f"**{name}**")
                if product.get("source"):
                    st.markdown(f"🏪 **{product['source']}**")
                st.markdown(f"Price: {format_price(product.get('price'))}")
                st.markdown(f"Rating: {format_rating(product.get('rating'))}")
                if product.get("link"):
                    st.link_button("🔗 View Full Listing", product["link"])


# ═══════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_recommendations() -> None:
    st.markdown("### ⭐ Personalized Recommendations")

    last = st.session_state.last_results
    if not last or not last.get("ranked_products"):
        st.markdown(
            """<div class="empty-state">
              <div class="empty-icon">⭐</div>
              <div class="empty-title">No history yet</div>
              <div class="empty-desc">Run a search first to get personalized recommendations.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div class="notif notif-info">Based on your search: <b>{last.get("query","")}</b></div>',
        unsafe_allow_html=True,
    )

    if last.get("recommendation"):
        st.markdown(
            f"""<div class="rec-card">
              <div class="rec-header"><div class="rec-icon">🤖</div>
                <div class="rec-title">AI Summary</div></div>
              <div class="rec-body">{last['recommendation']}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("**Top 3 Products**")
    for i, p in enumerate(last["ranked_products"][:3]):
        with st.expander(f"#{i+1}  {p.get('name','?')[:55]}", expanded=(i == 0)):
            c1, c2 = st.columns([1, 2])
            with c1:
                img = p.get("image", "")
                if img:
                    st.image(img, use_container_width=True)
                else:
                    st.markdown(
                        '<div style="text-align:center;font-size:4rem;padding:20px">🛍️</div>',
                        unsafe_allow_html=True,
                    )
            with c2:
                st.markdown(f"**Price:**  {format_price(p.get('price'))}")
                st.markdown(f"**Rating:** {format_rating(p.get('rating'))}")
                st.markdown(f"**Score:**  {p.get('score', 0):.1f} / 100")
                if p.get("link"):
                    st.link_button("View Product 🔗", p["link"])

    # Preference profile
    prefs = st.session_state.memory.preferences
    if prefs:
        st.markdown("---")
        st.markdown("**Your Preference Profile**")
        pref_html = ""
        if prefs.get("typical_budget"):
            pref_html += f"<span class='tag'>💰 Budget ~{format_price(prefs['typical_budget'])}</span>"
        for kw in (prefs.get("keywords") or [])[:8]:
            pref_html += f"<span class='tag'>{kw}</span>"
        if pref_html:
            st.markdown(pref_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# HISTORY PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_history() -> None:
    st.markdown("### 📜 Search History")

    if not st.session_state.search_history:
        st.markdown(
            """<div class="empty-state">
              <div class="empty-icon">📜</div>
              <div class="empty-title">No searches yet</div>
              <div class="empty-desc">Your search history will appear here.</div>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        _, clr_col = st.columns([4, 1])
        with clr_col:
            if st.button("🗑️ Clear", key="clr_history"):
                st.session_state.search_history = []
                st.session_state.memory.clear()
                st.rerun()

        for i, entry in enumerate(st.session_state.search_history):
            hcol, rcol = st.columns([4, 1])
            with hcol:
                st.markdown(
                    f"""<div class="history-item">
                      <div class="h-query">🔍  {entry['query']}</div>
                      <div class="h-meta">{time_ago(entry.get('timestamp', 0))} · {entry.get('count', 0)} products</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with rcol:
                if st.button("↩️", key=f"redo_{i}", help="Re-run this search"):
                    st.session_state._nav_target = "🔍 Search"
                    st.session_state.search_query = entry["query"]
                    st.session_state.search_main_input = entry["query"]
                    st.session_state.auto_search = True
                    st.rerun()

    # Wishlist section
    st.markdown("---")
    st.markdown(f"### ❤️ Wishlist ({len(st.session_state.wishlist)} items)")

    if st.session_state.wishlist:
        for i, item in enumerate(st.session_state.wishlist):
            wc1, wc2, wc3 = st.columns([3, 1, 1])
            with wc1:
                st.markdown(
                    f"**{item['name'][:50]}** — {format_price(item.get('price'))} "
                    f"({format_rating(item.get('rating'))})"
                )
            with wc2:
                if item.get("link"):
                    st.link_button("View 🔗", item["link"])
            with wc3:
                if st.button("🗑️", key=f"rm_wl_{i}"):
                    st.session_state.wishlist.pop(i)
                    st.rerun()
    else:
        st.markdown(
            "<div style='color:rgba(255,255,255,0.35);'>No saved items.</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_settings() -> None:
    st.markdown("### ⚙️ Settings")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### API Status")

        def _notif(label: str, env: str) -> None:
            val = os.getenv(env, "")
            cls = "notif-ok" if val else "notif-err"
            ico = "✅" if val else "❌"
            masked = f"{val[:8]}…" if val else "Not configured"
            st.markdown(
                f'<div class="notif {cls}">{ico} {label} — {masked}</div>',
                unsafe_allow_html=True,
            )

        _notif("Claude API", "ANTHROPIC_API_KEY")
        _notif("SerpAPI",    "SERPAPI_API_KEY")

    with c2:
        st.markdown("#### Agent Config")
        refl = st.toggle(
            "✨ Reflection layer",
            value=st.session_state.preferences.get("enable_reflection", True),
            key="s_refl",
        )
        st.session_state.preferences["enable_reflection"] = refl

        if st.button("🗑️ Clear Memory & History", key="clr_all"):
            st.session_state.search_history = []
            st.session_state.last_results   = None
            st.session_state.memory.clear()
            st.markdown(
                '<div class="notif notif-ok">✅ Memory cleared.</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown("#### Agent Pipeline")
    for icon, name, model, desc in [
        ("📋", "Planner",     "Claude Haiku",   "Decomposes query into steps"),
        ("🧠", "Intent",      "Claude Haiku",   "Extracts keywords, budget, preferences"),
        ("🔍", "Search",      "SerpAPI",        "Google Shopping — up to 20 results"),
        ("⚖️",  "Compare",     "Python scoring", "Value-for-money ranking"),
        ("💡", "Recommend",   "Claude Haiku",   "Personalized recommendation"),
        ("✨", "Reflect",     "Claude Haiku",   "Quality check & improvement"),
    ]:
        st.markdown(
            f"""<div class="glass-card" style="padding:13px 18px;margin-bottom:8px;">
              <div style="display:flex;align-items:center;gap:12px;">
                <div style="font-size:1.35rem;">{icon}</div>
                <div>
                  <div style="font-weight:700;font-size:0.91rem;">{name}
                    <span style="font-size:0.7rem;color:rgba(255,255,255,0.38);
                      background:rgba(255,255,255,0.06);border-radius:4px;
                      padding:1px 7px;margin-left:6px;">{model}</span>
                  </div>
                  <div style="font-size:0.79rem;color:rgba(255,255,255,0.46);margin-top:2px;">{desc}</div>
                </div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        """<div class="glass-card">
          <div style="font-weight:700;font-size:1.05rem;margin-bottom:10px;">🛍️ ShopMind AI v2.0</div>
          <div style="color:rgba(255,255,255,0.55);font-size:0.88rem;line-height:1.85;">
            <b>Framework:</b> Streamlit + LangGraph<br>
            <b>AI:</b> Anthropic Claude Haiku (fast, cost-efficient)<br>
            <b>Search:</b> SerpAPI — Google Shopping India<br>
            <b>Architecture:</b> Multi-agent pipeline with Memory &amp; Reflection
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CART PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_cart() -> None:
    st.markdown("### 🛒 Cart & Checkout")
    cart = st.session_state.cart
    step = st.session_state.get("cart_step", "cart")

    # Guard: reset mid-flow if cart was emptied externally
    if cart.count == 0 and step in ("checkout", "confirm"):
        st.session_state.cart_step   = "cart"
        st.session_state.show_payment = False
        st.session_state.ai_order_review = ""
        step = "cart"

    _cart_stepper(step)

    if   step == "cart":      _cart_view(cart)
    elif step == "checkout":  _cart_checkout(cart)
    elif step == "confirm":   _cart_confirm()
    elif step == "confirmed": _cart_confirmed()


def _cart_stepper(active: str) -> None:
    idx   = {"cart": 0, "checkout": 1, "confirm": 2, "confirmed": 3}.get(active, 0)
    steps = [("🛒", "Cart"), ("📋", "Details"), ("🤖", "Review & Pay"), ("✅", "Confirmed")]
    parts = ['<div class="stepper">']
    for i, (icon, label) in enumerate(steps):
        cls = "step-pill done" if i < idx else ("step-pill active" if i == idx else "step-pill")
        parts.append(f'<div class="{cls}">{icon} {label}</div>')
        if i < len(steps) - 1:
            parts.append('<span class="step-arrow">›</span>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _order_summary_box(cart) -> None:
    free_left = max(0.0, cart.FREE_SHIP_MIN - cart.subtotal)
    shipping_note = "🎉 FREE" if cart.shipping == 0 else f"₹{int(cart.shipping)}"
    if free_left > 0:
        shipping_note += f" — add ₹{int(free_left)} for free"
    st.markdown(
        f"""<div class="order-box">
          <div style="font-weight:700;font-size:1rem;margin-bottom:12px;">Order Summary</div>
          <div class="order-row"><span>Subtotal ({cart.count} item{'s' if cart.count != 1 else ''})</span>
            <span>₹{cart.subtotal:,.0f}</span></div>
          <div class="order-row"><span>GST (18%)</span><span>₹{cart.tax:,.2f}</span></div>
          <div class="order-row"><span>Shipping</span><span>{shipping_note}</span></div>
          <div class="order-row order-total"><span>Total</span><span>₹{cart.total:,.2f}</span></div>
        </div>""",
        unsafe_allow_html=True,
    )


def _cart_view(cart) -> None:
    if not cart.items:
        st.markdown(
            """<div class="empty-state">
              <div class="empty-icon">🛒</div>
              <div class="empty-title">Your cart is empty</div>
              <div class="empty-desc">Add products from the Search page.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("🔍 Start Shopping", key="cart_empty_shop", use_container_width=False):
            st.session_state._nav_target = "🔍 Search"
            st.rerun()
        return

    # Item rows
    for i, item in enumerate(cart.items):
        img_col, info_col, qty_col, rm_col = st.columns([1, 3, 2, 1])
        with img_col:
            if item.image:
                st.image(item.image, width=64)
            else:
                st.markdown('<div class="cart-img-ph">🛍️</div>', unsafe_allow_html=True)
        with info_col:
            if item.link:
                st.markdown(
                    f'<a href="{item.link}" target="_blank" style="color:#fff;font-weight:700;'
                    f'text-decoration:none;">{item.name[:55]}</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"**{item.name[:55]}**")
            source_tag = f'<span class="store-badge">{item.source}</span> ' if item.source else ""
            st.markdown(
                f"<span class='cart-price'>{source_tag}₹{int(item.price):,} × {item.quantity} "
                f"= <b style='color:#a09df5;'>₹{int(item.line_total):,}</b></span>",
                unsafe_allow_html=True,
            )
        with qty_col:
            qc1, qc2, qc3 = st.columns([1, 1, 1])
            with qc1:
                if st.button("−", key=f"dec_{i}", help="Decrease qty"):
                    if item.quantity > 1:
                        cart.set_qty(item.name, item.quantity - 1)
                    else:
                        cart.remove(item.name)
                    st.rerun()
            with qc2:
                st.markdown(
                    f"<div style='text-align:center;font-weight:700;padding:8px 0;'>{item.quantity}</div>",
                    unsafe_allow_html=True,
                )
            with qc3:
                if st.button("+", key=f"inc_{i}", help="Increase qty"):
                    cart.set_qty(item.name, item.quantity + 1)
                    st.rerun()
        with rm_col:
            if st.button("🗑️", key=f"rm_{i}", help="Remove item"):
                cart.remove(item.name)
                st.rerun()

    st.markdown("---")
    left_col, right_col = st.columns([3, 2])
    with left_col:
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("← Continue Shopping", key="cont_shop", use_container_width=True):
                st.session_state._nav_target = "🔍 Search"
                st.rerun()
        with bc2:
            if st.button("🗑️ Clear Cart", key="clear_cart", use_container_width=True):
                cart.clear()
                st.rerun()
    with right_col:
        _order_summary_box(cart)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Proceed to Checkout →", key="go_checkout", use_container_width=True):
            st.session_state.cart_step = "checkout"
            st.session_state.show_payment = False
            st.rerun()


def _cart_checkout(cart) -> None:
    form_col, summary_col = st.columns([3, 2])
    with summary_col:
        _order_summary_box(cart)

    with form_col:
        st.markdown("#### 📋 Shipping Details")
        with st.form("checkout_form"):
            name  = st.text_input("Full Name",  placeholder="Rahul Sharma")
            email = st.text_input("Email",       placeholder="rahul@email.com")
            phone = st.text_input("Phone",       placeholder="+91 98765 43210")
            addr  = st.text_area("Address",      placeholder="123 MG Road, Koramangala", height=80)
            city_col, pin_col = st.columns(2)
            with city_col:
                city    = st.text_input("City",    placeholder="Bengaluru")
            with pin_col:
                pincode = st.text_input("Pincode", placeholder="560034")
            submitted = st.form_submit_button("Review & Pay →", use_container_width=True)

        if submitted:
            errors = []
            if not name.strip():              errors.append("Full Name")
            if not email.strip():             errors.append("Email")
            if not phone.strip():             errors.append("Phone")
            if not addr.strip():              errors.append("Address")
            if not city.strip():              errors.append("City")
            if not pincode.strip():           errors.append("Pincode")
            elif not pincode.strip().isdigit() or len(pincode.strip()) != 6:
                errors.append("Pincode (must be 6 digits)")

            if errors:
                st.markdown(
                    f'<div class="notif notif-err">❌ Please fix: {", ".join(errors)}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.session_state.ship_info = {
                    "name": name.strip(), "email": email.strip(),
                    "phone": phone.strip(), "address": addr.strip(),
                    "city": city.strip(), "pincode": pincode.strip(),
                }
                st.session_state.cart_step       = "confirm"
                st.session_state.ai_order_review = ""   # reset so review refreshes
                st.rerun()

    if st.button("← Back to Cart", key="back_to_cart"):
        st.session_state.cart_step = "cart"
        st.rerun()


# ── Step 3: AI Review & Pay ────────────────────────────────────────────────

def _cart_confirm() -> None:
    cart = st.session_state.cart
    ship = st.session_state.get("ship_info", {})

    left_col, right_col = st.columns([3, 2])

    with right_col:
        _order_summary_box(cart)
        # Delivery address recap
        if ship:
            st.markdown(
                f"""<div class="order-box" style="margin-top:12px;">
                  <div style="font-weight:700;font-size:0.88rem;margin-bottom:8px;">📍 Delivering to</div>
                  <div style="font-size:0.82rem;color:rgba(255,255,255,0.6);line-height:1.7;">
                    <b>{ship.get('name','')}</b><br>
                    {ship.get('address','')}<br>
                    {ship.get('city','')} — {ship.get('pincode','')}<br>
                    📧 {ship.get('email','')}<br>
                    📱 {ship.get('phone','')}
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

    with left_col:
        # ── AI Order Review ──────────────────────────────────────────────
        st.markdown("#### 🤖 AI Order Review")
        if not st.session_state.get("ai_order_review"):
            with st.spinner("ShopMind AI is reviewing your order…"):
                st.session_state.ai_order_review = _generate_order_review(cart, ship)

        st.markdown(
            f"""<div class="rec-card">
              <div class="rec-header">
                <div class="rec-icon">🤖</div>
                <div class="rec-title">ShopMind AI Says</div>
              </div>
              <div class="rec-body">{st.session_state.ai_order_review}</div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Budget alert + cheaper alternatives ──────────────────────────
        budget = st.session_state.memory.preferences.get("typical_budget")
        if budget and cart.total > budget * 1.15:
            _show_alternatives(cart, float(budget))

        # ── Related / you-may-also-want ───────────────────────────────────
        _show_related_products(cart)

    # ── Payment section ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💳 Choose Payment Method")

    rzp_key = os.getenv("RAZORPAY_KEY_ID", "")
    if rzp_key:
        _payment_razorpay(cart, ship, rzp_key)
    else:
        _payment_demo(cart, ship)

    if st.button("← Edit Details", key="back_to_checkout_from_confirm"):
        st.session_state.cart_step       = "checkout"
        st.session_state.ai_order_review = ""
        st.rerun()


def _generate_order_review(cart, ship_info: dict) -> str:
    """Call Claude Haiku to generate a 2-3 sentence order review."""
    import anthropic as _ant
    items_text = "\n".join(
        f"- {it.name} ×{it.quantity} @ ₹{int(it.price):,}"
        for it in cart.items
    )
    budget      = st.session_state.memory.preferences.get("typical_budget")
    budget_line = f"User's usual budget: ₹{int(budget):,}" if budget else ""
    customer    = ship_info.get("name", "").split()[0] if ship_info.get("name") else "there"
    prompt = (
        f"You are ShopMind AI. Review this shopping order for {customer} in exactly 2-3 short sentences.\n\n"
        f"Items:\n{items_text}\n"
        f"Total: ₹{cart.total:,.2f}\n"
        f"{budget_line}\n\n"
        f"Be friendly and address the customer by first name. Mention the key item(s), whether it looks "
        f"like good value, and if the total is notably above the usual budget flag it gently. "
        f"End with a positive note encouraging them to proceed."
    )
    try:
        client = _ant.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        resp   = client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 140,
            messages   = [{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return (
            f"Your order of {cart.count} item(s) totalling ₹{cart.total:,.2f} is ready to go! "
            f"Everything looks good — proceed to payment when you're ready."
        )


def _show_alternatives(cart, budget: float) -> None:
    """Show cheaper alternatives when cart total exceeds typical budget."""
    last       = st.session_state.get("last_results") or {}
    products   = last.get("ranked_products", [])
    cart_names = {it.name for it in cart.items}
    max_price  = max((it.price for it in cart.items), default=0)

    cheaper = [
        p for p in products
        if p.get("name") not in cart_names
        and isinstance(p.get("price"), (int, float))
        and p["price"] < max_price * 0.85
        and p["price"] > 0
    ][:3]

    if not cheaper:
        return

    over_pct = int((cart.total / budget - 1) * 100)
    st.markdown(
        f'<div class="notif notif-warn">⚠️ Your cart is <b>{over_pct}% over</b> your typical '
        f'budget of ₹{int(budget):,}. Consider a cheaper alternative below.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("💡 Cheaper Alternatives", expanded=True):
        for ai, p in enumerate(cheaper):
            ac1, ac2, ac3 = st.columns([4, 1, 1])
            with ac1:
                st.markdown(f"**{p['name'][:52]}**")
                saving = int(max_price - p["price"])
                st.markdown(
                    f"<span style='color:#4caf87;font-size:0.85rem;'>"
                    f"₹{int(p['price']):,} — saves ₹{saving:,}</span>",
                    unsafe_allow_html=True,
                )
            with ac2:
                st.markdown(f"⭐ {p.get('rating') or 'N/A'}")
            with ac3:
                if st.button("Switch", key=f"alt_{ai}_{p['name'][:10]}", use_container_width=True):
                    expensive = max(cart.items, key=lambda x: x.price)
                    cart.remove(expensive.name)
                    cart.add(p)
                    st.session_state.ai_order_review = ""
                    st.rerun()


def _show_related_products(cart) -> None:
    """Suggest products from the last search that are not already in the cart."""
    last       = st.session_state.get("last_results") or {}
    products   = last.get("ranked_products", [])
    cart_names = {it.name for it in cart.items}
    related    = [p for p in products if p.get("name") not in cart_names][:3]

    if not related:
        return

    with st.expander("🛍️ You Might Also Want", expanded=False):
        r_cols = st.columns(len(related))
        for ri, (col, p) in enumerate(zip(r_cols, related)):
            with col:
                if p.get("image"):
                    st.image(p["image"], use_container_width=True)
                st.markdown(f"**{p['name'][:36]}**")
                st.markdown(
                    f"<span style='color:#a09df5;font-weight:700;'>₹{int(p.get('price') or 0):,}</span>",
                    unsafe_allow_html=True,
                )
                if st.button("+ Add", key=f"rel_{ri}_{p['name'][:10]}", use_container_width=True):
                    cart.add(p)
                    st.session_state.ai_order_review = ""
                    st.rerun()


def _simulate_and_place(cart, ship: dict, payment_id: str) -> None:
    """Animate payment processing then place the order."""
    prog = st.progress(0)
    msg  = st.empty()
    steps = [
        (20,  "🔐 Verifying payment details…"),
        (50,  "💳 Processing transaction…"),
        (78,  "📦 Confirming your order…"),
        (100, "✅ Payment successful!"),
    ]
    for pct, text in steps:
        msg.markdown(
            f'<div class="notif notif-info" style="margin:4px 0;">{text}</div>',
            unsafe_allow_html=True,
        )
        prog.progress(pct)
        time.sleep(0.65)
    prog.empty()
    msg.empty()
    _place_order(cart, ship, payment_id)


def _payment_razorpay(cart, ship: dict, rzp_key: str) -> None:
    """Razorpay checkout — supports UPI, Cards, Net Banking, Wallets, EMI."""
    methods_html = (
        '<div class="pay-methods-row">'
        + "".join(
            f'<span class="pay-method-pill">{m}</span>'
            for m in ["📱 UPI", "💳 Cards", "🏦 Net Banking", "👛 Wallets", "💰 EMI", "🚀 BNPL"]
        )
        + "</div>"
    )
    st.markdown(methods_html, unsafe_allow_html=True)

    rzp_html = f"""<!DOCTYPE html>
<html><body style="background:transparent;margin:0;padding:4px;font-family:sans-serif;">
<button id="rzp-btn" style="background:linear-gradient(135deg,#7c6bf3,#b06ef3);
  border:none;border-radius:50px;color:#fff;font-weight:700;padding:13px 0;
  font-size:1rem;cursor:pointer;box-shadow:0 4px 18px rgba(124,107,243,0.45);
  width:100%;letter-spacing:0.3px;">
  🔒 Pay ₹{int(cart.total):,} Securely
</button>
<div id="success-box" style="display:none;margin-top:14px;padding:14px 16px;
  border-radius:10px;background:rgba(76,175,135,0.12);border:1px solid #4caf87;">
  <div style="color:#4caf87;font-weight:700;font-size:0.95rem;">✅ Payment Successful!</div>
  <div style="margin-top:6px;font-size:0.82rem;color:#ccc;">Payment ID:</div>
  <div id="pid-box" style="font-family:monospace;font-size:0.9rem;color:#a09df5;
    background:rgba(0,0,0,0.3);padding:8px 12px;border-radius:6px;margin-top:4px;
    cursor:pointer;user-select:all;" title="Click to select all">—</div>
  <div style="font-size:0.75rem;color:#888;margin-top:6px;">
    👆 Click the ID above to select it, then copy and paste below.
  </div>
</div>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
document.getElementById('rzp-btn').onclick = function() {{
  new Razorpay({{
    key: '{rzp_key}',
    amount: {int(cart.total * 100)},
    currency: 'INR',
    name: 'ShopMind AI',
    description: 'Shopping Order',
    handler: function(r) {{
      document.getElementById('pid-box').innerText = r.razorpay_payment_id;
      document.getElementById('success-box').style.display = 'block';
      document.getElementById('rzp-btn').style.display = 'none';
      try {{ navigator.clipboard.writeText(r.razorpay_payment_id); }} catch(e) {{}}
    }},
    prefill: {{
      name: '{ship.get("name","")}',
      email: '{ship.get("email","")}',
      contact: '{ship.get("phone","")}'
    }},
    theme: {{ color: '#7c6bf3' }}
  }}).open();
}};
</script></body></html>"""
    components.html(rzp_html, height=160)

    pay_id = st.text_input(
        "Paste your Razorpay Payment ID here",
        placeholder="pay_XXXXXXXXXXXXXXXXXX",
        key="rzp_pay_id",
    )
    if st.button("✅ Confirm Order", key="confirm_rzp", use_container_width=True):
        if not pay_id.strip():
            st.markdown(
                '<div class="notif notif-err">❌ Complete Razorpay payment and paste the Payment ID.</div>',
                unsafe_allow_html=True,
            )
        else:
            _simulate_and_place(st.session_state.cart, ship, pay_id.strip())


def _payment_demo(cart, ship: dict) -> None:
    """Multi-method demo checkout — UPI / Card / Net Banking / Wallet / COD."""
    st.markdown(
        '<div class="notif notif-info">ℹ️ Demo mode — select any method. No real charge.</div>',
        unsafe_allow_html=True,
    )

    tab_upi, tab_card, tab_nb, tab_wallet, tab_cod = st.tabs(
        ["📱 UPI", "💳 Card", "🏦 Net Banking", "👛 Wallet", "🚚 Cash on Delivery"]
    )

    with tab_upi:
        st.markdown(
            f"<div style='background:rgba(124,107,243,0.08);border:1px solid rgba(124,107,243,0.25);"
            f"border-radius:10px;padding:14px 16px;margin-bottom:12px;'>"
            f"<div style='font-size:0.82rem;color:rgba(255,255,255,0.45);'>Pay to UPI ID</div>"
            f"<div style='font-size:1.1rem;font-weight:700;color:#a09df5;font-family:monospace;"
            f"margin-top:4px;'>shopmind@ybl</div>"
            f"<div style='font-size:0.82rem;color:rgba(255,255,255,0.45);margin-top:6px;'>"
            f"Amount: <b style='color:#fff;'>₹{cart.total:,.2f}</b></div></div>",
            unsafe_allow_html=True,
        )
        st.text_input("Your UPI ID", placeholder="yourname@upi", key="demo_upi_id")
        if st.button("Pay via UPI 📱", key="pay_upi", use_container_width=True):
            _simulate_and_place(cart, ship, f"UPI-{uuid.uuid4().hex[:10].upper()}")

    with tab_card:
        st.text_input("Card Number", placeholder="4111 1111 1111 1111", key="demo_card_no")
        cc1, cc2 = st.columns(2)
        with cc1:
            st.text_input("Expiry (MM/YY)", placeholder="08/27", key="demo_card_exp")
        with cc2:
            st.text_input("CVV", placeholder="•••", type="password", max_chars=4, key="demo_card_cvv")
        st.text_input("Name on Card", placeholder="RAHUL SHARMA", key="demo_card_name")
        if st.button(f"Pay ₹{cart.total:,.0f} via Card 💳", key="pay_card", use_container_width=True):
            _simulate_and_place(cart, ship, f"CARD-{uuid.uuid4().hex[:10].upper()}")

    with tab_nb:
        banks = [
            "SBI", "HDFC Bank", "ICICI Bank", "Axis Bank",
            "Kotak Mahindra", "PNB", "Bank of Baroda", "Canara Bank",
            "Yes Bank", "IndusInd Bank",
        ]
        bank = st.selectbox("Select Your Bank", banks, key="demo_nb_bank")
        st.markdown(
            f"<div style='color:rgba(255,255,255,0.45);font-size:0.83rem;margin:8px 0;'>"
            f"You'll be redirected to <b>{bank}</b>'s secure portal (demo).</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"Pay via {bank} 🏦", key="pay_nb", use_container_width=True):
            _simulate_and_place(cart, ship, f"NB-{uuid.uuid4().hex[:10].upper()}")

    with tab_wallet:
        wallets = ["Paytm", "PhonePe", "Amazon Pay", "Google Pay", "MobiKwik", "Freecharge", "Airtel Money"]
        wallet = st.selectbox("Select Wallet", wallets, key="demo_wallet_sel")
        st.markdown(
            f"<div style='color:rgba(255,255,255,0.45);font-size:0.83rem;margin:8px 0;'>"
            f"Pay ₹{cart.total:,.2f} from your <b>{wallet}</b> balance (demo).</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"Pay via {wallet} 👛", key="pay_wallet", use_container_width=True):
            _simulate_and_place(cart, ship, f"WALLET-{uuid.uuid4().hex[:10].upper()}")

    with tab_cod:
        st.markdown(
            f"<div style='background:rgba(76,175,135,0.08);border:1px solid rgba(76,175,135,0.25);"
            f"border-radius:10px;padding:16px;'>"
            f"<div style='font-size:1rem;font-weight:700;margin-bottom:8px;'>🚚 Cash on Delivery</div>"
            f"<div style='color:rgba(255,255,255,0.55);font-size:0.88rem;line-height:1.6;'>"
            f"Pay <b>₹{cart.total:,.2f}</b> in cash when your order arrives.<br>"
            f"Available for orders up to ₹50,000.</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Place Order (Cash on Delivery) 🚚", key="pay_cod", use_container_width=True):
            _simulate_and_place(cart, ship, f"COD-{uuid.uuid4().hex[:10].upper()}")


def _place_order(cart, ship_info: dict, payment_id: str) -> None:
    order = cart.to_order(ship_info, payment_id)
    st.session_state.orders.insert(0, order)
    st.session_state.last_order = order
    cart.clear()
    st.session_state.cart_step = "confirmed"
    st.session_state.show_payment = False
    from utils.email_sender import send_order_confirmation
    ok, emsg = send_order_confirmation(order)
    st.session_state["email_status"] = (ok, emsg)
    st.rerun()


def _cart_confirmed() -> None:
    import math, datetime
    order   = st.session_state.get("last_order", {})
    oid     = order.get("order_id", "—")
    total   = order.get("total", 0)
    items   = order.get("items", [])
    pay_id  = order.get("payment_id", "")
    ship    = order.get("shipping_info", {})

    # Estimate delivery: 3-5 business days from today
    today    = datetime.date.today()
    est_from = today + datetime.timedelta(days=3)
    est_to   = today + datetime.timedelta(days=5)
    est_str  = f"{est_from.strftime('%d %b')} – {est_to.strftime('%d %b %Y')}"

    # Detect payment method label from payment_id prefix
    method_map = {"UPI": "UPI", "CARD": "Credit / Debit Card",
                  "NB": "Net Banking", "WALLET": "Wallet",
                  "COD": "Cash on Delivery", "DEMO": "Demo"}
    method_label = next(
        (v for k, v in method_map.items() if pay_id.startswith(k)), "Online Payment"
    )

    st.markdown(
        f"""<div class="order-confirm">
          <div class="order-confirm-icon">🎉</div>
          <div class="order-confirm-title">Order Confirmed!</div>
          <div class="order-confirm-sub">
            Thank you, <b>{ship.get('name','')}</b>! Your order has been placed.<br><br>
            <span style="font-family:monospace;font-size:1rem;
              background:rgba(124,107,243,0.18);padding:4px 14px;border-radius:6px;">
              {oid}
            </span>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Two-column: order summary | delivery info
    sc1, sc2 = st.columns(2)
    with sc1:
        item_rows = "".join(
            f'<div class="order-row"><span>{it["name"][:38]}</span>'
            f'<span>×{it["qty"]} — ₹{int(it["total"]):,}</span></div>'
            for it in items
        )
        st.markdown(
            f"""<div class="order-box">
              <div style="font-weight:700;margin-bottom:10px;">🧾 Order Summary</div>
              {item_rows}
              <div class="order-row"><span>GST (18%)</span><span>₹{order.get('tax',0):,.2f}</span></div>
              <div class="order-row"><span>Shipping</span>
                <span>{"FREE" if order.get('shipping',0)==0 else "₹"+str(int(order.get('shipping',0)))}</span></div>
              <div class="order-row order-total"><span>Total Paid</span><span>₹{total:,.2f}</span></div>
            </div>""",
            unsafe_allow_html=True,
        )
    with sc2:
        st.markdown(
            f"""<div class="order-box">
              <div style="font-weight:700;margin-bottom:10px;">🚚 Delivery Info</div>
              <div class="order-row"><span>Estimated Delivery</span>
                <span style="color:#4caf87;font-weight:700;">{est_str}</span></div>
              <div class="order-row"><span>Payment via</span><span>{method_label}</span></div>
              <div class="order-row"><span>Delivering to</span>
                <span>{ship.get('city','')}</span></div>
              <div style="margin-top:10px;font-size:0.78rem;color:rgba(255,255,255,0.4);">
                📧 {ship.get('email','')}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # Email confirmation status
    email_status = st.session_state.pop("email_status", None)
    if email_status is not None:
        ok, emsg = email_status
        if ok:
            st.markdown(
                f'<div class="notif notif-ok">✅ Confirmation email sent to <b>{ship.get("email","")}</b>!</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="notif notif-warn">⚠️ Email not sent: {emsg}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        if st.button("📦 Track Order", key="goto_orders", use_container_width=True):
            st.session_state._nav_target = "📦 Orders"
            st.session_state.cart_step   = "cart"
            st.rerun()
    with cc2:
        if st.button("🔍 Continue Shopping", key="conf_shop", use_container_width=True):
            st.session_state._nav_target = "🔍 Search"
            st.session_state.cart_step   = "cart"
            st.rerun()
    with cc3:
        if st.button("🏠 Go to Home", key="conf_home", use_container_width=True):
            st.session_state._nav_target = "🏠 Home"
            st.session_state.cart_step   = "cart"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# ORDERS PAGE
# ═══════════════════════════════════════════════════════════════════════════

def render_orders() -> None:
    st.markdown("### 📦 My Orders")
    orders = st.session_state.orders

    # Show cancel email status if present
    cancel_status = st.session_state.pop("cancel_email_status", None)
    if cancel_status is not None:
        ok, emsg = cancel_status
        cls = "notif-ok" if ok else "notif-warn"
        ico = "✅" if ok else "⚠️"
        st.markdown(
            f'<div class="notif {cls}">{ico} {emsg}</div>',
            unsafe_allow_html=True,
        )

    if not orders:
        st.markdown(
            """<div class="empty-state">
              <div class="empty-icon">📦</div>
              <div class="empty-title">No orders yet</div>
              <div class="empty-desc">Completed orders will appear here.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("🔍 Start Shopping", key="orders_shop"):
            st.session_state._nav_target = "🔍 Search"
            st.rerun()
        return

    st.markdown(
        f'<div class="notif notif-ok">✅ {len(orders)} completed order(s)</div>',
        unsafe_allow_html=True,
    )

    for i, order in enumerate(orders):
        oid        = order.get("order_id", "—")
        total      = order.get("total", 0)
        status     = order.get("status", "Confirmed")
        ts         = order.get("timestamp", 0)
        items      = order.get("items", [])
        ship       = order.get("shipping_info", {})
        item_count = sum(it.get("qty", 1) for it in items)

        with st.expander(
            f"🏷️ {oid}  ·  {item_count} item(s)  ·  ₹{total:,.2f}  ·  {time_ago(ts)}",
            expanded=(i == 0),
        ):
            # Status badge + cancel button on same row
            badge_col, cancel_col = st.columns([5, 1])
            with badge_col:
                st.markdown(
                    f'<span class="oh-status confirmed">{status}</span>'
                    f'<span class="oh-id" style="margin-left:10px;">{oid}</span>',
                    unsafe_allow_html=True,
                )
            with cancel_col:
                if st.button("🗑️ Cancel", key=f"cancel_btn_{i}", use_container_width=True,
                             help="Cancel this order"):
                    st.session_state[f"confirm_cancel_{oid}"] = True

            # Inline confirmation prompt
            if st.session_state.get(f"confirm_cancel_{oid}"):
                st.markdown(
                    '<div class="notif notif-warn" style="margin:8px 0 4px;">'
                    '⚠️ Are you sure you want to cancel this order? This cannot be undone.'
                    '</div>',
                    unsafe_allow_html=True,
                )
                yes_col, no_col, _ = st.columns([1, 1, 4])
                with yes_col:
                    if st.button("✅ Yes, Cancel", key=f"yes_cancel_{i}", use_container_width=True):
                        from utils.email_sender import send_cancellation_email
                        ok, emsg = send_cancellation_email(order)
                        st.session_state.orders = [
                            o for o in st.session_state.orders
                            if o.get("order_id") != oid
                        ]
                        del st.session_state[f"confirm_cancel_{oid}"]
                        st.session_state["cancel_email_status"] = (ok, emsg)
                        st.rerun()
                with no_col:
                    if st.button("❌ Keep Order", key=f"no_cancel_{i}", use_container_width=True):
                        del st.session_state[f"confirm_cancel_{oid}"]
                        st.rerun()

            st.markdown("")

            items_col, ship_col = st.columns([3, 2])
            with items_col:
                st.markdown("**Items**")
                for it in items:
                    ic1, ic2 = st.columns([1, 4])
                    with ic1:
                        if it.get("image"):
                            st.image(it["image"], width=56)
                        else:
                            st.markdown(
                                '<div style="font-size:2rem;text-align:center;">🛍️</div>',
                                unsafe_allow_html=True,
                            )
                    with ic2:
                        if it.get("link"):
                            st.markdown(
                                f'<a href="{it["link"]}" target="_blank" style="color:#fff;'
                                f'font-weight:700;text-decoration:none;">{it["name"][:48]}</a>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(f"**{it['name'][:48]}**")
                        src = f" · 🏪 {it['source']}" if it.get("source") else ""
                        st.markdown(f"Qty: {it.get('qty',1)}  ·  ₹{int(it.get('total',0)):,}{src}")

            with ship_col:
                if ship:
                    st.markdown("**Delivered to**")
                    st.markdown(
                        f"{ship.get('name','')}  \n"
                        f"{ship.get('address','')}  \n"
                        f"{ship.get('city','')} {ship.get('pincode','')}  \n"
                        f"📧 {ship.get('email','')}  \n"
                        f"📱 {ship.get('phone','')}"
                    )
                st.markdown("**Payment ID**")
                st.code(order.get("payment_id", "—"), language=None)
                st.markdown(
                    f"<div style='font-size:0.82rem;color:rgba(255,255,255,0.45);margin-top:6px;'>"
                    f"Subtotal ₹{order.get('subtotal',0):,.0f} · GST ₹{order.get('tax',0):,.2f} "
                    f"· Shipping ₹{order.get('shipping',0):,.0f}</div>",
                    unsafe_allow_html=True,
                )


# ═══════════════════════════════════════════════════════════════════════════
# ALERTS PAGE  — proactive price-drop notifications
# ═══════════════════════════════════════════════════════════════════════════

def render_alerts() -> None:
    st.markdown("### 🔔 Price Alerts")

    from utils.price_monitor import PriceMonitor
    monitor = PriceMonitor()

    # ── Show pending drop alerts ───────────────────────────────────────────
    drops = st.session_state.get("price_drop_alerts", [])
    if drops:
        st.markdown(
            f'<div class="notif notif-ok">🎉 {len(drops)} price drop(s) detected since last check!</div>',
            unsafe_allow_html=True,
        )
        for d in drops:
            st.markdown(
                f"""<div class="glass-card" style="padding:16px 20px;margin-bottom:10px;">
                  <div style="font-weight:700;font-size:0.93rem;">{d['name'][:60]}</div>
                  <div style="margin-top:6px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
                    <span style="color:#9ca3af;text-decoration:line-through;font-size:0.9rem;">
                      ₹{int(d.get('old_price',0)):,}</span>
                    <span style="color:#4caf87;font-weight:800;font-size:1.1rem;">
                      ₹{int(d.get('new_price',0)):,}</span>
                    <span style="background:#dcfce7;color:#15803d;border-radius:20px;
                      padding:2px 10px;font-size:0.8rem;font-weight:700;">
                      -{d.get('drop_pct',0)}% ↓</span>
                    <span style="color:rgba(255,255,255,0.45);font-size:0.8rem;">
                      saves ₹{int(d.get('drop_amount',0)):,}</span>
                  </div>
                  {f'<a href="{d["link"]}" target="_blank" style="display:inline-block;margin-top:10px;color:#a09df5;font-size:0.85rem;">🔗 View Product →</a>' if d.get('link') else ''}
                </div>""",
                unsafe_allow_html=True,
            )
        if st.button("✅ Clear Alerts", key="clr_alerts"):
            st.session_state.price_drop_alerts = []
            st.rerun()
        st.markdown("---")

    # ── Manual price check ─────────────────────────────────────────────────
    col_check, col_info = st.columns([1, 3])
    with col_check:
        if st.button("🔄 Check Prices Now", key="manual_check", use_container_width=True):
            with st.spinner("Checking prices for all watched products…"):
                _auto_price_check()
            st.rerun()
    with col_info:
        last = st.session_state.get("last_price_check", 0)
        if last:
            import datetime as _dt
            checked_at = _dt.datetime.fromtimestamp(last).strftime("%d %b %Y, %I:%M %p")
            st.markdown(
                f"<div style='color:rgba(255,255,255,0.4);font-size:0.82rem;padding-top:10px;'>"
                f"Last checked: {checked_at} · Auto-checks every hour</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Watched products list ──────────────────────────────────────────────
    if not monitor.watches:
        st.markdown(
            """<div class="empty-state">
              <div class="empty-icon">🔔</div>
              <div class="empty-title">No price watches set</div>
              <div class="empty-desc">Click "🔔 Watch Price" on any product card to start tracking.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    st.markdown(f"**Watching {len(monitor.watches)} product(s)**")
    for i, w in enumerate(monitor.watches):
        orig  = w.get("original_price", 0)
        curr  = w.get("current_price", orig)
        tgt   = w.get("target_price", 0)
        drift = int(((curr - orig) / orig * 100)) if orig else 0
        drift_str = (f"▲ {drift}%" if drift > 0 else f"▼ {abs(drift)}%") if drift else "—"
        drift_col = "#f05050" if drift > 0 else ("#4caf87" if drift < 0 else "#888")

        wc1, wc2, wc3, wc4 = st.columns([3, 1, 1, 1])
        with wc1:
            st.markdown(f"**{w['name'][:52]}**")
            st.markdown(
                f"<span style='font-size:0.8rem;color:rgba(255,255,255,0.45);'>"
                f"Target: ₹{int(tgt):,} · Alert: {w.get('alert_email','—')}</span>",
                unsafe_allow_html=True,
            )
        with wc2:
            st.markdown(
                f"<div style='text-align:center;font-size:0.85rem;padding-top:8px;'>"
                f"₹{int(curr):,}</div>",
                unsafe_allow_html=True,
            )
        with wc3:
            st.markdown(
                f"<div style='text-align:center;font-size:0.82rem;color:{drift_col};"
                f"padding-top:8px;'>{drift_str}</div>",
                unsafe_allow_html=True,
            )
        with wc4:
            if st.button("🗑️", key=f"unwatch_{i}", help="Stop watching"):
                monitor.unwatch(w["name"])
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# GOALS PAGE  — long-horizon buying goals
# ═══════════════════════════════════════════════════════════════════════════

def render_goals() -> None:
    st.markdown("### 🎯 Buying Goals")
    st.markdown(
        '<div class="notif notif-info">Set a buying goal and ShopMind AI will '
        'automatically tag matching products on every search.</div>',
        unsafe_allow_html=True,
    )

    mem    = st.session_state.memory
    active = mem.get_active_goals()
    done   = [g for g in mem.goals if g["status"] != "active"]

    # ── Add new goal ───────────────────────────────────────────────────────
    with st.expander("➕ Add New Goal", expanded=(not active)):
        with st.form("goal_form"):
            desc     = st.text_input("What do you want to buy?",
                                      placeholder="e.g. Gaming laptop for college")
            keywords = st.text_input("Search keywords",
                                      placeholder="e.g. gaming laptop RTX")
            gc1, gc2 = st.columns(2)
            with gc1:
                budget = st.number_input("Budget (₹, 0 = no limit)", min_value=0,
                                          value=0, step=1000)
            with gc2:
                deadline = st.text_input("Deadline (optional)", placeholder="e.g. June 2026")
            submitted = st.form_submit_button("🎯 Set Goal", use_container_width=True)

        if submitted:
            if not desc.strip() or not keywords.strip():
                st.markdown(
                    '<div class="notif notif-err">❌ Description and keywords are required.</div>',
                    unsafe_allow_html=True,
                )
            else:
                mem.add_goal(
                    description=desc.strip(),
                    keywords=keywords.strip(),
                    budget=float(budget) if budget > 0 else None,
                    deadline=deadline.strip(),
                )
                st.markdown(
                    '<div class="notif notif-ok">✅ Goal saved! We\'ll tag matching products automatically.</div>',
                    unsafe_allow_html=True,
                )
                st.rerun()

    # ── Active goals ───────────────────────────────────────────────────────
    if active:
        st.markdown(f"#### 🟢 Active Goals ({len(active)})")
        for g in active:
            gc1, gc2, gc3 = st.columns([4, 1, 1])
            with gc1:
                budget_str = f" · Budget ₹{int(g['budget']):,}" if g.get("budget") else ""
                dl_str     = f" · Deadline: {g['deadline']}"    if g.get("deadline") else ""
                st.markdown(
                    f"""<div class="glass-card" style="padding:14px 18px;">
                      <div style="font-weight:700;font-size:0.93rem;">{g['description']}</div>
                      <div style="font-size:0.78rem;color:rgba(255,255,255,0.45);margin-top:4px;">
                        🔑 {g['keywords']}{budget_str}{dl_str}
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with gc2:
                if st.button("✅ Done", key=f"achieve_{g['id']}", use_container_width=True):
                    mem.achieve_goal(g["id"])
                    st.rerun()
            with gc3:
                if st.button("✕ Cancel", key=f"cancel_g_{g['id']}", use_container_width=True):
                    mem.cancel_goal(g["id"])
                    st.rerun()
    else:
        st.markdown(
            "<div style='color:rgba(255,255,255,0.35);font-size:0.88rem;'>"
            "No active goals. Add one above.</div>",
            unsafe_allow_html=True,
        )

    # ── Completed / cancelled goals ────────────────────────────────────────
    if done:
        st.markdown("---")
        st.markdown(f"#### 📋 Past Goals ({len(done)})")
        for g in done:
            icon = "✅" if g["status"] == "achieved" else "✕"
            col  = "#4caf87" if g["status"] == "achieved" else "#f05050"
            st.markdown(
                f"<div style='padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.06);"
                f"font-size:0.85rem;color:rgba(255,255,255,0.55);'>"
                f"<span style='color:{col};'>{icon}</span> {g['description']}</div>",
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════

render_sidebar()

_page = st.session_state.get("page", "Home")
if   _page == "Home":            render_home()
elif _page == "Search":          render_search()
elif _page == "Cart":            render_cart()
elif _page == "Orders":          render_orders()
elif _page == "Recommendations": render_recommendations()
elif _page == "History":         render_history()
elif _page == "Alerts":          render_alerts()
elif _page == "Goals":           render_goals()
elif _page == "Settings":        render_settings()
