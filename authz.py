"""Step 4: account-portfolio scope around every SAP tool.

Three controls, in this order, on every call:
1. CHECK BEFORE: is the customer in the user's portfolio? If not, SAP is never called.
2. FILTER AFTER: every record SAP returns is checked again. This catches lookups by
   document number (for example a sales order), where the customer is only known
   after the record is read.
3. AUDIT: every decision, allowed or denied, is written to audit/access.jsonl.

Refusals are identical whether a record is out of scope or does not exist, so a
user cannot probe for other customers' data by trying IDs.

Identity is SIMULATED in the sandbox (see config/portfolios.json). In production,
UserContext would be built from a validated XSUAA token, and principal propagation
would let S/4HANA apply its own authorizations as a second, independent layer.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from pydantic import BaseModel

import sap_tools

CONFIG = Path(__file__).parent / "config" / "portfolios.json"
AUDIT_LOG = Path(__file__).parent / "audit" / "access.jsonl"

# One message for every refusal. Never reveal whether the record exists.
NOT_AVAILABLE = "That record is not available within your access scope."


class AccessDenied(Exception):
    """Raised to the agent. Its message is always NOT_AVAILABLE."""

    def __init__(self):
        super().__init__(NOT_AVAILABLE)


class UserContext(BaseModel):
    user_id: str
    role: str
    customers: Optional[frozenset[str]]  # None means all customers

    def can_see(self, customer_id: str) -> bool:
        return self.customers is None or customer_id in self.customers


def load_user(user_id: str) -> UserContext:
    """Simulated identity lookup. Replace with token validation in production."""
    users = json.loads(CONFIG.read_text())["users"]
    if user_id not in users:
        raise ValueError(f"Unknown user {user_id!r}")
    u = users[user_id]
    customers = None if u["customers"] == "*" else frozenset(u["customers"])
    return UserContext(user_id=user_id, role=u["role"], customers=customers)


def _audit(user: UserContext, tool: str, target: str, decision: str, reason: str = ""):
    AUDIT_LOG.parent.mkdir(exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "user": user.user_id, "role": user.role, "tool": tool,
             "target": target, "decision": decision, "reason": reason}
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _check_before(user: UserContext, tool: str, customer_id: str):
    if not user.can_see(customer_id):
        _audit(user, tool, customer_id, "denied", "customer outside portfolio")
        raise AccessDenied()


def _filter_after(user: UserContext, tool: str, target: str, records: list) -> list:
    """Drop any record outside scope. Should never trigger after a passed check-before;
    if it does, it is logged as an anomaly because something upstream is wrong."""
    kept = [r for r in records if user.can_see(r.customer_id)]
    dropped = len(records) - len(kept)
    if dropped:
        _audit(user, tool, target, "filtered", f"{dropped} out-of-scope records removed")
    return kept


# ---------------------------------------------------------------- Scoped tools

def my_customers(user: UserContext) -> list[str]:
    """The customers this user may ask about. The approver gets a note instead of a list."""
    _audit(user, "my_customers", "-", "allowed")
    return sorted(user.customers) if user.customers is not None else ["all customers"]


def business_partner(user: UserContext, customer_id: str) -> sap_tools.BusinessPartner:
    _check_before(user, "business_partner", customer_id)
    bp = sap_tools.fetch_business_partner(customer_id)
    _audit(user, "business_partner", customer_id, "allowed")
    return bp


def sales_orders(user: UserContext, customer_id: str, top: int = 20) -> list[sap_tools.SalesOrder]:
    _check_before(user, "sales_orders", customer_id)
    orders = _filter_after(user, "sales_orders", customer_id,
                           sap_tools.fetch_sales_orders(customer_id, top=top))
    _audit(user, "sales_orders", customer_id, "allowed")
    return orders


def sales_order(user: UserContext, sales_order_id: str) -> sap_tools.SalesOrder:
    """Lookup by order number: the customer is unknown until the record is read,
    so this relies on the filter-after control."""
    try:
        order = sap_tools.fetch_sales_order(sales_order_id)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            _audit(user, "sales_order", sales_order_id, "denied", "order does not exist")
            raise AccessDenied()
        raise
    if not user.can_see(order.customer_id):
        _audit(user, "sales_order", sales_order_id, "denied",
               "order belongs to customer outside portfolio")
        raise AccessDenied()
    _audit(user, "sales_order", sales_order_id, "allowed")
    return order


def billing_documents(user: UserContext, customer_id: str,
                      top: int = 5) -> list[sap_tools.BillingDocument]:
    _check_before(user, "billing_documents", customer_id)
    docs = _filter_after(user, "billing_documents", customer_id,
                         sap_tools.fetch_billing_documents(customer_id, top=top))
    _audit(user, "billing_documents", customer_id, "allowed")
    return docs


def customer_position(user: UserContext, customer_id: str) -> sap_tools.CustomerPosition:
    _check_before(user, "customer_position", customer_id)
    pos = sap_tools.customer_position(customer_id)
    _audit(user, "customer_position", customer_id, "allowed",
           "" if pos.complete else "partial result")
    return pos
