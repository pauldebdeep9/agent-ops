# isc-agent-ops

Agentic three-way match exception resolution. An agent reconciles purchase order
↔ goods receipt ↔ invoice, classifies exceptions, and **proposes** a disposition.
It never executes one.

Standalone by decision — imports nothing from `isc-docint`. See
[ADR-001](docs/adr/001-standalone-build.md).

## Run it

```bash
conda activate Sai2608
pip install -e ".[dev]"

make test        # 190 tests, no API key needed
make baseline    # deterministic engine vs gold across all 12 scenarios, no key
make audit       # the gate and the engine measured: seven checks, no key
make mutate      # one change at a time to gate, taxonomy and match; minutes, no key
make run         # the agent loop against a live model; needs OPENAI_API_KEY
make transcripts # render a human-readable transcript.md for the most recent run
```

`make baseline` is worth running first. If the deterministic engine disagrees with
gold, an agent failure tells you nothing.

## Shape

```
iscops/
  config.py            dotenv export into os.environ (pydantic-settings won't)
  domain/taxonomy.py   6 exception classes, 7 dispositions, 5 escalate-only states, what each permits
  domain/records.py    frozen models; Decimal money, explicit UOM, no confidence
  corpus/scenarios.py  12 scenarios with gold dispositions and rationales
  corpus/variants.py   the same case written another way: lines split, reversed, scaled, one field changed
  tools/match.py       deterministic three-way match — ground truth for the gate
  tools/registry.py    6 tools, exactly one not read-only
  agent/client.py      ~50-line chat client
  agent/loop.py        while over tool dispatch; typed termination
  approval/gate.py     the item that matters
  eval/                baseline (no LLM), runner, cli, transcript
  eval/gate_audit.py   every proposal the gate can receive, and the gate against its contract
  eval/engine_audit.py tolerance edges, case variants, which fields the engine reads
  eval/audit.py        the seven checks behind make audit
  eval/surface.py      everything the model is shown, as one digest
scripts/mutate.py      source-level mutation pass over gate, taxonomy and match
```

2,452 lines of Python under `iscops/` by `wc -l`, 782 of them the audits (`eval/gate_audit.py`, `eval/engine_audit.py`, `eval/audit.py`, `eval/surface.py`, `corpus/variants.py`). No agent framework: the loop is a `while` over tool dispatch, because
"I wrote the loop so I know where it fails" is a stronger position in an
architecture review than "we use LangGraph".

## What the gate does

An agent that proposes with a full audit trail is a fundamentally different
artefact from one that acts. `approve()` raises unless all of:

1. the proposal targets this case;
2. `get_po`, `get_receipt` and `get_invoice` were actually observed;
3. **the claimed exception classes match what the engine independently verifies**;
4. the disposition is permitted given those verified facts, and only escalation is permitted in five states the engine computes: under-billing, a mismatched PO number, currency or supplier, and a receipt that does not match the PO;
5. a rationale is present.

Check 3 is P1's citation finding transposed: *a citation that resolves is not a
citation that supports.* A proposal can name real exception classes, cite real
tool output, and still be wrong about what happened. The gate re-derives rather
than trusting the account.

Output is an `ApprovalRecord` carrying actor, UTC timestamp, disposition, evidence,
trace id, and the verified exception set alongside the claimed one. `applied` is
never set true by any code here.

## What has been measured about the gate

Before anything more is said about the agent, the gate and the engine were
measured on their own ([ADR-003](docs/adr/003-policy-pinned-by-audit.md),
[work breakdown](docs/WBS-GA.md)). `make audit` runs seven checks.
`tests/test_falsifiability.py` breaks each of them on purpose on every run,
so a check cannot quietly stop working.

