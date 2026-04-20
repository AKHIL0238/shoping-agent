"""
UI Components — CSS, HTML helpers, and pipeline renderer.
All glassmorphism/gradient styles live here so app.py stays clean.
"""

from __future__ import annotations
from typing import Dict


# ─────────────────────────────────────────────────────────────────────────────
# FULL CSS (dark-first, light-theme class override at the bottom)
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
<style>
/* ── Variables ──────────────────────────────────────────────── */
:root {
  --pri:     #7c6bf3;
  --pri-dk:  #5a4ad1;
  --sec:     #b06ef3;
  --acc:     #f3a06e;
  --ok:      #4caf87;
  --warn:    #f0a500;
  --err:     #f05050;

  --bg:      #0d0d1a;
  --bg2:     #1a1a2e;
  --glass:   rgba(255,255,255,0.05);
  --glass-h: rgba(255,255,255,0.08);
  --border:  rgba(255,255,255,0.09);

  --t1: #ffffff;
  --t2: rgba(255,255,255,0.68);
  --t3: rgba(255,255,255,0.38);

  --shadow: 0 8px 32px rgba(0,0,0,0.45);
  --grad:   linear-gradient(135deg, var(--pri), var(--sec));
  --r:  16px;
  --r2:  8px;
  --tr: all 0.28s cubic-bezier(0.4,0,0.2,1);
}

/* ── Reset / Base ───────────────────────────────────────────── */
.stApp {
  background: linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 55%, #16213e 100%);
  color: var(--t1);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  min-height: 100vh;
}
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Scrollbar ─────────────────────────────────────────────── */
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background: var(--pri); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background: var(--sec); }

