# SAP Governed Agent Reference

A reference architecture for a governed AI agent over SAP S/4HANA business APIs: typed tools, role-based scope, human approval for actions, and measured evaluation.

**Status: in progress.** This is a personal reference build against SAP's public S/4HANA Cloud sandbox. Identity and the final write-back are simulated; everything else is real and documented as it is built.

## The use case

A sales user asks plain-language questions about a customer (open orders, blocks, billing, contacts) and gets an answer grounded in live S/4HANA data, citing the business object IDs it used. The agent can request one action, release of a delivery block, which only proceeds after a human approver accepts it.

## Design principles

- **The model never writes OData.** It can only call narrow, typed tools.
- **Authorization lives in the tools, not the prompt.** Scope is checked before each SAP call and results are filtered after, so out-of-scope records never reach the model.
- **Arithmetic is done in code**, not by the model.
- **Codes come from the system, never from the model.** Block reasons and other codes are relayed with their descriptions from S/4. The agent never interprets them on its own (see findings below).
- **No action without approval.** Writes go to an approval queue, with idempotency and an audit entry.
- **Measured, not demoed.** A fixed evaluation set, safety gates treated as defects, and recorded accuracy, latency and cost.

## Findings so far

**The real data changed the design.** Exploring the S/4HANA Cloud sandbox ([output](docs/step0_output.txt)) showed every sampled sales order in a single sales organization, so scoping access by sales organization would test nothing. Access is scoped by **account portfolio** instead: each sales rep owns a set of customers, which is also closer to how account teams work. Billing blocks are common and delivery blocks rarer, so the approval-gated action is **release of a delivery block**.

**A sample is not the data.** The first exploration read 100 orders and found delivery blocks on only two. Reading every order showed one customer alone with 965 orders, 297 of them open and 48 delivery-blocked. An early version of the tools also capped results at 200 orders without saying so: for that customer it reported $57K in open orders when the true figure was $329K, understating it by about 83%. The tools now page through every record, and any position that hits the safety limit is flagged as partial rather than presented as complete.

**Models guess at SAP codes with full confidence.** In SAP generative AI hub, two models were asked what two S/4 block codes mean. Both answered as fact, they disagreed on one code, and one invented transaction codes. Block codes are system configuration, so neither could know. A follow-up in the orchestration service showed that a system instruction turns guessing into refusal, but a smaller model kept inventing configuration transactions the instruction didn't mention. Instructions reduce risk; only grounding gives the right answer. This drives the "codes come from the system" principle and a new evaluation category. [Full write-up](docs/model-comparison-block-codes.md)

**Refusals must not reveal what exists.** Access is checked before every SAP call, and again on what SAP returns, because a lookup by document number (a sales order) only reveals the customer after the read. Asking for another rep's order and asking for an order that does not exist produce the same refusal, so the scope cannot be probed by trying IDs. Every decision is written to an audit log, and a check script runs each role against each customer and order as a pass/fail matrix. Identity is simulated here; in production it comes from an XSUAA token, with principal propagation so S/4HANA applies its own authorizations as a second layer.

## Progress

- [x] Sandbox access and data exploration (`explore_sandbox.py`)
- [x] Typed Business Partner tool (`sap_tools.py`)
- [x] Model behavior test on S/4 codes in SAP generative AI hub ([write-up](docs/model-comparison-block-codes.md))
- [ ] Model access through SAP AI Core, Orchestration Service V2 (`hello_orchestration.py`): waiting on AI Core credentials
- [ ] Thin slice: one tool, one grounded answer, one trace (`thin_slice.py`): waiting on AI Core credentials
- [x] Sales order and billing tools (`sap_tools.py`)
- [x] Role-based scope enforcement (`authz.py`, `step4_check.py`)
- [ ] Approval queue and audited write-back
- [ ] Evaluation harness and results
- [ ] Architecture decisions, production notes and lessons learned

## Running it

```
python -m venv .venv
.venv\Scripts\activate        # Windows; use source .venv/bin/activate on Mac or Linux
pip install -r requirements.txt
copy .env.example .env        # then add your SAP Business Accelerator Hub API key
python explore_sandbox.py
```

Keys go in `.env`, which is excluded from version control.
