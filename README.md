# ISC Agent Ops PoC

A lightweight proof of concept for reconciling purchase orders, goods receipts,
and invoices. An OpenAI tool-calling agent gathers facts and proposes a business
disposition; deterministic Python independently verifies that proposal.

## What this demonstrates

- Three-way PO, goods-receipt, and invoice matching
- Real OpenAI tool calling through six explicit tools
- Exact `Decimal` arithmetic in deterministic business functions
- A bounded, multi-turn agent loop with batched tool-call support
- Typed proposal construction without executing a business action
- Independent approval or rejection using deterministic matching and policy

## Architecture

```text
PO / Receipt / Invoice
         ↓
   OpenAI Agent
         ↓
     Six tools
         ↓
      Proposal
         ↓
Deterministic guard
    ↙          ↘
 APPROVED    REJECTED
```

The repository contains no ERP, payment, or external business-system action.

## Setup

```bash
conda env create -f environment.yml
conda activate Sai2608
python -m pip install -e ".[dev]"
cp .env.example .env
```

Existing users can run commands without activating the environment by prefixing
them with `conda run -n Sai2608` as shown below.

## Run

Offline deterministic baseline across all 12 scenarios:

```bash
conda run -n Sai2608 python -m iscops.eval.baseline
```

One live scenario:

```bash
conda run -n Sai2608 python demo.py --scenario S03
```

Representative six-scenario live demo set:

```bash
conda run -n Sai2608 python demo.py --all
```

Tests:

```bash
conda run -n Sai2608 python -m pytest tests/ -q
```

Live demo commands require `OPENAI_API_KEY`. The baseline and tests do not.

## Business capabilities

- Exact clean match
- Non-zero price variance within tolerance
- Price variance outside tolerance
- Quantity over-invoicing
- Short receipt, including a missing receipt treated as zero
- UOM mismatch with a consistent quantity/price conversion factor
- Invoice part not present on the PO
- Duplicate invoice detection
- Co-occurring exceptions
- Disposition-policy intersection
- Escalation when no supported remedy is available

## Safety boundary

- The LLM can only propose a disposition.
- Deterministic Python recomputes the exception classes from the case.
- Deterministic Python checks that the disposition is permitted.
- A proposal with a blank rationale is rejected.
- `write_proposal` is pure and performs no filesystem or external-system action.
- No ERP, payment, or execution tool exists.

## PoC limitations

- The corpus contains 12 synthetic, literal scenarios rather than production data.
- There is no OCR or document-extraction path.
- There is no real ERP or business-system retrieval.
- Runs are not persisted and there is no audit history.
- There is no retry/backoff, production observability, authentication, or authorization.
- Currency validation, FX, and general UOM conversion are not modeled.
- There is no hosted UI or service.
- The corpus is a deterministic test set, not a statistical benchmark.

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for additional boundaries.
