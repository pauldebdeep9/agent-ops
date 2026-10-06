# Limitations

Started at item one, not at the end. Everything here is a known gap, not a bug.

## The agent loop has met a live model, and the results are unstable

**This is the most important entry.** `make run` was executed against
`gpt-4o-mini` at `temperature=0.0` seven times total: two initial passes, then
five more back to back, unchanged, no prompt edits between any of them. k/12
came back as 5, 7, 6, 6, 7, 6, 7. Two runs of the identical model, code, and
prompt disagreed by two full scenarios out of twelve. **Any claim about this
agent's capability requires repeated runs; a single k/12 number is one sample
from a distribution nobody has fully characterized, not a measurement.**

### Five failures are stable; two are not

Across the five-run set, S02, S06, S08, S11, and S12 failed **every single
run** — 0/5, and 0/7 counting the two earlier passes. These are findings about
the model. S09 (3/5) and S10 (4/5) are not stable — those are findings about
the measurement, and about how much a single run can mislead.

The original hypothesis for this entry was that the stable failures would
share "requires reasoning, not lookup." That doesn't survive the data: S03 (a
9.6% price variance), S04, and S05 (invoiced vs. received, a direct two-way
comparison) also require a judgment the tools don't make for you, and all
three passed 5/5. What the five stable failures actually share is narrower —
each requires either a judgment close to a boundary, synthesizing three or
more facts instead of two, reading a sign rather than a magnitude, or holding
two independent findings at once without one crowding out the other:

- **S02** — is a 1.6% variance inside "2% of PO price, floored at $0.50"?
  Requires computing the floor and comparing against it, not eyeballing a
  percentage the way S03's unambiguous 9.6% allows.
- **S06** — the UOM trap. Quantity ratio, price ratio, and extended-amount
  agreement all have to be read together to conclude "data problem, nothing
  owed." No single one of the three tells you that.
- **S08** — the invoice's own supplier invoice number has to be checked
  against `prior_invoice_numbers_on_this_po`, a second field from the same
  `get_invoice` call, for exact string equality. The model never once made
  this comparison across all 7 runs; every S08 failure proposed `auto_match`
  having claimed no exceptions existed at all.
- **S11** — two exceptions co-occur: an unreferenced invoice line, and zero
  units received. The model consistently caught the first and dropped the
  second, every run.
- **S12** — a 12% variance *below* the PO price. Every failure got the
  magnitude, the direction, or the tolerance boundary wrong.

### S02 (and, at least once, S12): a stuck loop, not a hard case

One persisted trace (`runs/23744e7fbb90/`, S02) shows exactly what
`budget_exhausted` means mechanically. After the two evidence-gathering turns,
the model re-called `compare_prices` and `compare_quantities` — the same two
argument-free tools, identical calls — **six more times**, verbatim, never
calling `write_proposal`, until the 8-turn budget ran out at **17 tool calls**
total. It had every fact it was going to get after turn 2; it just never
concluded. In the same run, S12 did the same thing independently (19 tool
calls, budget exhausted) — this is a repeatable failure mode on
boundary/direction judgments, not an S02 idiosyncrasy.

### The budget bounds turns, not tool calls

`step_budget` counts loop iterations (LLM turns), not individual tool calls.
The model usually batches — 9 of 12 scenarios in that same run dispatched the
canonical `get_po`+`get_receipt`+`get_invoice`, then
`compare_quantities`+`compare_prices`, then `write_proposal` shape (`[3, 2,
1]`, 6 tool calls in 3 turns), and S05 resolved in 4 turns with a slightly
different shape. A budget of 8 turns is generous in the model's favor when it
batches like this. It was irrelevant to S02 and S12's failures above, which
burned all 8 turns regardless of batching. Worth knowing before treating
`ISCOPS_STEP_BUDGET` as if it bounded agent effort directly: it bounds turns,
and turns and tool calls are not the same number.

### `no_progress` has never fired in a live run

`Termination.NO_PROGRESS` exists to catch a model that stops calling tools
without proposing anything. It has never fired outside the scripted-client
tests. S02 shows why that's not reassuring: a model that keeps calling tools
without ever converging exhausts the budget instead, and `budget_exhausted`
alone doesn't distinguish "ran out of room while making genuine progress"
from "looped." The turn-by-turn trace — `runs/<trace_id>/steps.jsonl`, or the
rendered `transcript.md` — is the only way to tell them apart.

### The write_proposal-batched-with-a-read bug is still live

