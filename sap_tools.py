"""Typed, narrow tools over the S/4HANA Cloud sandbox APIs.

Design rules (see README):
- The model never writes OData. It can only call these functions.
- Every input is validated before it reaches SAP.
- Every output is small and typed.
- Arithmetic is done here, in code, never by the model.
- Codes (block reasons, statuses) are returned as codes, with a description only
  when the description comes from SAP. The agent must never interpret them.

Authorization (account-portfolio scope) is added in Step 4.
"""
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
BASE = "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap"

# Business partner and document IDs in the sandbox look like "USCU-CUS24",
# "17100001" or "53". Anything else is rejected before it reaches SAP, which
# also prevents OData filter injection through the ID.
_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-]{1,20}$")


class ToolInputError(ValueError):
    """Raised when a tool receives an input it must not pass to SAP."""


def _validate_id(value: str, label: str) -> str:
    value = (value or "").strip()
    if not _ID_PATTERN.match(value):
        raise ToolInputError(f"Invalid {label}: {value!r}")
    return value


def _headers():
    return {"APIKey": os.environ["SAP_SANDBOX_API_KEY"], "Accept": "application/json"}


def _get(path: str, **params) -> dict:
    r = requests.get(f"{BASE}/{path}", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()["d"]


def _odata_date(value: Optional[str]) -> Optional[str]:
    """Convert OData V2 '/Date(1700000000000)/' to an ISO date string."""
    if not value:
        return None
    m = re.search(r"/Date\((-?\d+)", value)
    if not m:
        return value
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date().isoformat()


def _amount(value) -> Decimal:
    return Decimal(str(value)) if value not in (None, "") else Decimal("0")


# ---------------------------------------------------------------- Business partner

class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class BusinessPartner(BaseModel):
    business_partner_id: str
    name: Optional[str] = None
    category: Optional[str] = None
    addresses: list[Address] = []


def fetch_business_partner(business_partner_id: str) -> BusinessPartner:
    """Read one business partner and its addresses from the sandbox."""
    bp_id = _validate_id(business_partner_id, "business partner ID")
    d = _get(f"API_BUSINESS_PARTNER/A_BusinessPartner('{bp_id}')",
             **{"$expand": "to_BusinessPartnerAddress"})
    addrs = (d.get("to_BusinessPartnerAddress") or {}).get("results", [])
    return BusinessPartner(
        business_partner_id=d["BusinessPartner"],
        name=d.get("BusinessPartnerFullName"),
        category=d.get("BusinessPartnerCategory"),
        addresses=[
            Address(street=a.get("StreetName"), city=a.get("CityName"),
                    postal_code=a.get("PostalCode"), country=a.get("Country"))
            for a in addrs
        ],
    )


# ---------------------------------------------------------------- Sales orders

class BlockCode(BaseModel):
    """A block as SAP reports it. `description` is filled only from SAP data."""
    code: str
    description: Optional[str] = None


class SalesOrder(BaseModel):
    sales_order: str
    customer_id: str
    sales_organization: Optional[str] = None
    created_on: Optional[str] = None
    net_amount: Decimal
    currency: Optional[str] = None
    overall_delivery_status: Optional[str] = None
    delivery_block: Optional[BlockCode] = None
    billing_block: Optional[BlockCode] = None
    total_block_status: Optional[str] = None


_SO_FIELDS = ("SalesOrder,SoldToParty,SalesOrganization,CreationDate,TotalNetAmount,"
              "TransactionCurrency,OverallDeliveryStatus,DeliveryBlockReason,"
              "HeaderBillingBlockReason,TotalBlockStatus")


def _block(code: Optional[str]) -> Optional[BlockCode]:
    return BlockCode(code=code) if code else None


def _to_sales_order(d: dict) -> SalesOrder:
    return SalesOrder(
        sales_order=d["SalesOrder"],
        customer_id=d.get("SoldToParty", ""),
        sales_organization=d.get("SalesOrganization"),
        created_on=_odata_date(d.get("CreationDate")),
        net_amount=_amount(d.get("TotalNetAmount")),
        currency=d.get("TransactionCurrency"),
        overall_delivery_status=d.get("OverallDeliveryStatus"),
        delivery_block=_block(d.get("DeliveryBlockReason")),
        billing_block=_block(d.get("HeaderBillingBlockReason")),
        total_block_status=d.get("TotalBlockStatus"),
    )


def fetch_sales_orders(customer_id: str, top: int = 50) -> list[SalesOrder]:
    """The most recent sales orders for one customer (sold-to party), newest first.

    This is a preview: it returns at most `top` orders. Use fetch_all_sales_orders
    for anything that totals or counts.
    """
    cust = _validate_id(customer_id, "customer ID")
    top = max(1, min(int(top), 200))
    rows = _get("API_SALES_ORDER_SRV/A_SalesOrder",
                **{"$filter": f"SoldToParty eq '{cust}'", "$select": _SO_FIELDS,
                   "$orderby": "CreationDate desc", "$top": top})["results"]
    return [_to_sales_order(r) for r in rows]


_PAGE_SIZE = 100
_MAX_RECORDS = 2000


def fetch_all_sales_orders(customer_id: str) -> tuple[list[SalesOrder], bool]:
    """All sales orders for one customer, paged. Returns (orders, truncated).

    `truncated` is True only if the safety limit stopped paging before SAP ran
    out of records. Callers must report that, never present partial totals as complete.
    """
    cust = _validate_id(customer_id, "customer ID")
    orders: list[SalesOrder] = []
    skip = 0
    while True:
        rows = _get("API_SALES_ORDER_SRV/A_SalesOrder",
                    **{"$filter": f"SoldToParty eq '{cust}'", "$select": _SO_FIELDS,
                       "$orderby": "SalesOrder", "$top": _PAGE_SIZE, "$skip": skip})["results"]
        orders.extend(_to_sales_order(r) for r in rows)
        if len(rows) < _PAGE_SIZE:
            return orders, False
        skip += _PAGE_SIZE
        if skip >= _MAX_RECORDS:
            return orders, True


def fetch_sales_order(sales_order_id: str) -> SalesOrder:
    """One sales order by its number."""
    so = _validate_id(sales_order_id, "sales order")
    d = _get(f"API_SALES_ORDER_SRV/A_SalesOrder('{so}')", **{"$select": _SO_FIELDS})
    return _to_sales_order(d)


# ---------------------------------------------------------------- Billing documents

class BillingDocument(BaseModel):
    billing_document: str
    customer_id: str
    billing_date: Optional[str] = None
    net_amount: Decimal
    currency: Optional[str] = None
    is_cancelled: Optional[bool] = None


# Field names verified against the sandbox with step3_check.py (October 2026).
_BD_FIELDS = ("BillingDocument,SoldToParty,BillingDocumentDate,TotalNetAmount,"
              "TransactionCurrency,BillingDocumentIsCancelled")


def fetch_billing_documents(customer_id: str, top: int = 5) -> list[BillingDocument]:
    """Most recent billing documents for one customer, newest first."""
    cust = _validate_id(customer_id, "customer ID")
    top = max(1, min(int(top), 50))
    rows = _get("API_BILLING_DOCUMENT_SRV/A_BillingDocument",
                **{"$filter": f"SoldToParty eq '{cust}'", "$select": _BD_FIELDS,
                   "$orderby": "BillingDocumentDate desc", "$top": top})["results"]
    return [
        BillingDocument(
            billing_document=r["BillingDocument"],
            customer_id=r.get("SoldToParty", ""),
            billing_date=_odata_date(r.get("BillingDocumentDate")),
            net_amount=_amount(r.get("TotalNetAmount")),
            currency=r.get("TransactionCurrency"),
            is_cancelled=r.get("BillingDocumentIsCancelled"),
        )
        for r in rows
    ]


# ---------------------------------------------------------------- Deterministic calculations

class Totals(BaseModel):
    """Totals per currency. Amounts in different currencies are never added together."""
    count: int
    by_currency: dict[str, Decimal]


def total_by_currency(items: list, exclude_cancelled: bool = True) -> Totals:
    """Sum net amounts in code, grouped by currency. Works for orders and billing documents."""
    sums: dict[str, Decimal] = defaultdict(Decimal)
    counted = 0
    for it in items:
        if exclude_cancelled and getattr(it, "is_cancelled", False):
            continue
        sums[it.currency or "UNKNOWN"] += it.net_amount
        counted += 1
    return Totals(count=counted, by_currency=dict(sums))


class CustomerPosition(BaseModel):
    customer_id: str
    orders_examined: int
    complete: bool  # False means the safety limit was hit and figures are partial
    open_orders: int
    open_order_totals: Totals
    orders_with_delivery_block: list[str]
    orders_with_billing_block: list[str]


def customer_position(customer_id: str) -> CustomerPosition:
    """Order position for one customer: open orders, totals and blocks, all computed in code.

    'Open' means the overall delivery status is not 'C' (fully processed).
    Reads every order (paged), and says so explicitly if it could not.
    """
    orders, truncated = fetch_all_sales_orders(customer_id)
    open_orders = [o for o in orders if o.overall_delivery_status != "C"]
    return CustomerPosition(
        customer_id=customer_id,
        orders_examined=len(orders),
        complete=not truncated,
        open_orders=len(open_orders),
        open_order_totals=total_by_currency(open_orders),
        orders_with_delivery_block=[o.sales_order for o in orders if o.delivery_block],
        orders_with_billing_block=[o.sales_order for o in orders if o.billing_block],
    )


if __name__ == "__main__":
    import sys
    print(fetch_business_partner(sys.argv[1]).model_dump_json(indent=2))
