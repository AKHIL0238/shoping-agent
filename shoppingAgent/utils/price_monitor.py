"""
PriceMonitor — persistent price-watch list with automatic drop detection.

Watches are stored in .shopmind_watches.json in the project root.
Call check_all() on app load to detect drops and trigger email alerts.
"""
from __future__ import annotations
import json
import os
import time
from typing import Dict, List, Optional

_WATCH_FILE = os.path.join(os.path.dirname(__file__), "..", ".shopmind_watches.json")


class PriceMonitor:
    def __init__(self) -> None:
        self.watches: List[Dict] = []
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            path = os.path.abspath(_WATCH_FILE)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.watches = json.load(f)
        except Exception:
            self.watches = []

    def _save(self) -> None:
        try:
            path = os.path.abspath(_WATCH_FILE)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.watches, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Mutations ──────────────────────────────────────────────────────────

    def watch(self, product: dict, target_price: float, alert_email: str) -> None:
        """Start watching a product. Overwrites if already watched."""
        name = product.get("name", "")
        self.watches = [w for w in self.watches if w.get("name") != name]
        keywords = " ".join(name.split()[:6])
        self.watches.append({
            "name":           name,
            "keywords":       keywords,
            "original_price": float(product.get("price") or 0),
            "target_price":   float(target_price),
            "current_price":  float(product.get("price") or 0),
            "image":          product.get("image", ""),
            "link":           product.get("link", ""),
            "source":         product.get("source", ""),
            "alert_email":    alert_email,
            "added_at":       time.time(),
            "last_checked":   time.time(),
            "drop_detected":  False,
        })
        self._save()

    def unwatch(self, name: str) -> None:
        self.watches = [w for w in self.watches if w.get("name") != name]
        self._save()

    # ── Queries ────────────────────────────────────────────────────────────

    def is_watching(self, name: str) -> bool:
        return any(w["name"] == name for w in self.watches)

    def get_watch(self, name: str) -> Optional[Dict]:
        return next((w for w in self.watches if w["name"] == name), None)

    # ── Price check ────────────────────────────────────────────────────────

    def check_all(self, search_agent) -> List[Dict]:
        """
        Re-check prices for all watched products.
        Returns list of dicts describing price drops (each has new_price + drop_pct).
        Saves updated prices to disk.
        """
        drops: List[Dict] = []
        changed = False

        for watch in self.watches:
            try:
                products = search_agent.search_products(
                    keywords=watch["keywords"], max_results=6
                )
                for p in products:
                    # Fuzzy name match
                    wn = watch["name"][:25].lower()
                    pn = p["name"][:25].lower()
                    if wn in pn or pn[:len(wn)] == wn:
                        new_price = p.get("price")
                        if new_price:
                            old_price = watch["current_price"]
                            watch["current_price"] = float(new_price)
                            watch["last_checked"]  = time.time()
                            changed = True

                            if float(new_price) < old_price:
                                drop_pct = round((old_price - new_price) / old_price * 100)
                                drops.append({
                                    **watch,
                                    "new_price":    float(new_price),
                                    "old_price":    old_price,
                                    "drop_pct":     drop_pct,
                                    "drop_amount":  round(old_price - new_price),
                                })
                                watch["drop_detected"] = True
                        break
            except Exception:
                pass

        if changed:
            self._save()
        return drops
