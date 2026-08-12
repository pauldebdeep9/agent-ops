# ADR-002: A price variance inside tolerance is a third state, not an exception

**Status:** accepted

## Context

`RELEASE_WITHIN_TOLERANCE` was in the disposition enum from the start. Writing
`test_gold_dispositions_are_all_permitted` showed it was unreachable: a price
variance inside tolerance raises no exception, an empty exception set permitted
only `AUTO_MATCH` and `ESCALATE`, and so no case could ever legally be released
within tolerance. The enum was hiding a state the model did not have.

## Decision

Distinguish three clean states rather than two:

| state | permitted |
|---|---|
| nothing differed | `AUTO_MATCH`, `ESCALATE` |
| something differed, absorbed by tolerance | `RELEASE_WITHIN_TOLERANCE`, `ESCALATE` |
| something differed, outside tolerance | governed by `ExceptionClass` |

`absorbed_variance(case)` in `tools/match.py` computes the middle state. It is
not an `ExceptionClass`, because it selects no remedy and requires no evidence
beyond what the price comparison already returns.

## Consequences

The gate can now tell a clean match from an absorbed one, which is the difference
between "nothing to look at" and "we chose not to pursue $20". In an audit that
distinction is the whole point of having a tolerance policy at all.

Found by a test asserting an invariant across the corpus rather than by review —
consistent with P1, where the defects that mattered were invisible to every check
that existed and obvious the moment output met ground truth.
