"""
Cart — in-session shopping cart and order model.
Stored in st.session_state so it persists across page navigations.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CartItem:
    name:     str
    price:    float
    image:    str
    rating:   float
    quantity: int = 1
    source:   str = ""
    link:     str = ""

    @property
    def line_total(self) -> float:
        return self.price * self.quantity


class Cart:
    GST_RATE       = 0.18   # 18 % GST
    SHIPPING_FLAT  = 49.0   # flat ₹49 shipping
    FREE_SHIP_MIN  = 499.0  # free above ₹499

    def __init__(self) -> None:
        self.items: List[CartItem] = []

    # ── Mutations ──────────────────────────────────────────────────────────

    def add(self, product: dict, qty: int = 1) -> None:
        name = product.get("name", "")
        for item in self.items:
            if item.name == name:
                item.quantity += qty
                return
        self.items.append(CartItem(
            name     = name,
            price    = float(product.get("price") or 0),
            image    = product.get("image", ""),
            rating   = float(product.get("rating") or 0),
            quantity = qty,
            source   = product.get("source", ""),
            link     = product.get("link", ""),
        ))

    def remove(self, name: str) -> None:
        self.items = [i for i in self.items if i.name != name]

    def set_qty(self, name: str, qty: int) -> None:
        for item in self.items:
            if item.name == name:
                item.quantity = max(1, qty)

    def clear(self) -> None:
        self.items.clear()

    # ── Queries ────────────────────────────────────────────────────────────

    def is_in_cart(self, name: str) -> bool:
        return any(i.name == name for i in self.items)

    def get_qty(self, name: str) -> int:
        for i in self.items:
            if i.name == name:
                return i.quantity
        return 0

    @property
    def count(self) -> int:
        return sum(i.quantity for i in self.items)

    @property
    def subtotal(self) -> float:
        return sum(i.line_total for i in self.items)

    @property
    def shipping(self) -> float:
        return 0.0 if self.subtotal >= self.FREE_SHIP_MIN else self.SHIPPING_FLAT

    @property
    def tax(self) -> float:
        return round(self.subtotal * self.GST_RATE, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.tax + self.shipping, 2)

    # ── Serialise to an order ──────────────────────────────────────────────

    def to_order(self, shipping_info: dict, payment_id: str) -> dict:
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        return {
            "order_id":    order_id,
            "items":       [
                {
                    "name":    i.name,
                    "price":   i.price,
                    "qty":     i.quantity,
                    "total":   i.line_total,
                    "image":   i.image,
                    "rating":  i.rating,
                    "source":  i.source,
                    "link":    i.link,
                }
                for i in self.items
            ],
            "subtotal":    self.subtotal,
            "tax":         self.tax,
            "shipping":    self.shipping,
            "total":       self.total,
            "shipping_info": shipping_info,
            "payment_id":  payment_id,
            "timestamp":   time.time(),
            "status":      "Confirmed",
        }
