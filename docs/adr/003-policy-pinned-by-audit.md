# ADR-003: A permission needs a witness, and some states permit only escalation

**Status:** accepted

D3–D11 taken as the reference patch's defaults. D5 and D6 confirmed on 2026-10-07.

## Context

The gate was covered by four rejection tests. Enumerating every proposal it can
receive — 12 scenarios × 64 claimed exception sets × 7 dispositions, 5,376 in
all — showed it admitted 32: the 12 gold answers, 10 escalations where gold
names a remedy, and 10 remedies gold does not accept.

| scenario | gold | also admitted |
|---|---|---|
| S03 | `request_credit_memo` | `release_within_tolerance`, `request_po_amendment` |
| S04 | `request_credit_memo` | `hold_pending_receipt` |
| S05 | `hold_pending_receipt` | `request_credit_memo` |
| S07 | `request_po_amendment` | `request_credit_memo` |
| S10 | `hold_pending_receipt` | `request_credit_memo` |
| S11 | `escalate` | `request_credit_memo` |
| S12 | `escalate` | `release_within_tolerance`, `request_credit_memo`, `request_po_amendment` |

Two of the ten release payment on a case gold blocks. None of this showed in the
suite: `auto_match` could be added to all six exception classes with 27 of 27
tests still passing.

The ten trace back to three causes.

1. `PRICE_VARIANCE` permitted `RELEASE_WITHIN_TOLERANCE`. A price variance is by
   definition outside tolerance. The cell predates ADR-002, which gave the
   inside-tolerance case its own state and left this one behind.
2. Four cells permitted a remedy that no scenario accepts as an answer:
   `PRICE_VARIANCE → REQUEST_PO_AMENDMENT`, `QUANTITY_OVER_INVOICED →
   HOLD_PENDING_RECEIPT`, `SHORT_RECEIPT → REQUEST_CREDIT_MEMO`, `PART_NOT_ON_PO →
   REQUEST_CREDIT_MEMO`. Each is defensible in some accounts-payable process.
   None has evidence behind it here: no tool tells the agent the new price was
   agreed, or that the balance will never ship.
3. The policy could not see direction. S12 is billed 12% *below* the PO. The
   engine reports a price variance, which is true, and the price remedies all
   assume the supplier overcharged.

## Decision

**No exception class permits a disposition that releases payment.**
`RELEASING = {AUTO_MATCH, RELEASE_WITHIN_TOLERANCE}` is declared in the taxonomy
and the rule is checked on the table itself, for every class, not scenario by
scenario. Releasing dispositions are reachable from the two clean states of
ADR-002 and nowhere else.

**A permitted remedy needs a witness.** Every remedy a row permits must be the
accepted answer of some scenario that isolates that row. A cell without one is
either removed or given a witness; it is not left in place because it sounds
reasonable. The four cells above are removed. `Gold.also_acceptable` exists for
the day a scenario has two right answers; it is empty for all twelve.

**Some states permit only escalation.** `EscalateOnly` holds states in which no
remedy is supportable. They follow ADR-002's reasoning for the absorbed state:
computed from the case, never claimed by the agent, selecting no remedy, needing
no evidence beyond what the deterministic comparison returns. So they are states
and not exception classes, and the agent's vocabulary does not change.

| state | raised when |
|---|---|
| `under_billed` | a unit price is below the PO price by more than tolerance |
| `po_number_mismatch` | invoice or receipt cites a different PO |
| `currency_mismatch` | invoice and PO are in different currencies |
| `supplier_mismatch` | invoice is from a different supplier than the PO |
| `receipt_mismatch` | a receipt line cites an unknown PO line, or a different part or unit |

**One way in.** `permitted_dispositions(case)` in `tools/match.py` is the only
caller of `permitted_for` inside the package. The gate, the baseline and the
audit all reach the policy through it, so none of them can leave a state out. A
test reads the source tree to hold that.

## Consequences

On the twelve scenarios the gate now admits the gold answer and escalation, and
nothing else: 22 of 5,376.

Every row is left with exactly one remedy. That makes the gate, not the agent,
the thing that picks the remedy: once the exception set is verified, the only
choice the agent still makes is remedy or escalate. This is a finding about the
PoC's scope and is recorded in `docs/LIMITATIONS.md`, not softened. Giving the
agent a real choice between two remedies needs evidence that distinguishes them
and a scenario where each is right — a tool and a witness, which is corpus work.

The agent cannot see what raises three of the states. `get_invoice` does not
return the invoice's PO number, supplier or currency. A case with mismatched
headers is therefore refused at the gate rather than resolved by the agent,
which is the safe direction. Showing those fields to the model changes the task
it is measured on and is deliberately not done here.

The under-billing rule is conservative: one under-billed line makes the whole
invoice escalate-only, even if another line is overcharged.

## What would make us revisit

A process owner who wants one of the four removed cells back. The route is a
scenario whose gold accepts it and, if the choice depends on a fact, a tool that
returns the fact. Or a decision that under-billing deserves its own exception
class, which changes the system prompt and makes earlier live results
incomparable.

## Decisions recorded

D5 and D6 were confirmed on 2026-10-07. The others were taken as the
reference defaults. Each was exercised by a fail-first run recorded in the
log of `docs/WBS-GA.md`. D7, D8 and D10 concern the engine, not the policy
table, and are recorded here so that all nine are in one place.

| # | Decision | Taken | Why | Held by |
|---|---|---|---|---|
| D3 | Which dispositions release payment | `auto_match` and `release_within_tolerance` | every other disposition stops the invoice until a person or the supplier acts | `RELEASING`; `check policy` |
| D4 | `price_variance → release_within_tolerance` | removed | a price variance is outside tolerance by definition; the cell predates ADR-002 | `check policy` |
| D5 | Four remedy cells no scenario accepts | all four removed | one reason for all four: no tool returns the fact that says when the remedy applies | `check witness` |
| D6 | Under-billing | a state that permits only escalation, not a seventh class | computed from the case, never claimed; the agent's vocabulary and the model surface do not change | `tests/test_escalate_only.py`; the surface digest |
| D7 | Tolerance rounding | not rounded to cents | the rule as written is 2% of the PO unit price; rounding moves the band at prices such as 33.33 | `TOLERANCE_EDGES`; `check tolerance` |
| D8 | Several invoice or receipt lines against one PO line | summed per PO line | partial deliveries and split billing are ordinary; letting the last line win changed conclusions on 4/12 and 6/12 scenarios | `check variants` |
| D9 | Mismatched PO number, currency or supplier | three states that permit only escalation | the documents are not about the same order, or no price comparison between them means anything | `check fields`; `tests/test_escalate_only.py` |
| D10 | An invoice line billing a different part from the PO line it cites | `part_not_on_po` | the class already says the PO does not cover what is billed | `po_line_for`; `check fields` |
| D11 | A receipt line for an unknown PO line, a different part or a different unit | a state that permits only escalation | it is not evidence that the ordered goods arrived; ignoring the line would read as a short receipt | `check fields`; `tests/test_escalate_only.py` |
