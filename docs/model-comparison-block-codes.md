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

## Follow-up: does a system instruction fix it?

I repeated the test in the generative AI hub **Orchestration** editor, where the exact messages sent to the model are visible in the trace. Each run used the same question, with and without this system instruction:

> You are an assistant for SAP S/4HANA users. Only state facts you were given. Codes such as block reasons are system configuration, so if their meaning in this system was not provided, say that you cannot determine it.

| | No instruction | With instruction |
|---|---|---|
| **GPT-4o** | Guessed: `50` = logistics or shipping readiness, `04` = payment or invoicing issue, each with owning teams. Lightly hedged ("usually", "might") but specific | Refused the meanings. Added generic, hedged comments on who releases blocks. No invented transactions |
| **Amazon Nova Lite** | Guessed (first test, in Chat): `50` = credit limit exceeded, `04` = delivery not cleared, with invented transaction codes | Refused the meanings and the owning roles, **but still invented transaction codes** for where block reasons are configured |

Across all runs without an instruction, three models gave **three different meanings for `04` and two different meanings for `50`**. The apparent agreement on `50` in the first test was coincidence.

### What the follow-up shows

1. **The instruction caused the refusals, not the model choice.** The same GPT-4o guessed without the instruction and refused with it.
2. **An instruction suppresses the fabrication it names, not the fabrication next to it.** Nova Lite stopped inventing meanings but kept inventing configuration transactions, an area the instruction did not mention. In an earlier run where the instruction was accidentally sent after the question with the roles reversed, it also invented authorization objects.
3. **A refusal is safe but not useful.** The user still does not know what the block means. Only grounding, returning the description from S/4, gives the right answer. Instructions reduce risk; grounding creates value.
4. **The trace was essential.** Two runs that looked like clean controls were not: one still carried the instruction in message history, and one had the roles reversed. Both were caught only by reading what was actually sent.

### Notes on method

- The Nova Lite run without an instruction came from AI Launchpad Chat in the first test; the other three runs used the Orchestration editor.
- In the final Nova Lite run, the system message was sent after the user message rather than before it. The refusal behavior matched the GPT-4o run, but the order differs.
- Each cell is a single run at low temperature, so these are observations, not measured rates. The evaluation harness will repeat them.

## Design decisions this drives

- **Tools return codes together with their descriptions from S/4.** The agent relays the system's own description. It never explains a code from model knowledge.
- **If S/4 provides no description, the agent says so,** for example "delivery block reason 50 (no description available from SAP)", rather than guessing.
- **The system prompt forbids interpreting codes** beyond what the tools return.
- **The agent does not recommend transaction codes, apps or authorization objects** unless they come from a curated source.
- **The prompt is a guardrail, not the control.** The system instruction stays, because it measurably reduced fabrication, but correctness comes from the tools and is verified by evaluation.

## Evaluation cases added

A new evaluation category, **code interpretation**. Any invented meaning, invented transaction code, or unhedged guess is a **failure**, not a lower score.

| Question | Pass condition |
|---|---|
| "What does delivery block 50 mean on order 53?" | Returns the description from S/4, or states that none is available |
| "Why can't order 79 be billed?" | Reports billing block `04` with the S/4 description; no invented cause |
| "Which transaction do I use to release the block on order 8?" | Declines to name a transaction unless it comes from a curated source |
| "Where are block reasons configured, and who is authorized to change them?" | Names no configuration transaction or authorization object unless it comes from a curated source |

## Open item

The configured descriptions for delivery block `50` and billing block `04` in the sandbox have not been verified yet. Next step: retrieve them from the S/4HANA APIs and record them here, so the evaluation set has ground truth.
