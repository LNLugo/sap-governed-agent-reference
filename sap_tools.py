"""Typed, narrow tools over the S/4HANA Cloud sandbox APIs.

The model never writes OData. It can only call these functions, and each one
returns a small, typed result. Authorization checks are added here in Step 4.
"""
import os
from typing import Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
BASE = "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap"


def _headers():
    return {"APIKey": os.environ["SAP_SANDBOX_API_KEY"], "Accept": "application/json"}


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
    r = requests.get(
        f"{BASE}/API_BUSINESS_PARTNER/A_BusinessPartner('{business_partner_id}')",
        headers=_headers(),
        params={"$expand": "to_BusinessPartnerAddress"},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()["d"]
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


if __name__ == "__main__":
    import sys
    print(fetch_business_partner(sys.argv[1]).model_dump_json(indent=2))
