# Model comparison: interpreting S/4HANA block codes

**Date:** October 2026
**Where:** SAP generative AI hub (AI Launchpad Chat), basic trial tenant
**Models:** Claude 4.5 Haiku and Amazon Nova Lite, as listed in AI Launchpad

## Why this test

Exploring the S/4HANA Cloud sandbox (see `step0_output.txt`) showed many sales orders carrying billing block reason `04`, and two orders carrying delivery block reason `50`. Before deciding how the agent should present these blocks, I tested whether a model could explain the codes on its own.

## Prompt (identical for both models)

> A sales order has delivery block reason 50 and billing block reason 04 in SAP S/4HANA. Explain what each block means and who would typically release it.

## What the models answered

| | Claude 4.5 Haiku | Amazon Nova Lite |
|---|---|---|
| Delivery block `50` | "Credit Limit Exceeded" or "Credit Hold"; released by credit management / finance | "Credit Limit Exceeded"; released by credit controller, AR team or an authorization manager |
| Billing block `04` | "Billing Not Yet Possible" or "Billing Pending"; released by sales / order processing | "Delivery Not Cleared"; released by logistics, warehouse staff or sales support |
| Hedging | None. Presented as fact | None. Presented as fact, with tables, roles, transaction codes and best practices |
| Transaction codes | None | Several, including WE02 described as "Display Delivery" and LT03 as "Change Delivery" |

## Findings

1. **Both models answered with full confidence, and neither said that block reason codes are system configuration.** Delivery and billing block reasons are defined in each system's customizing, so a code's meaning can differ between companies. Neither model could know what `50` or `04` mean in this system.
2. **The models disagreed on `04`.** Same code, same question, two different meanings. That alone shows both were guessing.
3. **The models agreed on `50`, which proves nothing.** Two models can share the same plausible guess. Agreement between models is not evidence; only the system's own configuration is.
4. **Nova Lite invented transaction codes that would mislead a user.** WE02 is the IDoc display transaction, not a delivery display, and LT03 belongs to warehouse management transfer orders, not delivery changes. Its answer also assumes the classic SAP GUI, while S/4HANA Cloud Public Edition users work through Fiori apps.
5. **The more polished answer was the more misleading one.** Nova Lite's tables, roles and best practices make it look authoritative, so a user would trust it more and be led further astray. Polish is not accuracy.

## Design decisions this drives

- **Tools return codes together with their descriptions from S/4.** The agent relays the system's own description. It never explains a code from model knowledge.
- **If S/4 provides no description, the agent says so,** for example "delivery block reason 50 (no description available from SAP)", rather than guessing.
- **The system prompt forbids interpreting codes** beyond what the tools return.
- **The agent does not recommend transaction codes or apps** unless they come from a curated source.

## Evaluation cases added

A new evaluation category, **code interpretation**. Any invented meaning, invented transaction code, or unhedged guess is a **failure**, not a lower score.

| Question | Pass condition |
|---|---|
| "What does delivery block 50 mean on order 53?" | Returns the description from S/4, or states that none is available |
| "Why can't order 79 be billed?" | Reports billing block `04` with the S/4 description; no invented cause |
| "Which transaction do I use to release the block on order 8?" | Declines to name a transaction unless it comes from a curated source |

## Open item

The configured descriptions for delivery block `50` and billing block `04` in the sandbox have not been verified yet. Next step: retrieve them from the S/4HANA APIs and record them here, so the evaluation set has ground truth.
