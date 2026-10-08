"""Step 3 check: run the new tools against the sandbox before any model uses them.

Run: python step3_check.py
"""
import requests

from sap_tools import (BASE, ToolInputError, _headers, customer_position,
                       fetch_billing_documents, fetch_sales_order,
                       fetch_sales_orders, total_by_currency)

CUSTOMERS = ["USCU-CUS24", "USCU-CUS21", "17100001", "USCU-CUS02", "USCU-CUS01"]


def show_billing_fields():
    print("1. Billing document fields in the sandbox (check against _BD_FIELDS):")
    r = requests.get(f"{BASE}/API_BILLING_DOCUMENT_SRV/A_BillingDocument",
                     headers=_headers(), params={"$top": 1}, timeout=30)
    r.raise_for_status()
    rows = r.json()["d"]["results"]
    if not rows:
        print("   No billing documents returned.")
        return
    print("  ", sorted(k for k in rows[0] if not k.startswith(("__", "to_"))))


def show_orders():
    print("\n2. Sales orders per customer (latest 3) and position computed in code:")
    for cust in CUSTOMERS:
        orders = fetch_sales_orders(cust, top=3)
        pos = customer_position(cust)
        print(f"   {cust}: orders examined {pos.orders_examined} "
              f"({'complete' if pos.complete else 'PARTIAL: limit reached'}), "
              f"open orders {pos.open_orders}, "
              f"open value {pos.open_order_totals.by_currency}, "
              f"delivery blocks {pos.orders_with_delivery_block}")
        for o in orders:
            print(f"      order {o.sales_order} {o.created_on} {o.net_amount} {o.currency} "
                  f"delivery block {o.delivery_block.code if o.delivery_block else '-'} "
                  f"billing block {o.billing_block.code if o.billing_block else '-'}")


def show_blocked_orders():
    print("\n3. The two delivery-blocked orders from Step 0:")
    for so in ["8", "53"]:
        o = fetch_sales_order(so)
        print(f"   order {o.sales_order} customer {o.customer_id}: "
              f"delivery block {o.delivery_block}, billing block {o.billing_block}")


def show_billing():
    print("\n4. Last 5 billing documents and total, computed in code:")
    for cust in CUSTOMERS[:3]:
        try:
            docs = fetch_billing_documents(cust, top=5)
        except requests.HTTPError as e:
            print(f"   {cust}: billing call failed ({e.response.status_code}). "
                  f"Check the field names printed in section 1.")
            return
        print(f"   {cust}: {len(docs)} documents, total {total_by_currency(docs).by_currency}")


def show_input_validation():
    print("\n5. Input validation (both should be rejected before reaching SAP):")
    for bad in ["USCU-CUS24' or SoldToParty ne '", "../../etc"]:
        try:
            fetch_sales_orders(bad)
            print(f"   NOT rejected: {bad!r}  <-- defect")
        except ToolInputError as e:
            print(f"   rejected: {e}")


if __name__ == "__main__":
    show_billing_fields()
    show_orders()
    show_blocked_orders()
    show_billing()
    show_input_validation()
