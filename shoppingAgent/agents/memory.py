"""
MemoryModule — persists search history, preferences, AND long-horizon goals to disk.
File: .shopmind_memory.json in project root.
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

_MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", ".shopmind_memory.json")


@dataclass
class SearchRecord:
    query:          str
    intent:         Dict[str, Any]
    results:        List[Dict]
    recommendation: str
    timestamp:      float = field(default_factory=time.time)


class MemoryModule:
    MAX_HISTORY = 30

    def __init__(self) -> None:
        self.history:     List[SearchRecord] = []
        self.preferences: Dict[str, Any]     = {}
        self.goals:       List[Dict]         = []
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            path = os.path.abspath(_MEMORY_FILE)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.preferences = data.get("preferences", {})
                self.goals       = data.get("goals", [])
                for rec in data.get("history", []):
                    self.history.append(SearchRecord(**rec))
        except Exception:
            pass

    def _save(self) -> None:
        try:
            path = os.path.abspath(_MEMORY_FILE)
            data = {
                "preferences": self.preferences,
                "history":     [asdict(r) for r in self.history],
                "goals":       self.goals,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Search history ─────────────────────────────────────────────────────

    def add_search(
        self,
        query:          str,
        intent:         Dict[str, Any],
        results:        List[Dict],
        recommendation: str = "",
    ) -> None:
        record = SearchRecord(
            query=query, intent=intent,
            results=results[:5], recommendation=recommendation,
        )
        self.history = [h for h in self.history if h.query != query]
        self.history.insert(0, record)
        self.history = self.history[:self.MAX_HISTORY]
        self._update_preferences(intent, results)
        self._save()

    def save_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value
        self._save()

    def _update_preferences(self, intent: Dict, results: List[Dict]) -> None:
        max_price = intent.get("max_price")
        if max_price:
            try:
                prev = self.preferences.get("typical_budget")
                self.preferences["typical_budget"] = (
                    round(float(prev) * 0.6 + float(max_price) * 0.4)
                    if prev else float(max_price)
                )
            except (TypeError, ValueError):
                pass
        raw_prefs = intent.get("preferences", "")
        tokens  = raw_prefs.split() if isinstance(raw_prefs, str) else list(raw_prefs or [])
        kws     = intent.get("keywords", "")
        tokens += kws.split() if isinstance(kws, str) else list(kws or [])
        tokens  = [t.lower() for t in tokens if len(t) > 3]
        existing = self.preferences.get("keywords", [])
        self.preferences["keywords"] = list(dict.fromkeys(tokens + existing))[:30]

    # ── Goals (long-horizon planning) ──────────────────────────────────────

    def add_goal(
        self,
        description: str,
        keywords:    str,
        budget:      Optional[float] = None,
        deadline:    str = "",
    ) -> str:
        goal_id = f"G{str(int(time.time()))[-6:]}"
        self.goals.append({
            "id":          goal_id,
            "description": description,
            "keywords":    keywords.lower(),
            "budget":      budget,
            "deadline":    deadline,
            "created":     time.time(),
            "status":      "active",   # active | achieved | cancelled
        })
        self._save()
        return goal_id

    def get_active_goals(self) -> List[Dict]:
        return [g for g in self.goals if g.get("status") == "active"]

    def achieve_goal(self, goal_id: str) -> None:
        for g in self.goals:
            if g["id"] == goal_id:
                g["status"]   = "achieved"
                g["achieved"] = time.time()
        self._save()

    def cancel_goal(self, goal_id: str) -> None:
        for g in self.goals:
            if g["id"] == goal_id:
                g["status"] = "cancelled"
        self._save()

    def match_goals(self, products: List[Dict]) -> List[Dict]:
        """
        Tag products that satisfy an active goal.
        Adds 'goal_match' key to matching product dicts (in-place).
        Returns list of (product, goal) pairs where goal is newly achieved.
        """
        active = self.get_active_goals()
        if not active:
            return []
        newly_achieved = []
        for product in products:
            name  = product.get("name", "").lower()
            price = product.get("price")
            for goal in active:
                goal_words = set(goal["keywords"].split())
                name_words = set(name.split())
                if goal_words & name_words:
                    budget_ok = (
                        not goal.get("budget")
                        or not price
                        or float(price) <= float(goal["budget"])
                    )
                    if budget_ok:
                        product["goal_match"] = goal["description"]
                        newly_achieved.append((product, goal))
                        break
        return newly_achieved

    # ── Read ───────────────────────────────────────────────────────────────

    def get_context(self, last_n: int = 5) -> str:
        parts: List[str] = []
        if self.preferences.get("typical_budget"):
            parts.append(f"Typical budget: ₹{int(self.preferences['typical_budget']):,}")
        if self.preferences.get("keywords"):
            parts.append(f"Interests: {', '.join(self.preferences['keywords'][:12])}")
        for k, v in self.preferences.items():
            if k not in ("typical_budget", "keywords", "alert_email"):
                parts.append(f"User preference — {k}: {v}")
        active = self.get_active_goals()
        if active:
            g_lines = ["Active goals:"] + [
                f"  • {g['description']}"
                + (f" (budget ₹{int(g['budget']):,})" if g.get("budget") else "")
                + (f" by {g['deadline']}" if g.get("deadline") else "")
                for g in active
            ]
            parts.append("\n".join(g_lines))
        if self.history:
            recent = self.history[:last_n]
            lines = ["Recent searches:"] + [f"  • {r.query}" for r in recent]
            parts.append("\n".join(lines))
        return "\n".join(parts)

    def get_similar_searches(self, topic: str) -> List[SearchRecord]:
        words = set(topic.lower().split())
        scored: List[tuple] = []
        for rec in self.history:
            overlap = words & set(rec.query.lower().split())
            if overlap:
                scored.append((len(overlap), rec))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:3]]

    def get_summary(self) -> List[Dict]:
        return [
            {"query": r.query, "count": len(r.results), "timestamp": r.timestamp}
            for r in self.history
        ]

    def clear(self) -> None:
        self.history.clear()
        self.preferences.clear()
        self.goals.clear()
        self._save()