`run_case` returns immediately on `write_proposal`; any tool call batched
*after* it in the same turn is silently never dispatched — never recorded,
never in evidence. This was flagged as a latent bug and instrumented for
across all seven live runs. It has not fired once: this model, on this
corpus, has never batched `write_proposal` with anything else. It remains
real and unexercised, not fixed.

## n=12 is a test suite, not a measuring instrument

Twelve scenarios cannot distinguish an 80% agent from a 90% one. Results are
reported as *k*/12 with failures named, never as a percentage. `runner.report()`
deliberately has no aggregate metric beyond the count.

## The corpus is written literally, not generated

No RNG, no seed, no PDF rendering — the twelve cases are Python literals. Determinism
is by construction rather than verified at the byte layer, which is a departure
from P1's convention. The trade: P1 spent three sessions with determinism checked
at the wrong layer because generated JSON was stable while the PDFs carried
wall-clock timestamps. Twelve literals have no such surface.

The cost is real: the corpus cannot grow without hand-writing each case.
`corpus/variants.py` now rewrites a case in ways that should change nothing —
lines reversed, quantities scaled, one line recorded as two — and changes one
field at a time. Only the engine is run on the results, never the agent. And
the variant check compares the engine with itself: its conclusions on the
rewritten case against its conclusions on the original. It reads no gold. A
variant's right answer is the original's only because the baseline separately
shows the engine agrees with gold on all 12.

## No extraction path

Records are JSON, not extracted from documents. P2 therefore tests nothing about
parsing, extraction or field-level confidence. This was a deliberate withdrawal:
running invoices through an extraction pipeline would add extraction noise to the
gold labels and reintroduce the circular-gold problem, where labels are asserted
from generation intent rather than derived from output.

## `isc-core` is unproven as substrate

P1's `common/` and `llm/` were designed as shared substrate. With P2 standalone
and P3 dropped, that design intent has never been exercised across a second
project. See ADR-001.

## The tolerance regime deviates from the original brief

The brief specified "2% or $50, whichever is greater" on unit price. Applied to a
unit price of $12.50 that is a 400% band, which would swallow every price variance
in the corpus and make S03 and S12 undetectable. Implemented as 2% floored at
$0.50, and flagged rather than routed around. $50 is an extended-amount threshold,
not a unit-price one.

The tolerance is not rounded to cents. 2% of $33.33 is $0.6666, so a
difference of $0.66 is inside the band and $0.67 is outside it. The rule is
held at six PO prices in `TOLERANCE_EDGES`, written by hand and computed from
nothing.

## Mismatched documents are refused, not resolved

The engine compares the PO number, supplier and currency across the
documents, and checks each receipt line against the PO line it cites. A
mismatch raises a state that permits only escalation (ADR-003). There is
still no FX: two currencies are told apart, never converted.

The agent cannot see what raises three of these states. `get_invoice` returns
no PO number, supplier or currency, and `get_receipt` returns no PO number, so
the agent has nothing to set against `get_po`. Nor does it see the refusal:
the gate runs in `eval/runner.py` after the loop has ended, and nothing under
`iscops/agent/` reads its verdict. A case with mismatched headers is refused
safely, and the agent can neither resolve it nor explain it. Showing those
fields changes what the model is shown, which is a decision for the
scenario-families work.

No scenario in the corpus raises a mismatch state. Each one is exercised by a
constructed case in `tests/test_escalate_only.py`, not by a scenario with gold.

## Every policy row has one remedy, so the gate picks it

With the four unwitnessed cells removed (ADR-003), each exception class
permits exactly one remedy, plus escalation. Once the exception set is
verified, the table fixes the remedy. The agent is left with one choice:
apply it or escalate. On this corpus the agent is therefore measured on
naming the exception set the engine verifies, and on choosing between the
remedy and escalation. It is not measured on choosing between remedies,
because the gate no longer offers that choice.

The four cells are a PO amendment for a price variance, a hold for
over-invoicing, a credit memo for a short receipt, and a credit memo for a
part not on the PO. Each is used by some accounts-payable process. They were
removed for one shared reason, not four: no tool returns the fact that says
when the remedy applies — that the new price was agreed, or that the balance
will never ship. Putting one back needs that tool, and a scenario whose gold
accepts it.

Of 5,376 proposals the gate admits 22: the gold answer on all 12 scenarios,
and escalation on the 10 whose gold is not escalation. S11 and S12 permit
escalation only.

## Under-billing escalates the whole invoice

A unit price below the PO price by more than tolerance raises `under_billed`,
which permits only escalation. One under-billed line does this for the whole
invoice, even if another line is overcharged and would on its own call for a
credit memo. The approval record stores the verified exception classes and
not the state, so an escalation forced by a state leaves no trace of which
state forced it. A rejection names the state only inside its message. Both
are for the trial ledger to fix.

