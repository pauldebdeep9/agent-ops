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

make test        # 27 tests, no API key needed
make baseline    # deterministic engine vs gold across all 12 scenarios, no key
make run         # the agent loop against a live model; needs OPENAI_API_KEY
make transcripts # render a human-readable transcript.md for the most recent run
```

`make baseline` is worth running first. If the deterministic engine disagrees with
gold, an agent failure tells you nothing.

## Shape

```
iscops/
  config.py            dotenv export into os.environ (pydantic-settings won't)
  domain/taxonomy.py   6 exception classes, 7 dispositions, what each permits
  domain/records.py    frozen models; Decimal money, explicit UOM, no confidence
  corpus/scenarios.py  12 scenarios with gold dispositions and rationales
  tools/match.py       deterministic three-way match — ground truth for the gate
  tools/registry.py    6 tools, exactly one not read-only
  agent/client.py      ~50-line chat client
  agent/loop.py        while over tool dispatch; typed termination
  approval/gate.py     the item that matters
  eval/                baseline (no LLM), runner, cli
```

~700 LOC. No agent framework: the loop is a `while` over tool dispatch, because
"I wrote the loop so I know where it fails" is a stronger position in an
architecture review than "we use LangGraph".

## What the gate does

An agent that proposes with a full audit trail is a fundamentally different
artefact from one that acts. `approve()` raises unless all of:

1. the proposal targets this case;
2. `get_po`, `get_receipt` and `get_invoice` were actually observed;
3. **the claimed exception classes match what the engine independently verifies**;
4. the disposition is permitted given those verified facts;
5. a rationale is present.

Check 3 is P1's citation finding transposed: *a citation that resolves is not a
citation that supports.* A proposal can name real exception classes, cite real
tool output, and still be wrong about what happened. The gate re-derives rather
than trusting the account.

Output is an `ApprovalRecord` carrying actor, UTC timestamp, disposition, evidence,
trace id, and the verified exception set alongside the claimed one. `applied` is
never set true by any code here.

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

## Not built, deliberately

Nothing that moves money. No trade-compliance automation. No framework, no
guardrails layer, no UI. Full list and reasoning in
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).