| Measured | `main` (`fda9f00`) | now |
|---|---|---|
| Proposals the gate admits, of the 5,376 it can receive: 12 scenarios × 64 claimed exception sets × 7 dispositions | 32: 12 gold answers, 10 escalations, and 10 remedies gold does not accept, 2 of them releasing payment (S03, S12) | 22: 12 gold answers and 10 escalations |
| The gate against its five conditions, over 258,048 proposals | not checked | 0 disagreements |
| Scenarios whose conclusions change when one line is recorded as two | invoice lines 4/12 (S04, S05, S09, S10); receipt lines 6/12 (S01, S02, S03, S07, S08, S12) | 0/12 and 0/12 |
| Record fields the engine reads, of 27 | 12 | 23; the other 4 are identifiers |
| Single changes to gate, taxonomy and match that the suite catches | 68 of 132 | 166 of 167; the one left changes no result |
| Tests | 27 | 190 |

The mutation row was taken on a checkout of `main`. The other `main` readings
were taken on this branch with the fix reverted, because the instruments that
take them do not exist on `main`.

What the 27 tests could not see, each shown by making the change and running
them: `auto_match` permitted for a duplicate invoice; the tolerance floor
halved, `max` swapped for `min`, the band closed at its edge; invoice lines no
longer summed per PO line; the engine no longer reading the part number, or
the currency. All 27 stayed green under each one.

None of this is about the agent. 22 of 5,376 is what the gate would let
through, not what a model proposes. And with the unwitnessed cells removed,
every exception class is left with one remedy, so the gate picks the remedy
and the agent decides only between it and escalation. That, and the other
limits of the measurement, are in [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## The scenario worth knowing about

**S06** — PO in cases of 12 at $150.00, invoice in eaches at $12.50. Quantity
looks 12× over, unit price looks 92% under, and the extended amounts agree exactly
at $1,500.00. It is a data problem, nothing is owed either way, and the correct
disposition is a PO amendment. The obvious answer — a credit memo for
over-invoicing — is the wrong one.

## Results

`make run` (`gpt-4o-mini`, `temperature=0.0`) executed five times back to back,
unchanged, no prompt edits between runs.

k/12 per run: 6, 6, 7, 6, 7 — mean 6.4/12, range 6–7.

| scenario | run 1 | run 2 | run 3 | run 4 | run 5 | pass rate |
|---|---|---|---|---|---|---|
| S01 | PASS | PASS | PASS | PASS | PASS | 5/5 |
| S02 | FAIL | FAIL | FAIL | FAIL | FAIL | 0/5 |
| S03 | PASS | PASS | PASS | PASS | PASS | 5/5 |
| S04 | PASS | PASS | PASS | PASS | PASS | 5/5 |
| S05 | PASS | PASS | PASS | PASS | PASS | 5/5 |
| S06 | FAIL | FAIL | FAIL | FAIL | FAIL | 0/5 |
| S07 | PASS | PASS | PASS | PASS | PASS | 5/5 |
| S08 | FAIL | FAIL | FAIL | FAIL | FAIL | 0/5 |
| S09 | PASS | FAIL | PASS | FAIL | PASS | 3/5 |
| S10 | FAIL | PASS | PASS | PASS | PASS | 4/5 |
| S11 | FAIL | FAIL | FAIL | FAIL | FAIL | 0/5 |
| S12 | FAIL | FAIL | FAIL | FAIL | FAIL | 0/5 |

No percentage is given: n=12 cannot distinguish an 80% agent from a 90% one,
and five runs of the identical model, code, and prompt did not even agree with
each other on k/12. S02, S06, S08, S11, and S12 failed every run — findings
about the model. S09 and S10 did not — findings about the measurement. Detail
on both, and on the specific failure mechanisms, in
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).

These runs were taken on `main`, before the gate audit. The audit cannot
change a PASS or a FAIL in the table. A PASS is the gold answer, approved by
the gate; the gate still admits the gold answer on all 12 scenarios, and on
these scenarios it admits nothing it did not admit before. The table cannot
be regenerated from the repository, because `runs/` is not tracked in git.
Storing every trial is the next feature.

## Not built, deliberately

Nothing that moves money. No trade-compliance automation. No framework, no
guardrails layer, no UI. Full list and reasoning in
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).