/* ── Glass card ────────────────────────────────────────────── */
.glass-card {
  background: var(--glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 24px;
  box-shadow: var(--shadow);
  transition: var(--tr);
}
.glass-card:hover {
  background: var(--glass-h);
  border-color: rgba(124,107,243,0.4);
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(124,107,243,0.22);
}

/* ── Product card ───────────────────────────────────────────── */
.prod-card {
  background: linear-gradient(135deg,rgba(124,107,243,0.10),rgba(176,110,243,0.04));
  backdrop-filter: blur(18px);
  border: 1px solid rgba(124,107,243,0.18);
  border-radius: var(--r);
  overflow: hidden;
  transition: var(--tr);
  position: relative;
}
.prod-card:hover {
  border-color: rgba(124,107,243,0.55);
  box-shadow: 0 12px 40px rgba(124,107,243,0.28);
  transform: translateY(-4px);
}
.prod-card img {
  width:100%; height:185px; object-fit:cover;
  border-radius: var(--r) var(--r) 0 0;
  display:block;
}
.prod-img-placeholder {
  width:100%; height:185px;
  background: rgba(124,107,243,0.10);
  border-radius: var(--r) var(--r) 0 0;
  display:flex; align-items:center; justify-content:center;
  font-size:3rem;
}
.prod-body { padding:14px 16px 16px; }
.prod-title {
  font-size:0.9rem; font-weight:600; color:var(--t1);
  margin-bottom:8px; line-height:1.4;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
}
.prod-price {
  font-size:1.25rem; font-weight:700;
  background: var(--grad);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.prod-rating { font-size:0.82rem; color:var(--warn); margin-top:4px; }

/* ── Badges ────────────────────────────────────────────────── */
.badge {
  position:absolute; top:10px; left:10px;
  padding:3px 10px; border-radius:20px;
  font-size:0.7rem; font-weight:700; letter-spacing:.5px;
  text-transform:uppercase; z-index:5; color:#fff;
}
.badge-best { background: var(--grad); }
.badge-deal { background: linear-gradient(135deg,#f0a500,#f05050); }
.badge-top  { background: linear-gradient(135deg,#4caf87,#2196f3); }

/* ── Pipeline ───────────────────────────────────────────────── */
.pipeline {
  display:flex; align-items:center; justify-content:space-between;
  padding:22px 28px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: var(--r);
  overflow-x:auto; gap:0;
  margin: 14px 0;
}
.pipe-step { display:flex; flex-direction:column; align-items:center; gap:7px; flex:1 0 auto; }
.pipe-circle {
  width:44px; height:44px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:1.1rem; border:2px solid var(--border);
  background: rgba(255,255,255,0.04);
  transition: var(--tr); position:relative; z-index:1;
}
.pipe-circle.running {
  border-color: var(--pri);
  background: rgba(124,107,243,0.18);
  box-shadow: 0 0 0 0 rgba(124,107,243,0.6);
  animation: pulse-ring 1.4s infinite;
}
.pipe-circle.complete { border-color: var(--ok); background: rgba(76,175,135,0.18); }
.pipe-circle.error    { border-color: var(--err); background: rgba(240,80,80,0.18); }
.pipe-label { font-size:0.72rem; color:var(--t2); font-weight:500; text-align:center; max-width:70px; }
.pipe-conn  { flex:1; height:2px; background: var(--border); margin:0 4px; position:relative; top:-17px; }
.pipe-conn.done { background: var(--ok); }

@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0   rgba(124,107,243,0.65); }
  70%  { box-shadow: 0 0 0 12px rgba(124,107,243,0);    }
  100% { box-shadow: 0 0 0 0   rgba(124,107,243,0);    }
}

/* ── Hero ──────────────────────────────────────────────────── */
.hero { text-align:center; padding:48px 20px 32px; }
.hero h1 {
  font-size:clamp(2rem,4vw,3rem); font-weight:800;
  background: linear-gradient(135deg,#fff,var(--sec));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
  margin-bottom:10px; line-height:1.2;
}
.hero p { color:var(--t2); font-size:1.05rem; max-width:480px; margin:0 auto 32px; line-height:1.6; }

/* ── All text inputs & text areas — white bg, black text ───── */
.stTextInput > div > div > input,
.stTextInput > div > div > input[type="text"],
.stTextInput > div > div > input[type="password"],
.stTextInput > div > div > input[type="email"],
.stTextArea  > div > div > textarea {
  background: rgba(255,255,255,0.96) !important;
  border: 1.5px solid rgba(124,107,243,0.45) !important;
  border-radius: 12px !important;
  color: #111111 !important;
  padding: 11px 18px !important;
  font-size: 0.97rem !important;
  transition: var(--tr) !important;
}
/* Search bar keeps pill shape */
.stTextInput > div > div > input {
  border-radius: 50px !important;
  padding: 13px 22px !important;
  font-size: 1rem !important;
}
.stTextInput > div > div > input:focus,
.stTextArea  > div > div > textarea:focus {
  border-color: var(--pri) !important;
  box-shadow: 0 0 0 3px rgba(124,107,243,0.25) !important;
  background: #ffffff !important;
  color: #111111 !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea  > div > div > textarea::placeholder {
  color: rgba(0,0,0,0.38) !important;
}
/* Labels above inputs */
.stTextInput label, .stTextArea label {
  color: rgba(255,255,255,0.75) !important;
  font-size: 0.85rem !important;
}

/* ── Buttons — white text, bold, text-shadow for contrast ─── */
.stButton > button {
  background: var(--grad) !important;
  border: none !important;
  border-radius: 50px !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.25px !important;
  padding: 10px 26px !important;
  text-shadow: 0 1px 3px rgba(0,0,0,0.35) !important;
  box-shadow: 0 4px 15px rgba(124,107,243,0.38) !important;
  transition: var(--tr) !important;
}
/* Streamlit renders button label inside <p> — force colour there too */
.stButton > button p,
.stButton > button div,
.stButton > button span {
  color: #ffffff !important;
  font-weight: 700 !important;
  text-shadow: 0 1px 3px rgba(0,0,0,0.35) !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 24px rgba(124,107,243,0.55) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Metrics ───────────────────────────────────────────────── */
[data-testid="stMetricValue"] {
  background: var(--grad) !important;
  -webkit-background-clip:text !important; -webkit-text-fill-color:transparent !important;
  font-size:1.55rem !important; font-weight:700 !important;
}
[data-testid="stMetricLabel"] { color:var(--t3) !important; font-size:0.78rem !important; }
[data-testid="metric-container"] {
  background: var(--glass);
  border: 1px solid var(--border);
  border-radius: var(--r2);
  padding: 16px 20px;
}

/* ── Sidebar ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: rgba(10,10,22,0.96) !important;
  backdrop-filter: blur(20px) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stRadio label {
  background: rgba(255,255,255,0.03);
  border: 1px solid transparent;
  border-radius: var(--r2); padding: 10px 14px;
  cursor:pointer; transition:var(--tr); font-size:0.9rem;
  display:flex; align-items:center; gap:8px; margin-bottom:4px;
}
[data-testid="stSidebar"] .stRadio label:hover {
  background: rgba(124,107,243,0.14);
  border-color: rgba(124,107,243,0.28);
}

/* ── Recommendation card ───────────────────────────────────── */
.rec-card {
  background: linear-gradient(135deg,rgba(124,107,243,0.13),rgba(176,110,243,0.07));
  border: 1px solid rgba(124,107,243,0.28);
  border-radius: var(--r); padding:22px 24px; margin:14px 0;
  position:relative; overflow:hidden;
}
.rec-card::before {
  content:''; position:absolute; top:0; left:0; right:0; height:3px;
  background: var(--grad);
}
.rec-header { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.rec-icon {
  width:38px; height:38px; border-radius:50%;
  background: var(--grad);
  display:flex; align-items:center; justify-content:center; font-size:1rem;
}
.rec-title { font-size:1rem; font-weight:700; color:var(--t1); }
.rec-body  { color:var(--t2); font-size:0.93rem; line-height:1.65; }

/* ── Notifications ─────────────────────────────────────────── */
.notif {
  padding:13px 18px; border-radius:var(--r2);
  display:flex; align-items:center; gap:10px; font-size:0.88rem; margin:10px 0;
}
.notif-ok   { background:rgba(76,175,135,0.13); border:1px solid rgba(76,175,135,0.38); color:#4caf87; }
.notif-err  { background:rgba(240,80,80,0.12);  border:1px solid rgba(240,80,80,0.38);  color:#f05050; }
.notif-info { background:rgba(124,107,243,0.12);border:1px solid rgba(124,107,243,0.38);color:#a09df5; }
.notif-warn { background:rgba(240,165,0,0.12); border:1px solid rgba(240,165,0,0.38);  color:#f0a500; }

/* ── History item ──────────────────────────────────────────── */
.history-item {
  padding:12px 16px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: var(--r2); margin-bottom:8px;
  transition:var(--tr);
}
.history-item:hover { background:rgba(124,107,243,0.08); border-color:rgba(124,107,243,0.28); }
.h-query { font-size:0.9rem; color:var(--t1); font-weight:500; }
.h-meta  { font-size:0.74rem; color:var(--t3); margin-top:3px; }

/* ── Tags ──────────────────────────────────────────────────── */
.tag {
  display:inline-block; padding:3px 10px; border-radius:20px;
  font-size:0.74rem; font-weight:500;
  background:rgba(124,107,243,0.14); border:1px solid rgba(124,107,243,0.28);
  color:#a09df5; margin:2px;
}

/* ── Empty state ───────────────────────────────────────────── */
.empty-state { text-align:center; padding:60px 20px; color:var(--t3); }
.empty-icon  { font-size:4rem; margin-bottom:14px; }
.empty-title { font-size:1.25rem; font-weight:600; color:var(--t2); margin-bottom:6px; }
.empty-desc  { font-size:0.88rem; }

/* ── Progress bar ──────────────────────────────────────────── */
.stProgress > div > div { background:var(--grad) !important; border-radius:10px !important; }
.stProgress > div       { background:rgba(255,255,255,0.08) !important; border-radius:10px !important; }

/* ── Step log ──────────────────────────────────────────────── */
.step-log {
  font-family:'JetBrains Mono','Cascadia Code',monospace;
  background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.06);
  border-radius:var(--r2); padding:14px; font-size:0.8rem; line-height:1.85;
  color:var(--t2); max-height:180px; overflow-y:auto;
}

/* ── Section divider ───────────────────────────────────────── */
.sec-div { display:flex; align-items:center; gap:14px; margin:28px 0; }
.sec-div::before, .sec-div::after { content:''; flex:1; height:1px; background:var(--border); }
.sec-title { font-size:0.8rem; font-weight:600; color:var(--t3); text-transform:uppercase; letter-spacing:1.5px; white-space:nowrap; }

/* ── Expander ──────────────────────────────────────────────── */
.stExpander {
  background:rgba(255,255,255,0.03) !important;
  border:1px solid rgba(255,255,255,0.07) !important;
  border-radius:var(--r2) !important;
}

/* ── Select / slider overrides ─────────────────────────────── */
[data-baseweb="select"] > div {
  background: rgba(255,255,255,0.06) !important;
  border-color: rgba(255,255,255,0.14) !important;
  border-radius: var(--r2) !important;
}
[data-testid="stSlider"] [data-testid="stSliderThumb"] { background:var(--pri) !important; }

/* ── Confirm box ───────────────────────────────────────────── */
.confirm-box {
  background:rgba(240,165,0,0.07); border:1px solid rgba(240,165,0,0.3);
  border-radius:var(--r); padding:18px 22px; margin:14px 0;
}
.confirm-box-hdr {
  display:flex; align-items:center; gap:9px;
  font-size:0.97rem; font-weight:600; color:var(--warn); margin-bottom:8px;
}
.confirm-box-body { font-size:0.88rem; color:var(--t2); margin-bottom:14px; }

/* ── Cart item row ─────────────────────────────────────────── */
.cart-row {
  display:flex; align-items:center; gap:14px;
  background:var(--glass); border:1px solid var(--border);
  border-radius:var(--r2); padding:14px 16px; margin-bottom:10px;
  transition:var(--tr);
}
.cart-row:hover { background:var(--glass-h); border-color:rgba(124,107,243,0.3); }
.cart-img {
  width:72px; height:72px; object-fit:cover; border-radius:8px; flex-shrink:0;
}
.cart-img-ph {
  width:72px; height:72px; border-radius:8px; flex-shrink:0;
  background:rgba(124,107,243,0.12); display:flex;
  align-items:center; justify-content:center; font-size:1.8rem;
}
.cart-name  { font-size:0.9rem; font-weight:600; color:var(--t1); line-height:1.4; }
.cart-price { font-size:0.85rem; color:var(--t3); margin-top:2px; }

/* ── Order summary box ─────────────────────────────────────── */
.order-box {
  background:linear-gradient(135deg,rgba(124,107,243,0.10),rgba(176,110,243,0.05));
  border:1px solid rgba(124,107,243,0.25);
  border-radius:var(--r); padding:20px 22px;
}
.order-row {
  display:flex; justify-content:space-between; align-items:center;
  font-size:0.88rem; color:var(--t2); padding:5px 0;
  border-bottom:1px solid rgba(255,255,255,0.05);
}
.order-row:last-child { border-bottom:none; }
.order-total { font-size:1.15rem; font-weight:700; color:var(--t1); }

/* ── Checkout stepper ──────────────────────────────────────── */
.stepper {
  display:flex; align-items:center; gap:0; margin-bottom:24px;
}
.step-pill {
  display:flex; align-items:center; gap:8px; padding:8px 18px;
  border-radius:50px; font-size:0.82rem; font-weight:600;
  background:rgba(255,255,255,0.04); border:1px solid var(--border);
  color:var(--t3);
}
.step-pill.active {
  background:rgba(124,107,243,0.2); border-color:var(--pri); color:#fff;
}
.step-pill.done {
  background:rgba(76,175,135,0.15); border-color:var(--ok); color:var(--ok);
}
.step-arrow { color:var(--t3); padding:0 6px; font-size:0.85rem; }

/* ── Payment card ──────────────────────────────────────────── */
.pay-card {
  background:rgba(255,255,255,0.04); border:1px solid var(--border);
  border-radius:var(--r); padding:24px;
}
.card-field input {
  background:rgba(255,255,255,0.07) !important;
  border:1px solid rgba(255,255,255,0.14) !important;
  border-radius:var(--r2) !important; color:#fff !important;
}

/* ── Order confirmation ────────────────────────────────────── */
.order-confirm {
  text-align:center; padding:40px 20px;
}
.order-confirm-icon {
  font-size:4rem; margin-bottom:16px;
  animation: pop 0.4s cubic-bezier(0.175,0.885,0.32,1.275);
}
@keyframes pop {
  0%   { transform:scale(0); }
  100% { transform:scale(1); }
}
.order-confirm-title {
  font-size:1.6rem; font-weight:800;
  background:var(--grad); -webkit-background-clip:text;
  -webkit-text-fill-color:transparent; background-clip:text;
  margin-bottom:8px;
}
.order-confirm-sub { font-size:0.95rem; color:var(--t2); }

/* ── Cart badge (sidebar) ──────────────────────────────────── */
.cart-badge {
  display:inline-block; background:var(--pri); color:#fff;
  border-radius:50%; width:18px; height:18px; font-size:0.68rem;
  font-weight:700; text-align:center; line-height:18px;
  margin-left:6px; vertical-align:middle;
}

/* ── Order history card ────────────────────────────────────── */
.order-hist {
  background:var(--glass); border:1px solid var(--border);
  border-radius:var(--r2); padding:16px 18px; margin-bottom:10px;
  transition:var(--tr);
}
.order-hist:hover { background:var(--glass-h); border-color:rgba(124,107,243,0.3); }
.oh-id    { font-size:0.72rem; color:var(--t3); font-family:monospace; }
.oh-total { font-size:1.1rem; font-weight:700; color:var(--pri); }
.oh-status {
  display:inline-block; padding:2px 10px; border-radius:20px;
  font-size:0.7rem; font-weight:700; letter-spacing:.5px;
}
.oh-status.confirmed { background:rgba(76,175,135,0.18); color:var(--ok); border:1px solid var(--ok); }

/* ── Product card footer (source + view link) ──────────────── */
.prod-footer {
  display:flex; align-items:center; justify-content:space-between;
  padding:8px 16px 14px; border-top:1px solid var(--border);
  margin-top:6px; gap:8px;
}
.store-badge {
  font-size:0.7rem; color:var(--t3); font-weight:500;
  background:rgba(255,255,255,0.04); border:1px solid var(--border);
  border-radius:4px; padding:2px 8px; white-space:nowrap;
  overflow:hidden; max-width:110px; text-overflow:ellipsis;
}
.view-store-btn {
  font-size:0.75rem; font-weight:600; color:var(--pri) !important;
  text-decoration:none !important;
  border:1px solid rgba(124,107,243,0.4);
  border-radius:20px; padding:4px 12px;
  transition:var(--tr); white-space:nowrap;
}
.view-store-btn:hover {
  background:rgba(124,107,243,0.18); color:#fff !important;
  border-color:var(--pri);
}

/* ── Payment method pills ──────────────────────────────────── */
.pay-methods-row {
  display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px;
}
.pay-method-pill {
  background:rgba(124,107,243,0.10); border:1px solid rgba(124,107,243,0.28);
  border-radius:20px; padding:5px 14px; font-size:0.78rem;
  color:#a09df5; font-weight:500;
}

/* ── Light theme class override ────────────────────────────── */
.light .stApp {
  background: linear-gradient(135deg,#f0f2f8,#e8eaf6,#ede7f6) !important;
  color: #1a1a2e !important;
}
.light .glass-card { background: rgba(255,255,255,0.85); border-color:rgba(0,0,0,0.08); }
</style>
"""


def get_css() -> str:
    return _CSS


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline HTML renderer
# ─────────────────────────────────────────────────────────────────────────────

_PIPE_STEPS = [
    ("plan",      "📋", "Plan"),
    ("intent",    "🧠", "Intent"),
    ("search",    "🔍", "Search"),
    ("compare",   "⚖️",  "Compare"),
    ("recommend", "💡", "Recommend"),
    ("reflect",   "✨", "Reflect"),
]


def render_pipeline_html(step_status: Dict[str, str]) -> str:
    """Return HTML for the 6-step pipeline tracker."""
    parts = ['<div class="pipeline">']
    for i, (key, icon, label) in enumerate(_PIPE_STEPS):
        status = step_status.get(key, "pending")
        circle_cls = f"pipe-circle {status}" if status != "pending" else "pipe-circle"
        # override icon for complete/error
        display_icon = "✅" if status == "complete" else ("❌" if status == "error" else icon)
        parts.append(f"""
          <div class="pipe-step">
            <div class="{circle_cls}">{display_icon}</div>
            <div class="pipe-label">{label}</div>
          </div>""")
        if i < len(_PIPE_STEPS) - 1:
            done_cls = "pipe-conn done" if status == "complete" else "pipe-conn"
            parts.append(f'<div class="{done_cls}"></div>')
    parts.append("</div>")
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Product card HTML (visual-only; Streamlit buttons are rendered separately)
# ─────────────────────────────────────────────────────────────────────────────

def render_product_card_html(product: dict, rank: int) -> str:
    """Return HTML string for a product card (no interactive elements)."""
    name    = product.get("name", "Unknown Product")
    price   = product.get("price", 0)
    rating  = product.get("rating", 0)
    image   = product.get("image", "")
    link    = product.get("link", "")
    source  = product.get("source", "")
    reviews = product.get("reviews", 0)

    # Badge
    badge = ""
    if rank == 0:
        badge = '<span class="badge badge-best">Best Pick</span>'
    elif rank < 3 and isinstance(price, (int, float)) and price > 0:
        badge = '<span class="badge badge-deal">Top Deal</span>'
    elif isinstance(rating, (int, float)) and rating >= 4.5:
        badge = '<span class="badge badge-top">Top Rated</span>'

    price_str  = f"₹{int(price):,}" if isinstance(price, (int, float)) and price > 0 else "Price N/A"
    stars      = "⭐" * min(5, int(rating)) if isinstance(rating, (int, float)) else ""
    rating_str = f"{rating}/5" if isinstance(rating, (int, float)) and rating > 0 else "N/A"
    rev_str    = f" ({int(reviews):,} reviews)" if reviews and int(reviews) > 0 else ""
    title_safe = name[:72] + ("…" if len(name) > 72 else "")

    if image:
        img_html = (
            f'<img src="{image}" alt="product" '
            'onerror="this.parentElement.innerHTML=\'<div class=prod-img-placeholder>🛍️</div>\'">'
        )
    else:
        img_html = '<div class="prod-img-placeholder">🛍️</div>'

    # Footer: store badge + view link
    footer = ""
    if source or link:
        store_label = source[:22] if source else "Store"
        view_link = (
            f'<a href="{link}" target="_blank" class="view-store-btn">View on {store_label} →</a>'
            if link else ""
        )
        store_badge = f'<span class="store-badge">🏪 {source[:20]}</span>' if source else '<span></span>'
        footer = f'<div class="prod-footer">{store_badge}{view_link}</div>'

    return f"""
<div class="prod-card" style="margin-bottom:16px;">
  <div style="position:relative;">{badge}{img_html}</div>
  <div class="prod-body">
    <div class="prod-title">{title_safe}</div>
    <div class="prod-price">{price_str}</div>
    <div class="prod-rating">{stars} {rating_str}{rev_str}</div>
  </div>
  {footer}
</div>"""
