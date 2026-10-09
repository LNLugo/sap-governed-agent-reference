"""Step 4 check: prove scope enforcement against the sandbox, as pass/fail.

The EXPECTED tables below are written independently of config/portfolios.json,
so a mistake in the configuration shows up as a failure instead of being trusted.

Run: python step4_check.py
"""
import authz
from authz import AccessDenied, NOT_AVAILABLE, load_user

USERS = ["rep_a", "rep_b", "approver"]
CUSTOMERS = ["USCU-CUS24", "USCU-CUS02", "USCU-CUS21", "USCU-CUS01", "17100001"]

# Who should see which customer. True = allowed.
EXPECTED_CUSTOMERS = {
    "rep_a":    {"USCU-CUS24": True,  "USCU-CUS02": True,  "USCU-CUS21": False, "USCU-CUS01": False, "17100001": False},
    "rep_b":    {"USCU-CUS24": False, "USCU-CUS02": False, "USCU-CUS21": True,  "USCU-CUS01": True,  "17100001": False},
    "approver": {"USCU-CUS24": True,  "USCU-CUS02": True,  "USCU-CUS21": True,  "USCU-CUS01": True,  "17100001": True},
}

# Lookups by order number. Order 53 belongs to USCU-CUS24, order 8 to 17100001,
# order 79 to USCU-CUS21. 99999999 does not exist.
EXPECTED_ORDERS = [
    ("rep_a", "53", True),
    ("rep_a", "8", False),         # the indirect path: another customer's order by number
    ("rep_a", "79", False),
    ("rep_a", "99999999", False),  # does not exist: must look identical to out of scope
    ("rep_b", "79", True),
    ("rep_b", "53", False),
    ("approver", "8", True),
]


def attempt(fn):
    try:
        fn()
        return True, ""
    except AccessDenied as e:
        return False, str(e)


def main():
    failures = 0
    refusal_messages = set()

    print("1. Customer scope (sales orders, check before every call):\n")
    print(f"   {'':10}" + "".join(f"{c:>13}" for c in CUSTOMERS))
    for u in USERS:
        user = load_user(u)
        row = f"   {u:10}"
        for c in CUSTOMERS:
            allowed, msg = attempt(lambda: authz.sales_orders(user, c, top=1))
            if not allowed:
                refusal_messages.add(msg)
            ok = allowed == EXPECTED_CUSTOMERS[u][c]
            failures += not ok
            row += f"{('allow' if allowed else 'deny') + ('' if ok else ' FAIL'):>13}"
        print(row)

    print("\n2. Lookups by order number (filter after the call):\n")
    for u, so, expected in EXPECTED_ORDERS:
        user = load_user(u)
        allowed, msg = attempt(lambda: authz.sales_order(user, so))
        if not allowed:
            refusal_messages.add(msg)
        ok = allowed == expected
        failures += not ok
        print(f"   {u:9} order {so:>9}: {'allow' if allowed else 'deny ':5}  "
              f"expected {'allow' if expected else 'deny '}  {'PASS' if ok else 'FAIL'}")

    print("\n3. Refusals must not leak whether a record exists:\n")
    same = refusal_messages == {NOT_AVAILABLE}
    failures += not same
    print(f"   distinct refusal messages: {len(refusal_messages)}  {'PASS' if same else 'FAIL'}")
    for m in refusal_messages:
        print(f"   \"{m}\"")

    print("\n4. Last audit entries:\n")
    lines = authz.AUDIT_LOG.read_text().splitlines()[-6:]
    for line in lines:
        print(f"   {line}")

    print(f"\nRESULT: {'ALL PASSED' if failures == 0 else f'{failures} FAILURE(S)'}")


if __name__ == "__main__":
    main()
