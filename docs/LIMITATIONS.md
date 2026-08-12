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

The cost is real: there is no generator, so a scenario cannot be perturbed
systematically, and the corpus cannot grow without hand-writing each case.

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

## Single currency, single supplier, no FX

`currency` is carried on records and never checked. A cross-currency invoice would
pass the price comparison silently.

## The gate is stricter than a real one

`approve()` requires the agent's claimed exception set to match the deterministic
engine's exactly. A real gate would tolerate an agent that names a superset, or
that reports a class the engine missed. The strict form is chosen because a
disagreement is a finding worth stopping on, not noise to absorb.

## A UOM mismatch masks anything underneath it

`detect_exceptions` flags `UOM_MISMATCH` and stops evaluating that line. A line
that has both a UOM error and a real price error reports only the first. Correct
for the corpus; wrong in general.

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
