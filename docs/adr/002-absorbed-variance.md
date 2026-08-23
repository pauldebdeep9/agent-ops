# ADR-002: A price variance inside tolerance is a third state, not an exception

**Status:** accepted

## Context

`RELEASE_WITHIN_TOLERANCE` requires information that an empty exception set alone
cannot express. An empty set could mean either that every value matched exactly,
or that a non-zero price difference was accepted by policy.

## Decision

Distinguish three price states:

| State | Permitted dispositions |
|---|---|
| Nothing differed | `AUTO_MATCH`, `ESCALATE` |
| A difference was absorbed by tolerance | `RELEASE_WITHIN_TOLERANCE`, `ESCALATE` |
| A difference exceeded tolerance | Governed by `ExceptionClass` |

`absorbed_variance(case)` computes the middle state. It is not an
`ExceptionClass`: it selects no corrective remedy and needs no evidence beyond
the deterministic price comparison.

## Consequences

The gate can distinguish an exact match from a deliberate tolerance release.
Without this state, `RELEASE_WITHIN_TOLERANCE` would be unreachable or an exact
match could be mislabeled as a tolerated variance.
