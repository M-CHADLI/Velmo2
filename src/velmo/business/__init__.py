"""Velmo 2.0 — Base métier e-commerce fictive (lecture seule)."""
from .tools import (
    TOOLS,
    get_customer_orders,
    get_discovered_email,
    lookup_order,
    set_business_identity,
)

__all__ = [
    "TOOLS",
    "lookup_order",
    "get_customer_orders",
    "set_business_identity",
    "get_discovered_email",
]
