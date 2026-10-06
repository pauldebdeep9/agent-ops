# GA Work Breakdown — Gate audit

Working document for `isc-agent-ops`, feature #1 of the evaluation hardening:
measuring the deterministic gate and the match engine before anything is said
about the agent. Two halves. Hold a case still and enumerate every proposal the
gate can receive; then hold the proposal still and change the case in ways whose
effect is known. Design and rationale live in
`docs/adr/003-policy-pinned-by-audit.md`. Drop this at `docs/WBS-GA.md`.

**Target:** 10 items, 3–6 prompts each (43 prompts), ~1,000 LOC source + ~800
LOC tests, a 250-line script and one fixture. **Milestone:** GA-09 — every check is
broken on purpose inside the suite, and the mutation reading is taken again with
the instrument that took it at GA-00.

Features #2 (trial ledger) and #3 (scenario families) get their own documents.
This one changes nothing the model sees.

---

## Current state

| Layer | State |
|---|---|
| P2 on `main` (`fda9f00`): loop, six tools, gate, runner, persistence, transcripts | complete — 27 tests |
| Gate coverage | four rejection tests, one acceptance |
| Proposal space, `main` | 32/5,376 admitted — 12 gold, 10 escalations where gold names a remedy, 10 remedies gold does not accept, 2 of which release payment |
| Case space, `main` | billing one line as two changes the engine's conclusions on 4/12 scenarios; recording one receipt as two on 6/12; 15/27 record fields are never read, 4 of them identifiers |
| Mutation reading, `main` | killed 68/132 — policy cells 16/56, constants 4/15 |
| GA-00..GA-09 | reference implementation in `ga-reference.patch` (one commit, 26 files, applies to `fda9f00` with `git am`) — sandbox-verified on Python 3.11.17 and 3.13.16, pydantic 2.13.5, pytest 9.1.1; **not yet run on `Sai2608`** |
| Reference, after | 190 tests; 22/5,376 admitted, 0 findings; 23/27 fields read, the other 4 identifiers; killed 166/167 |
| Live eval, corpus growth | not started (features #2, #3) |
| Dev/test env | `Sai2608` |
| Branch | `feat/ga-gate-audit` off `main`; merged after GA-09 |

Every number in this document was produced by running code against `main` in a
sandbox. Treat each as a prediction to reproduce on `Sai2608`, not as a result.

---

## Two ways to run GA-01..GA-09

- **Build mode.** Run each item's prompts as written, with the patch as
  reference — "a reference implementation of the finished feature exists; read
  the parts for this item's files, write only this item's scope". The patch
  shows the *end* state. Where an item's intermediate state differs from it
  (the ratchet lists in GA-01 and GA-08, `classify()` before GA-05, `CHECKS`
  growing one entry at a time), this document is the authority.
- **Adopt mode.** In this order:
  1. GA-00 prompt 1 — preflight, and this document committed
  2. `git am .ga-ref/ga-reference.patch`
  3. verify — `make test` 190 passed, `make baseline` 12/12,
     `python -m iscops.eval.audit --strict` exits 0 with seven checks ok, and
     the surface digest GA-00 states
  4. the "before" mutation reading, against untouched `main`:
     `git worktree add --detach .ga-ref/before fda9f00`, then
     `python scripts/mutate.py --repo .ga-ref/before`, then
     `git worktree remove .ga-ref/before`

  After that run only the prompts marked *adopt* — verify, fail-first, review
  — plus GA-09's prompts 4–6, which are measurements on your machine. About 15
  prompts instead of 43. The red-before-green runs (GA-04, GA-05, GA-07, GA-08)
  cannot happen naturally in adopt mode; the item's fail-first list reproduces
  each one by reverting the fix. Where a fail-first names a ratchet list, read
  it as the identity test that replaced it.

GA-00's two instruments come from the patch unchanged in **both** modes. Build
mode extracts them with `git apply --include` (prompts 2–3); adopt mode gets
them from `git am`. **Never both:** once GA-00.2 and GA-00.3 are committed,
`git am` stops on files that already exist. Their readings on `main` are stated
below; a rewritten instrument gives readings nobody has predicted.

**No merge into `main` before GA-09, in either mode.** After `git am` the code
is ahead of README and LIMITATIONS, which still describe `main`: 27 tests, a
currency that is never checked.

The patch lives at `.ga-ref/ga-reference.patch`, excluded through
`.git/info/exclude` so it is never committed. It applies the default for every
decision below. It contains ADR-003 as a draft and no README or LIMITATIONS
edits — those are GA-09's, from your own readings (**not in patch**).

---

## Decisions — settle before the item each one gates

Debdeep's call on each. The default is what the patch does.

| # | Decision | Default (patch) | Gates |
|---|---|---|---|
| D1 | Names: prefix `GA`; `eval/gate_audit.py`, `eval/engine_audit.py`, `eval/audit.py`, `eval/surface.py`, `corpus/variants.py`; `make audit`, `make mutate`; `RejectionCode`, `RELEASING`, `EscalateOnly`, `permitted_dispositions`, `Gold.also_acceptable` | as listed | GA-00 |
| D2 | Mutation instrument: an in-repo script plus breaks inside the suite, vs `mutmut` / `cosmic-ray` | in-repo — the trust base is mostly module-level data (a policy table, two constants) that function-level tools do not reach, and it adds no dependency | GA-00 |
| D3 | Which dispositions release payment | `auto_match`, `release_within_tolerance` | GA-04 |
| D4 | `price_variance → release_within_tolerance` | remove — a price variance is outside tolerance by definition; the cell predates ADR-002 | GA-04 |
| D5 | Four remedy cells no scenario accepts (table below): remove each, or keep it and declare it acceptable on named scenarios | remove all four | GA-05 |
| D6 | Under-billing: a state that permits only escalation (agent vocabulary unchanged), vs a seventh exception class | state — ADR-002's reasoning applies; `SYSTEM` and earlier live results stay comparable | GA-06 |
| D7 | Tolerance is not rounded to cents (2% of 33.33 is 0.6666) | keep, and pin it | GA-03 |
| D8 | Several invoice or receipt lines against one PO line: sum per PO line, vs refuse the shape | sum — partial deliveries are ordinary | GA-07 |
| D9 | Mismatched headers — PO number, currency, supplier | three escalate-only states | GA-08 |
| D10 | An invoice line billing a different part from the PO line it cites | `part_not_on_po` — the class docstring already says so | GA-08 |
| D11 | A receipt line for an unknown PO line, a different part or a different unit | escalate-only `receipt_mismatch`, vs ignore the line so it counts as not received | GA-08 |

**D5, cell by cell**

| Cell | Admitted against gold on | If kept |
|---|---|---|
| `price_variance → request_po_amendment` | S03, S12 | add to `also_acceptable` on S03; S12 closes through D6 either way |
| `quantity_over_invoiced → hold_pending_receipt` | S04 | add on S04 |
| `short_receipt → request_credit_memo` | S05, S10, S11 | add on S05 and S10 |
| `part_not_on_po → request_credit_memo` | S07, S11 | add on S07 |

S11 carries both of the last two classes, and the policy intersects. Its
finding closes if *either* cell goes and stays if both are kept.

---

## Conventions

Same as `WBS-AGG.md`, with two additions:

- Each item is **3–6 prompts**. The last is always verify + fail-first + review.
- **Done when** is checkable by running something. Every item ends with real
  `pytest` output pasted, `make test`, `make baseline` and `make audit` green,
  and a line in the log.
- **Fail-first ×3 per item** — make the change, paste the red run, restore,
  paste green. Each item names its three.
- **Red before green** *(new)*. GA-04, GA-05, GA-07 and GA-08 each start by
  writing the check and running it against unchanged code. That red output is
  the finding: paste it into the log before fixing anything. A red run is never
  committed.
- **Ratchets** *(new)*. Where a check starts red on known findings, the test
  pins the findings as a named list that may only shrink. An entry leaves in
  the same commit as the decision that closes it. If a list would need a new
  entry, stop.
- Invariants asserted as identities (`admitted ⊆ acceptable ∪ {escalate}`,
  `unread == UNREAD_BY_DESIGN`) rather than numbers wherever possible.
- Results as **k/n with named scenarios, cells or fields** — never a
  percentage.
- **Stop** marks a decision: Claude Code stops and asks rather than choosing.
- Every command runs through `conda run -n Sai2608 …`, from the repo root, as
  `python -m …`.
- A prompt whose verify step is green ends with a commit `GA-0X.N: <summary>`.
  A red verify stops without committing.
- **The model surface does not move.** From GA-00 a fixture holds everything
  the model is shown; no item may change it.

**Status**, in each item's heading: ☐ not started · ◐ in progress · ☒ done · ⊘ dropped

### Prompt frame

```text
isc-agent-ops · GA-0X prompt N/M — <title>
Read first: docs/WBS-GA.md §GA-0X, docs/adr/003 (from GA-04 on).
Reference: .ga-ref/ga-reference.patch shows the finished feature. Read the
parts for the files below; write only this prompt's scope.
Goal: <one sentence>.
In scope: <files>. Do not edit anything else.
Must hold: <invariants from this item's Watch and Done when>.
Do: <the prompt line, expanded>.
Verify: conda run -n Sai2608 python -m pytest -q <paths> — paste the full output.
Stop after pasting. Do not start prompt N+1. If you hit a choice this
document or ADR 003 does not settle, stop and ask.
```

---

## GA-00 — Preflight and the two instruments ☒

**Priority** critical · **~330 LOC adopted** (+ fixture) · **Prompts** 3 · **Depends** none · **Stop** D1, D2 before prompt 2

**Files** `docs/WBS-GA.md`, `scripts/mutate.py`, `Makefile`,
`iscops/eval/surface.py`, `tests/test_surface.py`,
`tests/fixtures/model_surface.json`

**Prompts**
1. Preflight — branch `feat/ga-gate-audit` off `main` at `fda9f00`; `Sai2608`
   is Python 3.11 and `iscops.__file__` is inside this checkout;
   `.ga-ref/` is in `.git/info/exclude`; `make test` and `make baseline`
   pasted; this document committed as the branch's first commit
2. Mutation instrument — `git apply --include='scripts/mutate.py'` from the
   patch, unchanged; add `make mutate`; state in five lines what the script
   changes and how it checks itself; run it on the untouched tree and paste
   the table
3. Model surface — `git apply --include` for `iscops/eval/surface.py`,
   `tests/test_surface.py` and the fixture, unchanged, then stage them; print
   the digest; regenerate with `--write` and show `git diff` is empty

**Done when**
- [ ] `iscops.__file__` printed and under this checkout
- [ ] `make test`: 27 passed; `make baseline`: 12/12
- [ ] Mutation reading on untouched `main`: **killed 68/132, survived 64/132**
      — policy 40/56 survive, constants 11/15, canary killed
- [ ] Surface digest
      `1a627aec67eaf69a9e784498ee49d3753a7cba0c5b7fb8e40d8815284f96c241`;
      `--write` leaves the fixture byte-identical
- [ ] Fail-first: change one word of `SYSTEM` (surface test red); change
      `"0"` to `"0.00"` in `compare_quantities` (surface test red); in a
      scratch copy of the script, make the canary replace text that does not
      exist (the run must abort with "canary survived")

**Watch** `Sai2608` is shared with `isc-docint`, and the archive this was
built from was a folder named `isc-agent-ops copy`. If `iscops` resolves to
another folder, every reading here is about that folder. `python -m` from the
repo root puts the checkout first; a bare `pytest` does not.

**Watch** the script measures itself before it measures anything: the untouched
copy must pass, and a canary that guts `detect_exceptions()` must fail. A canary
that survives means the suite ran against some other copy.

**Watch** a different digest is not a failure to fix by regenerating. It means
`main` here differs from the tree the patch was built on. Find the difference
first.

**Patch** covers prompts 2–3. Build mode extracts the files as written above.
Adopt mode skips both prompts: `git am` brings the files, the digest is checked
after it, and the mutation reading is taken with `--repo` against a detached
checkout of `fda9f00`.

---

## GA-01 — Enumerate the proposal space ☒

**Priority** critical · **~215 LOC** (+~70 test) · **Prompts** 4 · **Depends** GA-00

**Files** `iscops/eval/gate_audit.py`, `iscops/eval/audit.py`, `Makefile`,
`tests/test_gate_audit.py`

**Prompts**
1. `gate_audit.py`: `claims()` — all 64 subsets of `ExceptionClass` in a fixed
   order; `proposal_space(case)` — 64 × 7 proposals with everything else held
   valid; `admits()` through the real `approve()`; `classify()` → `gold` /
   `escalation` / `finding`; `audit()` → `AuditReport`
2. `render()` — counts with denominators and every finding by name, no rate;
   `audit_violations()`; `audit.py` with `CHECKS = {"audit": …}`, `check()`,
   `main()` and `--strict`; `make audit`
3. Tests: the space is the full product, asserted on the enum sizes; the gate
   admits no claim but the verified set; gold admitted on every scenario;
   escalate admitted on every scenario; **the ratchet** — `KNOWN_FINDINGS`,
   ten named pairs, asserted equal to the audit's findings
4. *adopt* — fail-first ×3, paste `make audit`, log line

**Done when**
- [ ] `make audit` prints `admitted 32/5376`, gold 12/12, escalation instead of
      gold 10/12, findings 10 in 7/12 scenarios
- [ ] The ten, by name: S03 `release_within_tolerance`, `request_po_amendment`;
      S04 `hold_pending_receipt`; S05, S07, S10, S11 `request_credit_memo`;
      S12 `release_within_tolerance`, `request_credit_memo`,
      `request_po_amendment`
- [ ] `make audit` exits 0; `--strict` exits 1, and will until GA-06
- [ ] The 27 existing tests unmodified and green
- [ ] Fail-first: add `auto_match` to `PERMITTED[DUPLICATE_INVOICE]` (ratchet
      red naming S08, **the 27 stay green** — paste both); replace the
      claimed-vs-verified comparison in `approve()` with `if False` (the
      verified-set test red); delete one entry from `KNOWN_FINDINGS` (ratchet red)

**Watch** the audit goes through `approve()`, never through `permitted_for()`.
An audit that works out what the gate should admit is measuring itself.

**Watch** this measures the gate, not the agent. 32/5,376 says nothing about
what a model proposes. In the one pass stored under `runs/` (12 Aug), 7
proposals were approved and all 7 were gold. That number belongs to feature #2.

**Watch** `auto_match` can be added to all six exception classes on `main` and
the 27 tests stay green. The first fail-first is that fact, pasted.

**Patch** covers all of it in its end state: no `KNOWN_FINDINGS` (GA-06 deletes
it), `classify()` already knows `acceptable`, `CHECKS` has seven entries.

---

## GA-02 — The gate's five conditions, over every proposal ☐

**Priority** critical · **~100 LOC** (+~130 test) · **Prompts** 4 · **Depends** GA-01

**Files** `iscops/approval/gate.py`, `iscops/eval/gate_audit.py`,
`iscops/eval/audit.py`, `tests/test_gate_contract.py`

**Prompts**
1. `RejectionCode` — five members, declared in the order `approve()` checks —
   and `GateRejection(code, message)`; every message string unchanged, so the
   27 tests pass unmodified
2. `expected_rejection(case, proposal)` — README's five conditions as an
   independent function returning the first one broken, the three tool names
   written as literals; `full_proposal_space()` — claim × disposition × the 8
   subsets of the document tools × {this case, another} × {`"because"`, `""`,
   whitespace}; `contract_violations()`; register `contract`
3. Tests: per scenario, `approve()` agrees with `expected_rejection` on every
   proposal; every `RejectionCode` is produced by something; blank rationale
   rejected; `Proposal` neither coerces strings nor allows edits;
   `ApprovalRecord.applied` cannot be set; the mismatch and not-permitted
   messages asserted in full, as `approve()` words them at this commit
4. *adopt* — fail-first ×3, review

**Done when**
- [ ] 21,504 proposals per scenario, 258,048 in all, 0 disagreements — the
      count asserted on the enum sizes
- [ ] `{code of every rejection} == set(RejectionCode)`
- [ ] The 27 existing tests unmodified and green; suite time recorded (sandbox:
      this file takes about 4 s)
- [ ] Fail-first: replace the rationale check with `if False` (**the 27 stay
      green**; the contract test goes red on all 12 scenarios); replace
      `if missing:` with `if False`; move the evidence check above the case
      check (only the contract test notices)

**Watch** `expected_rejection` must not import `REQUIRED_EVIDENCE`. An oracle
that reads the constant it is checking agrees with any value of it. GA-09 sets
that constant to `()` and requires this check to go red.

**Watch** order is now part of the contract. A proposal that breaks two
conditions is reported under the first, in README's order.

**Watch** the code enum is for feature #2. `rejection.json` stores a sentence
today, and a ledger will need to count rejections by cause without parsing it.
Do not touch `persist_run` here.

**Patch** covers all of it.

---

## GA-03 — Tolerance at its edges ☐

**Priority** high · **~120 LOC** (+~75 test) · **Prompts** 4 · **Depends** GA-01 · **Stop** D7 before prompt 2

**Files** `iscops/tools/match.py`, `iscops/corpus/variants.py`,
`iscops/eval/engine_audit.py`, `iscops/eval/audit.py`, `tests/test_tolerance.py`

**Prompts**
1. `match.py`: `PriceState` (`exact`, `absorbed`, `over`, `under`),
   `price_tolerance(po_unit_price)`, `price_state(po, invoice)`;
   `detect_exceptions` and `absorbed_variance` read `price_state`, so the rule
   and the comparison each appear once in the module
2. `variants.py`: `repriced(case, po_unit_price, invoice_unit_price)` —
   single-line cases only. `engine_audit.py`: `TOLERANCE_EDGES`, six rows
   written by hand (3.75 → 0.50, 12.50 → 0.50, 25.00 → 0.50, 33.33 → 0.6666,
   100.00 → 2.00, 150.00 → 3.00); `tolerance_violations()` — at each edge and
   in both directions the largest whole-cent difference inside the band is
   absorbed and one cent more is a variance, checked on `price_state` and
   again through the engine on a repriced S03; register `tolerance`
3. Tests: the check is clean; the table has a row where the floor binds, one
   where 2% binds, one where they are equal; nine literal
   `(PO, invoice, state)` rows; the unrounded case; engine and `price_state`
   agree on every scenario line
4. *adopt* — fail-first ×3, review

**Done when**
- [ ] `tolerance_violations() == []`
- [ ] `grep -c "price_tolerance(" iscops/tools/match.py` is 2 — the definition
      and one call
- [ ] `make baseline` 12/12; surface test green
- [ ] Fail-first: floor `0.50` → `0.25`; `max` → `min`; `<=` → `<`. For each,
      paste two runs — `tests/test_all.py` alone (27 green: the old suite
      cannot see it) and `tests/test_tolerance.py` (red)

**Watch** on `main` any effective tolerance from $0.20 to $1.19 on the $12.50
part passes all 27 tests. The corpus pins the rule at two points — S02 at 0.20,
S03 at 1.20 — and every price-checked line is under $25, where the $0.50 floor
wins, so the 2% term never decides a scenario.

**Watch** the edge table is the oracle. Nothing in it is computed from the
constants; a table derived from `PRICE_TOLERANCE_PCT` agrees with any value of it.

**Watch** this pins the rule in the engine. Whether the *agent* reads a
boundary correctly is a live question and belongs to feature #3's sweeps.

**Watch** `delta > 0` → `delta >= 0` in `price_state` changes nothing: zero is
returned two lines earlier. It is the one survivor GA-09 expects.

**Patch** covers all of it.

---

## GA-04 — Release safety, on the table itself ☐

**Priority** critical · **~55 LOC** (+~30 test) · **Prompts** 3 · **Depends** GA-01 · **Stop** D3, D4 before prompt 2

**Files** `iscops/domain/taxonomy.py`, `iscops/eval/gate_audit.py`,
`iscops/eval/audit.py`, `tests/test_policy.py`, `tests/test_gate_audit.py`,
`tests/test_all.py` (one comment), `docs/adr/003-policy-pinned-by-audit.md`

**Prompts**
1. `RELEASING` in the taxonomy; `Admitted.releases_payment`, and `render()`
   marks a finding that releases payment; `policy_rows()`;
   `policy_violations()` — escalate in every row including the two clean
   states, no exception class permits a releasing disposition, every class
   permits a remedy, the two clean rows exactly as ADR-002 states them. Tests,
   including one that the gate never releases payment where gold blocks it.
   **Run against the unchanged table, paste the red output, do not commit**
2. **Stop** on D3, D4. Then remove `release_within_tolerance` from
   `PERMITTED[PRICE_VARIANCE]`; delete the two ratchet entries it closes;
   correct the stale comment in `test_permitted_intersects_rather_than_unions`;
   register `policy`; take ADR-003 from the patch as a draft
3. *adopt* — fail-first ×3, review

**Done when**
- [ ] Prompt 1's red run names `price_variance: permits
      release_within_tolerance, which releases payment`, and S03 and S12 as
      the scenarios it releases on
- [ ] After prompt 2: `policy_violations() == []`; `make audit` shows admitted
      30/5376, findings 8 in 7/12; the ratchet has 8 entries
- [ ] Releasing dispositions appear in the two clean rows and nowhere else
      (identity)
- [ ] `git diff main -- tests/test_all.py` is that one comment
- [ ] Fail-first: put `release_within_tolerance` back on `PRICE_VARIANCE`; add
      `auto_match` to `DUPLICATE_INVOICE`; remove `escalate` from `CLEAN_EXACT`
      (on `main` this last one survives the whole suite)

**Watch** structural, not per-scenario — the same reasoning as P1's ACL gate. A
scenario audit shows only what a scenario exercises. "No class permits a
releasing disposition" holds for cases nobody has written.

**Watch** this is the cell ADR-002 left behind. That ADR gave "differed, inside
tolerance" its own state; `PRICE_VARIANCE` went on permitting the release it no
longer describes.

**Patch** covers all of it. Adopt mode reproduces the red run with the first
fail-first.

---

## GA-05 — A permitted remedy needs a witness ☐

**Priority** critical · **~45 LOC** (+~20 test) · **Prompts** 4 · **Depends** GA-04 · **Stop** D5 before prompt 3

**Files** `iscops/corpus/scenarios.py`, `iscops/eval/gate_audit.py`,
`iscops/eval/audit.py`, `iscops/domain/taxonomy.py`, `tests/test_policy.py`,
`tests/test_gate_audit.py`, `tests/test_gate_contract.py` (one assertion), ADR-003

**Prompts**
1. `Gold.also_acceptable` — empty by default — and the `acceptable` property;
   `Admission.ACCEPTABLE`; `classify()` reads it
2. `witness_violations()` — every remedy a row permits must be accepted by a
   scenario that isolates the row: its verified set is that class alone, or
   for a clean row a clean scenario in that state. Test. **Run against the
   unchanged table, paste the red output, do not commit**
3. **Stop** on D5, cell by cell. Remove the cell, or keep it and add the
   disposition to `also_acceptable` on the named scenarios. Delete the ratchet
   entries each decision closes; register `witness`
4. *adopt* — fail-first ×3; ADR-003 records each cell's decision and reason

**Done when**
- [ ] Prompt 2's red run names four cells: `price_variance →
      request_po_amendment`, `quantity_over_invoiced → hold_pending_receipt`,
      `short_receipt → request_credit_memo`, `part_not_on_po →
      request_credit_memo`
- [ ] With the defaults: admitted 23/5376, findings 1 — S12
      `request_credit_memo` — and the ratchet has that one entry
- [ ] `witness_violations() == []`; `make baseline` 12/12 with S11 at
      `1 permitted`
- [ ] Fail-first: put `request_credit_memo` back on `SHORT_RECEIPT` (witness
      and ratchet red; the ratchet names S05, S10, S11); change S06's gold to
      `escalate` (the UOM remedy loses its witness); remove
      `hold_pending_receipt` from `SHORT_RECEIPT` (gold unreachable on S05, S10)

**Watch** D5 is a process-owner decision, not an engineering default. Each of
the four is a remedy some accounts-payable process uses. What they share here
is that nothing lets the agent tell when it applies: no tool says the new price
was agreed, or that the balance will never ship.

**Watch** with the defaults every row has exactly one remedy. The gate then
picks the remedy and the agent decides only remedy-or-escalate. That is a
finding about this PoC and goes into LIMITATIONS at GA-09 at full length. A real
choice needs a fact, a tool that returns it, and a scenario where each answer is
right — corpus work.

**Watch** `also_acceptable` on a scenario whose cell was removed changes
nothing (verified). It matters only where the cell stays.

**Watch** one message moves. GA-02 asserts S05's not-permitted rejection in
full, and it lists what is allowed. Removing `short_receipt →
request_credit_memo` shortens that list; update the assertion in the same
commit, and nowhere else.

**Patch** covers all of it with every cell removed. Any cell kept means build
mode for prompt 3.

---

## GA-06 — Under-billing: a state that permits only escalation ☐

**Priority** critical · **~85 LOC** (+~100 test) · **Prompts** 5 · **Depends** GA-03, GA-05 · **Stop** D6 before prompt 2 · **ADR** 003

**Files** `iscops/domain/taxonomy.py`, `iscops/tools/match.py`,
`iscops/approval/gate.py`, `iscops/eval/baseline.py`,
`iscops/eval/gate_audit.py`, `tests/test_escalate_only.py`,
`tests/test_gate_audit.py`, ADR-003

**Prompts**
1. ADR-003, the section on states — read the draft against ADR-002 and the
   rule at the top of `taxonomy.py` ("an exception class earns a slot only if
   it selects a different disposition or requires different evidence").
   **Stop** on D6
2. `EscalateOnly` with one member, `under_billed`; `ESCALATE_ONLY`;
   `permitted_for(classes, absorbed_variance=False, escalate_only=False)`,
   intersecting like any other row; `escalate_only_states(case)`;
   `permitted_dispositions(case)`
3. `approve()`, `baseline.py` and the audit's `expected_rejection` reach the
   policy through `permitted_dispositions(case)`; the not-permitted message
   names the state; a test that reads the source tree and finds exactly one
   caller of `permitted_for` inside `iscops/`
4. The ratchet is empty: delete `KNOWN_FINDINGS` and assert the identity — the
   gate admits nothing gold does not accept, other than escalation.
   `policy_rows()` gains the `escalate_only` row, pinned to exactly `{escalate}`
5. *adopt* — fail-first ×3; ADR-003 → accepted

**Done when**
- [ ] `make audit`: admitted 22/5376, gold 12/12, escalation instead of gold
      10/12, findings 0; `--strict` exits 0 for the first time
- [ ] S12 permits exactly its gold; no other scenario raises a state
- [ ] +1.50 and −1.50 on a $12.50 part are the same class and different states;
      −0.20 is absorbed, not escalated
- [ ] `under_billed ⇒ price_variance` on every case tested (identity)
- [ ] `git diff main -- iscops/agent/` is empty and the surface test is green —
      the agent's vocabulary did not change
- [ ] The 27 existing tests unmodified and green
- [ ] Fail-first: drop the `escalate_only` intersection in `permitted_for`
      (S12's finding returns); test `PriceState.OVER` where it should test
      `UNDER` (gold unreachable on S03, S09); call `permitted_for` from
      `baseline.py` (the one-caller test red)

**Watch** the defaults stay on `permitted_for` so the 27 tests pass unmodified.
The cost is that a caller can forget a flag — hence exactly one caller and a
test that counts them.

**Watch** conservative by construction: one under-billed line makes the whole
invoice escalate-only, even if another line is overcharged.

**Watch** D6 the other way changes `SYSTEM` and the `write_proposal`
vocabulary. The surface fixture goes red by design, and every earlier live
result is about a different task. Say so in the log if you take it.

**Watch** the approval record still carries only `verified_exception_classes`.
An escalation forced by a state leaves no trace of the state. That is the
ledger's schema to fix in feature #2.

**Patch** covers all of it, with `EscalateOnly` already holding GA-08's four
other members.

---

## GA-07 — Quantities belong to the PO line ☐

**Priority** high · **~165 LOC** (+~100 test) · **Prompts** 4 · **Depends** GA-06 · **Stop** D8 before prompt 2

**Files** `iscops/corpus/variants.py`, `iscops/eval/engine_audit.py`,
`iscops/eval/audit.py`, `iscops/tools/match.py`, `iscops/tools/registry.py`,
`tests/test_variants.py`, `tests/test_engine_edges.py`

**Prompts**
1. `variants.py`: `reversed_lines`, `scaled`, `split_invoice_lines`,
   `split_receipt_lines` — each returns a new case describing the same goods
   and the same money. `engine_audit.py`: `conclusions(case)`, `VARIANTS` (the
   four, plus both splits together), `variant_violations()`. Tests. **Run
   against the unchanged engine, paste the red output, do not commit**
2. **Stop** on D8. Then `received_by_po_line(case)` and per-PO-line invoiced
   totals in `detect_exceptions`; price stays a property of each invoice line;
   the unreachable `else` branch goes, with its proof in the commit message;
   `compare_quantities` reads `received_by_po_line`; register `variants`
3. Tests for the two named cases — 120 EA billed as 60 + 60 is still
   over-invoiced and `auto_match` is refused; 100 received as 50 + 50 is not
   short — for the tool, and `tests/test_engine_edges.py` (one unit ordered
   and billed with nothing received; `uom_factor` at zero)
4. *adopt* — fail-first ×3, review

**Done when**
- [ ] Prompt 1's red run: `split_invoice_lines` changes conclusions on 4/12
      (S04, S05, S09, S10); `split_receipt_lines` on 6/12 (S01, S02, S03, S07,
      S08, S12); both together on 2/12 (S04, S09); `reversed_lines` and
      `scaled_x3` on 0/12
- [ ] After prompt 2: 0/12 for all five; `make baseline` 12/12
- [ ] Surface test green — no tool payload moved for any of the twelve
- [ ] Fail-first: let the last receipt line win again; stop summing invoice
      lines per PO line; change `"0"` to `"0.00"` in `compare_quantities` — the
      surface test must be the one that goes red

**Watch** on `main`, 120 EA billed as two 60-EA lines against a 100-EA PO line
raises no exception and the gate approves `auto_match` at $250 over the PO. S05
loses its short receipt the same way.

**Watch** the dead branch. Reaching it needs invoiced > received, invoiced ≤
ordered and received ≥ ordered, which together say invoiced > invoiced.

**Watch** gold is inherited, not recomputed: a variant's right answer is the
original scenario's. That is what lets a corpus grow without the engine marking
its own work. `variants.py` is the start of feature #3's transform library —
keep it free of test-only imports.

**Watch** the tools show no per-PO-line invoiced total, so a split-line case is
refused at the gate rather than resolved by the agent. Adding the field moves
the model surface: feature #3's decision.

**Watch** billing above the PO quantity when the excess was received (PO 100,
received 120, invoiced 120) is still a clean match. The class's definition says
so; a process owner may not. Recorded in LIMITATIONS, not changed here.

**Patch** covers all of it.

---

## GA-08 — Fields the engine never reads ☐

**Priority** high · **~165 LOC** (+~130 test) · **Prompts** 6 · **Depends** GA-07 · **Stop** D9, D10, D11 — one before each of prompts 2, 3, 4

**Files** `iscops/corpus/variants.py`, `iscops/eval/engine_audit.py`,
`iscops/eval/audit.py`, `iscops/domain/taxonomy.py`, `iscops/tools/match.py`,
`iscops/tools/registry.py`, `tests/test_fields.py`,
`tests/test_escalate_only.py`

**Prompts**
1. `field_perturbations(case)` — every leaf field of every record changed, one
   field at a time; `field_reading()` — per field, on how many scenarios the
   change alters `conclusions`. Tests: all 27 leaf fields are perturbed, and a
   second ratchet — `KNOWN_UNREAD`, eleven findings by name — beside
   `UNREAD_BY_DESIGN`, the four identifiers. Paste the reading; commit green
2. **Stop** on D9. `po_number_mismatch`, `currency_mismatch`,
   `supplier_mismatch` join `EscalateOnly`; ratchet 11 → 4
3. **Stop** on D10. `po_line_for(case, invoice_line)` — the PO line a line
   bills, or `None` if it cites no line, an unknown line, or a line that
   ordered a different part; the engine and both compare tools ask through it;
   ratchet 4 → 2
4. **Stop** on D11. `receipt_mismatch`; ratchet 2 → 0 — delete `KNOWN_UNREAD`
   and assert the unread set equals `UNREAD_BY_DESIGN`; register `fields`
5. Tests: each state has a case that raises it and leaves the exception set
   alone; the gate refuses `auto_match` across currencies and names the state;
   a substituted part is `part_not_on_po`; an invoice line citing PO line 99
   is `part_not_on_po`; tools and engine agree on `on_po`
6. *adopt* — fail-first ×3, review

**Done when**
- [ ] Prompt 1's reading: 27 fields, 12 read, 15 never read — 4 identifiers and
      11 findings: `part_number` on all three line types; the PO number on all
      three documents; supplier and currency on PO and invoice; the receipt
      line's `uom`
- [ ] After prompt 4: 23 read, and never-read == `{MatchCase.scenario_id,
      GoodsReceipt.receipt_number, Invoice.invoice_id,
      InvoiceLine.line_number}` (identity)
- [ ] Every member of `EscalateOnly` has a case that raises it (identity over
      the enum); no scenario raises a mismatch state
- [ ] `make baseline` 12/12; surface test green
- [ ] Fail-first: match PO lines by line number only; drop the currency
      comparison; list `InvoiceLine.part_number` in `UNREAD_BY_DESIGN` (the
      check reports a field listed as unread that the engine reads)

**Watch** on `main` the three-way match never reads the part. An invoice line
billing a different part against PO line 1, same quantity and price, is a clean
match and `auto_match` is approved.

**Watch** the agent cannot see what raises three of these states:
`get_invoice` returns no PO number, supplier or currency. Such a case is
refused at the gate — the safe direction — and cannot be resolved by the agent.
Showing those fields moves the model surface: feature #3's decision, recorded
in LIMITATIONS.

**Watch** `UNREAD_BY_DESIGN` is pinned both ways. A field listed there that the
engine does read is reported too.

**Watch** line number 0. `main` tests `if inv.po_line_number` in the tools and
`is None` in the engine; they disagree for a PO line numbered 0. `po_line_for`
removes the difference.

**Patch** covers all of it in its end state: no `KNOWN_UNREAD`.

---

## GA-09 — Every check broken on purpose ☐ ← **MILESTONE**

**Priority** critical · **~130 LOC** test + docs · **Prompts** 6 · **Depends** GA-01..GA-08

**Files** `tests/test_falsifiability.py`, `README.md`, `docs/LIMITATIONS.md`,
this document's log

**Prompts**
1. `tests/test_falsifiability.py`: `BREAKS` — one deliberate break per entry
   in `CHECKS`, applied with `monkeypatch`; the identity
   `set(BREAKS) == set(CHECKS)`; each check must report a violation under its
   break
2. The policy table one cell at a time — every row × every disposition flipped,
   each noticed by `policy`, `witness` or `audit`; six changes to the tolerance
   constants, each noticed by `tolerance`
3. *adopt* — fail-first ×3 on this file, review
4. `make mutate` on the finished tree; paste the table beside GA-00's
5. Every survivor: closed by a test, or written into LIMITATIONS with its line,
   the change, and the argument for why it stands
6. README "What the gate does" and LIMITATIONS state the measured numbers —
   proposal space, fields and mutation, each before and after — as counts with
   denominators and names

**Done when**
- [ ] `set(BREAKS) == set(CHECKS)`, seven of each
- [ ] Every policy cell noticed — asserted as `len(rows) × len(Disposition)`,
      which is 9 × 7 with the defaults
- [ ] Mutation: 0 survivors in `policy` and `constant`; every other survivor
      named in LIMITATIONS with a reason. Sandbox reading on the reference:
      **killed 166/167**, the survivor being `delta > 0` → `delta >= 0`
- [ ] `python -m iscops.eval.audit --strict` exits 0 with seven checks ok
- [ ] No ratchet left: `grep -rn "KNOWN_" tests/` is empty
- [ ] Surface digest unchanged from GA-00
- [ ] Fail-first: delete one entry from `BREAKS` (the identity red); make a
      break a no-op (its test red); remove the `escalate_only` row from
      `policy_rows()` (the whole-table test red)

**Watch** fail-first shows a check can fail, once, to whoever was watching.
This file shows it on every run.

**Watch** the breaks reach the checks through module attributes. A check that
bound `PERMITTED` at import time would hold the old table and never notice —
which is what the second fail-first demonstrates.

**Watch** the mutation count is an instrument reading, not a score. 166/167 on
three files says those three files are pinned. It says nothing about the agent,
the loop, or how the tools word what they return.

**Watch** do not quote anything here as the system's accuracy. That number
belongs to feature #2.

**Feature done here.**

**Patch** covers prompts 1–2. Prompts 4–6 are yours in both modes.

---

## Order

```
GA-00 ─► GA-01 ─┬─► GA-02 ──────────────────────────────────────────┐
                ├─► GA-03 ─────────────┐                            │
                └─► GA-04 ─► GA-05 ────┴─► GA-06 ─► GA-07 ─► GA-08 ─┴─► GA-09
```

The critical path runs through GA-04 → GA-06, where the ten findings close.
GA-02 and GA-03 touch other files and can run alongside it.

---

## Verification ladder

Run at every item, cheapest first:

```bash
conda run -n Sai2608 make test        # everything; about 12 s by GA-09
conda run -n Sai2608 make baseline    # 12/12; never skip
conda run -n Sai2608 make audit       # the report; add --strict from GA-06
conda run -n Sai2608 python -m iscops.eval.surface   # the digest must not move
conda run -n Sai2608 make mutate      # GA-00 and GA-09 only; minutes
```

---

## Definition of done

1. GA-09's criteria met on `Sai2608`
2. ADR-003 accepted, with D3–D11 each recorded and reasoned
3. README and LIMITATIONS state measured numbers, including the finding that
   every row is left with one remedy
4. The audit and the falsifiability suite run inside `make test`, unskipped
5. The model surface is byte-identical to `main`

---

## What the next two features take from this one

- **#2, trial ledger:** `RejectionCode` (count rejections by cause),
  `Gold.acceptable` and `RELEASING` (grade an approved-but-wrong proposal by
  whether it released payment), `escalate_only_states` (record why only
  escalation was open), `surface.digest()` (stamp every run with what the model
  was shown).
- **#3, scenario families:** `corpus/variants.py` and `VARIANTS` (families with
  inherited gold), `TOLERANCE_EDGES` (the sweep's expected answers),
  `field_perturbations` (one-field-changed cases).

---

## Recorded, not built

Found while building the reference, deliberately left for a later feature:

- **What the model is shown.** No per-PO-line invoiced total, and no PO number,
  supplier or currency on the invoice. Each changes the model surface (#3).
- **Billing above the PO quantity when the excess was received.** Clean match
  today.
- **Earlier invoices against the same PO.** Only invoice numbers are carried;
  quantities already billed are not, so cumulative over-billing is invisible.
- **The rationale.** The gate checks that it is non-blank. Nothing checks that
  it is true.
- **Stale pointers on `main`.** `registry.py`'s docstring cites
  `tests/test_tools.py`, which does not exist (the patch corrects it). README
  says "~700 LOC" and its `eval/` line omits `transcript.py`.
- **The five-run results table in README** cannot be regenerated from `runs/`,
  which holds one pass. That is feature #2's first item.

---

## Log

| Date | Item | Prompts | Note |
|---|---|---|---|
| 2026-10-06 | GA-00..09 reference patch | — | Built in a sandbox against `main@fda9f00`. 190 tests; readings identical under Python 3.11.17 and 3.13.16. Mutation 68/132 → 166/167 killed. Found while building: the engine never reads `part_number`; 15/27 fields unread; line splitting changes conclusions on 4/12 and 6/12. Not yet run on `Sai2608`. |
| 2026-10-06 | adopt order corrected | — | The first version of this document said to commit GA-00's instruments and then `git am`. The patch creates those same files, so `git am` stops with "already exists in index" (reproduced). Adopt mode now applies the patch first and takes the before-reading with `--repo`. Also checked: re-running the patched gate on the 10 proposals stored under `runs/` (12 Aug) gives the same verdict on 10/10. |
| 2026-10-06 | GA-00 | adopt entry | Patch applied as `4f52f7f`; its patch id equals the patch file's (`3d24357b…`). On `Sai2608` (Python 3.11.15, pydantic 2.13.4, pytest 9.1.1): 27 passed on `main`, 190 on the branch; baseline 12/12 on both. Surface digest `1a627aec…f96c241`. Mutation on `main`: killed 68/132, survived 64/132 — 40/56 policy and 11/15 constant mutants surviving. |
| 2026-10-06 | GA-01 | adopt | Audit under `main`'s policy (five cells restored, escalate-only intersection off): admitted 32/5376, gold 12/12, escalation instead of gold 10/12, findings 10 in 7/12 — the ten named in §GA-01, S03 and S12 `release_within_tolerance` marked RELEASES PAYMENT. Now: admitted 22/5376, findings 0, seven checks ok. Fail-first: A `auto_match` on `DUPLICATE_INVOICE` — `test_all.py` 27 passed, `test_gate_audit.py` 3 failed naming `('S08', 'auto_match')`; B claimed-vs-verified check off — `test_all.py` 1 failed / 26 passed, `test_gate_audit.py` 3 failed incl. the verified-set test (1408/5376 admitted); C `escalate` removed from `CLEAN_ABSORBED` — `test_all.py` 27 passed, `test_gate_audit.py` 3 failed incl. escalate-on-every-scenario (S02). Each restored; 8 passed. |
| | | | |