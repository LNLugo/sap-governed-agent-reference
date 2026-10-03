# SAP Governed Agent Reference

A reference architecture for a governed AI agent over SAP S/4HANA business APIs: typed tools, role-based scope, human approval for actions, and measured evaluation.

**Status: in progress.** This is a personal reference build against SAP's public S/4HANA Cloud sandbox. Identity and the final write-back are simulated; everything else is real and documented as it is built.

## The use case

A sales user asks plain-language questions about a customer (open orders, blocks, billing, contacts) and gets an answer grounded in live S/4HANA data, citing the business object IDs it used. The agent can request one action, release of a delivery block, which only proceeds after a human approver accepts it.

## Design principles

- **The model never writes OData.** It can only call narrow, typed tools.
- **Authorization lives in the tools, not the prompt.** Scope is checked before each SAP call and results are filtered after, so out-of-scope records never reach the model.
- **Arithmetic is done in code**, not by the model.
- **No action without approval.** Writes go to an approval queue, with idempotency and an audit entry.
- **Measured, not demoed.** A fixed evaluation set, safety gates treated as defects, and recorded accuracy, latency and cost.

## Progress

- [x] Sandbox access and data exploration (`explore_sandbox.py`)
- [x] Typed Business Partner tool (`sap_tools.py`)
- [ ] Model access through SAP AI Core, Orchestration Service V2 (`hello_orchestration.py`)
- [ ] Thin slice: one tool, one grounded answer, one trace (`thin_slice.py`)
- [ ] Sales order and billing tools
- [ ] Role-based scope enforcement
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
