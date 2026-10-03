"""Step 0: look at real sandbox data before writing any agent code.

Prints a sample of business partners and sales orders so you can pick the
five customers your evaluation set will use. Run: python explore_sandbox.py
"""
import os
from collections import Counter

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap"
HEADERS = {"APIKey": os.environ["SAP_SANDBOX_API_KEY"], "Accept": "application/json"}


def get(path, **params):
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["d"]["results"]


def main():
    orders = get("API_SALES_ORDER_SRV/A_SalesOrder", **{"$top": 100})
    if not orders:
        print("No sales orders returned. Check the API key and that the API is available in the sandbox.")
        return

    print("Fields available on a sales order header (check these names before using them):")
    print(sorted(k for k in orders[0] if not k.startswith("__") and not k.startswith("to_")))

    by_customer = Counter((o.get("SoldToParty"), o.get("SalesOrganization")) for o in orders)
    print("\nCustomers with the most orders, by sales organization:")
    for (customer, org), n in by_customer.most_common(15):
        print(f"  customer {customer:>12}  sales org {org:>6}  orders {n}")

    print("\nOrders that carry any block or credit status field (look for values):")
    block_fields = [k for k in orders[0] if "Block" in k or "Credit" in k]
    print("  block/credit fields:", block_fields)
    for o in orders:
        flagged = {k: o[k] for k in block_fields if o.get(k)}
        if flagged:
            print(f"  order {o.get('SalesOrder')} customer {o.get('SoldToParty')}: {flagged}")

    sample_ids = [c for (c, _), _ in by_customer.most_common(5)]
    print("\nBusiness partner records for the top customers:")
    for bp_id in sample_ids:
        bp = requests.get(f"{BASE}/API_BUSINESS_PARTNER/A_BusinessPartner('{bp_id}')",
                          headers=HEADERS, timeout=30)
        if bp.ok:
            d = bp.json()["d"]
            print(f"  {bp_id}: {d.get('BusinessPartnerFullName')} (category {d.get('BusinessPartnerCategory')})")
        else:
            print(f"  {bp_id}: not found as a business partner (HTTP {bp.status_code})")


if __name__ == "__main__":
    main()
