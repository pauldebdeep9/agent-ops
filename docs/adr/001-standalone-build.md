# ADR-001: Build P2 standalone

**Status:** accepted

## Context

P1 (`isc-docint`) built `common/` (confidence, tracing, ids, config), `llm/`
(provider port, structured output, schema hardening, cost) and `models/` as
intended shared substrate. P3, which would have consumed them, has been dropped.
The options for P2 were: import from the installed P1 package, vendor minimal
copies, or write its own.

## Decision

P2 is standalone. It imports nothing from `isc-docint` and does not declare it as
a dependency.

The primary goal of P2 is my own understanding of agentic control flow, and the
substrate I would import is the layer I most need to have written. The strongest
argument for importing was `llm/`'s strict-mode schema hardening — OpenAI
structured outputs require `additionalProperties: false` on every object
including `$defs`, and every property in `required`, neither of which Pydantic
emits. That argument does not apply: an agent loop uses **tool calling**, where
strict mode is optional and the schemas are ordinary JSON Schema written by hand.
The problem never arises, so the reason to import it dissolves.

## Consequences

**Accepted:**
- ~80 LOC of rebuilt foundation: a dotenv export (`iscops/config.py`) and a
  ~50-line chat client (`iscops/agent/client.py`).
- Two known problems must be re-solved rather than inherited: exporting `.env`
  into `os.environ`, and token accounting.
- P2 has no confidence concept anywhere. Its tools return exact arithmetic, and
  judgment is the human approver's. P1's second defect was a confidence signal
  meaning the opposite of what its consumer assumed; the cheapest defence against
  repeating it is not having the field.

**Declined, with reasons:**
- `isc.common.confidence` — no probabilistic surface in P2.
- `isc.common.tracing` — the audit record *is* P2-04, the item that matters most.
  Importing someone else's span writer to build the artefact that gets a pilot
  past governance is backwards.
- `isc.models` — ACL-bearing chunks solve a retrieval problem P2 does not have.

**Given up:** cross-repo reuse was the only remaining evidence that `isc-core` is
real substrate rather than a folder named optimistically. That claim is now
unproven and is recorded as such in `docs/LIMITATIONS.md`. Two independent
projects with genuinely different architectures is a cleaner story than one
project quietly depending on another, and half-importing would have been the
worst of both.

**Gained:** P2 cannot destabilise P1. Under an editable install, every change to
`isc.common` for P2's benefit would have put P1's "reproducible from a clean
clone" claim at risk.

## What would make us revisit

A third project needing the same substrate, or P2 growing a structured-output
surface where schema hardening becomes load-bearing again.