## The gate is stricter than a real one

`approve()` requires the agent's claimed exception set to match the deterministic
engine's exactly. A real gate would tolerate an agent that names a superset, or
that reports a class the engine missed. The strict form is chosen because a
disagreement is a finding worth stopping on, not noise to absorb.

## A UOM mismatch masks anything underneath it

`detect_exceptions` flags `UOM_MISMATCH` and stops evaluating that line. A line
that has both a UOM error and a real price error reports only the first. Correct
for the corpus; wrong in general.

## Found by the audit and left as they are

- **No per-PO-line invoiced total in the tools.** The engine sums invoiced
  quantities per PO line. `compare_quantities` returns one row per invoice
  line. For 120 EA billed as two lines of 60 against a PO line of 100, each
  row reads as inside the order and the 120 appears nowhere. The gate refuses
  `auto_match`. The agent cannot see why.
- **Billing above the PO quantity is a clean match when the excess was
  received.** PO 100, received 120, invoiced 120 raises no exception and
  `auto_match` is permitted. Over-invoicing is defined against what was
  received. A process owner may want it measured against the order.
- **Earlier invoices carry numbers, not quantities.** A case holds the
  invoice numbers already seen on the PO and nothing else about them. The
  duplicate check works. Cumulative over-billing across invoices is invisible.
- **The rationale is checked for presence, not truth.** The gate rejects a
  blank rationale. Nothing checks that what it says is so.

## One mutant survives, and the mutation reading covers three files

`scripts/mutate.py` makes one small change at a time to `approval/gate.py`,
`domain/taxonomy.py` and `tools/match.py` — a comparison, a boolean, a
constant, a deleted statement, one cell of a policy set — and runs the whole
suite against each. On this branch 166 of 167 changes fail the suite. On
`main` at `fda9f00`, 68 of 132 did. The two counts are over different sets of
changes, because the three files differ between the trees. They are two
readings, not one reading that improved.

| | `main` | this branch |
|---|---|---|
| changes made | 132 | 167 |
| caught by the suite | 68 | 166 |
| policy cells: made, not caught | 56, 40 | 70, 0 |
| constants: made, not caught | 15, 11 | 18, 0 |

The one change left standing is `tools/match.py:53`, `delta > 0` to
`delta >= 0` in `price_state`. No test can catch it, because it changes
nothing: a zero difference returns `EXACT` earlier in the same function, so
that line never sees zero and the two comparisons agree on every value that
reaches it. Checked by running it: over 3,606 price pairs — the six PO prices
of the tolerance edge table, each against every whole-cent difference from
−3.00 to +3.00 — the changed function returns the same state as the original
on all 3,606.

What the reading does not cover:

- **Three files.** The instrument was pointed at the tools once
  (`--targets iscops/tools/registry.py`): 15 of 19 changes were caught. The
  four left standing are `frozen=True` on the `Tool` dataclass (line 22),
  `parents=True` and `exist_ok=True` where the run directory is created
  (line 178), and `"recorded": True` in the reply `write_proposal` returns
  (line 188). The loop ends on that call, so no model reads that reply. None
  of the four is closed here. The agent loop, the runner and the transcript
  writer have not been mutated at all.
- **Single changes, of a few kinds.** The operators are listed in the
  script's docstring. It does not reorder statements, change a string, or
  change two things at once. The order of the gate's five conditions is held
  by the contract check, not by this pass.
- **The falsifiability suite reaches the engine and the gate, not the
  tools.** `tests/test_falsifiability.py` breaks things by replacing module
  attributes. `tools/registry.py` binds `po_line_for` and
  `received_by_po_line` at import, so under those breaks the tools keep the
  working versions. The suite shows that each check can go red. It does not
  show the tools following the engine.
- **Not a score.** 166 of 167 says these three files are pinned by the
  tests. It says nothing about what a model proposes or how often it is
  right.

## Not built, deliberately

- **Nothing that moves money.** Exactly one non-read-only tool exists
  (`write_proposal`), it writes a dict, and there is no ERP write path or payment
  call anywhere — not even stubbed. `applied` on `ApprovalRecord` is never set
  true by any code in this repo.
- **No trade-compliance automation.** Export classification and denied-party
  screening are exactly the decisions that should not be delegated to a model
  proposing from an eight-step budget.
- No agent framework, no guardrails layer, no PII detection, no LLM-as-judge,
  no UI, no retry/backoff.
