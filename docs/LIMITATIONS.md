# Limitations

This repository is a working AI proof of concept, not a production invoice
automation platform.

## Live model behavior is nondeterministic

Temperature zero does not guarantee identical model behavior. The deterministic
tools and approval gate remain stable, but the model may choose different tools,
arguments, exception claims, or dispositions between live runs.

## The budget bounds model turns

`step_budget` limits LLM turns rather than total tool calls. A single model turn
may request several tools, so total calls can exceed the budget value. A model
that repeatedly calls tools without proposing eventually ends as
`budget_exhausted`.

If `write_proposal` is followed by another call in the same batch, the loop
returns immediately after the proposal and does not execute the later call.

## The corpus is illustrative

The 12 scenarios are deterministic Python literals. They demonstrate selected
business cases and support regression tests, but they are not a statistical
benchmark and do not estimate real-world accuracy.

There is no OCR, PDF parsing, field extraction, confidence scoring, or connection
to a document-processing pipeline.

## Business rules are deliberately narrow

- Records contain currency, but currency equality and FX conversion are not checked.
- The examples use one supplier and do not model supplier-master validation.
- UOM handling recognizes only the demonstrated quantity/price factor where
  extended amounts agree; it is not a general conversion table.
- UOM mismatch takes precedence over price and quantity checks on that line, so a
  secondary issue can be masked until the UOM problem is corrected.
- Unit-price tolerance is 2% of PO price with a $0.50 floor. This intentionally
  replaces an ambiguous earlier unit-price interpretation of a $50 threshold.

## The deterministic gate is intentionally exact

The proposal's exception set must exactly equal the independently detected set.
The disposition must be permitted for those verified exceptions and the rationale
must be nonblank. A production review process might tolerate partial or additional
claims, but this PoC stops on any disagreement.

## No operational platform is implemented

- No ERP, payment, accounting, or workflow action exists.
- The tools operate only on in-memory scenario data.
- There is no persistent audit history.
- There is no authentication, authorization, multi-user operation, or hosted UI.
- There is no retry/backoff, production monitoring, PII handling, or compliance layer.
- There is no model-quality benchmark runner or automated repeated-run analysis.
