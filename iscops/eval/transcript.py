"""Render one runs/<trace_id>/ directory into a human-readable transcript.

    python -m iscops.eval.transcript <trace_id>   # one case
    python -m iscops.eval.transcript               # every case, latest run
"""
import json
import sys
from pathlib import Path

from iscops.config import RUNS_DIR
from iscops.corpus.scenarios import CASES, GOLD


def _qty(q, uom) -> str:
    return f"{q} {uom}" if q is not None else "—"


def _case_table(case) -> str:
    receipts = {ln.po_line_number: ln for ln in case.goods_receipt.lines}
    invoices = {ln.po_line_number: ln for ln in case.invoice.lines if ln.po_line_number is not None}
    rows = ["| Part | Ordered | Received | Invoiced | PO Price | Invoice Price |", "|---|---|---|---|---|---|"]
    for po in case.purchase_order.lines:
        inv, rc = invoices.get(po.line_number), receipts.get(po.line_number)
        rows.append(f"| {po.part_number} | {_qty(po.quantity, po.uom)} | "
                    f"{_qty(rc.quantity_received, rc.uom) if rc else '—'} | {_qty(inv.quantity, inv.uom) if inv else '—'} | "
                    f"${po.unit_price} | {'$' + str(inv.unit_price) if inv else '—'} |")
    for inv in case.invoice.lines:
        if inv.po_line_number is None:
            rows.append(f"| {inv.part_number} | — (not on PO) | — | {_qty(inv.quantity, inv.uom)} | — | ${inv.unit_price} |")
    return "\n".join(rows)


def render(run_dir: Path) -> Path:
    meta = json.loads((run_dir / "meta.json").read_text())
    case, gold = CASES[meta["scenario_id"]], GOLD[meta["scenario_id"]]
    steps = [json.loads(line) for line in (run_dir / "steps.jsonl").read_text().splitlines()]
    out = [f"# Case {case.scenario_id}", f"Model: {meta['model']} · Outcome: {meta['termination']}",
           "", "## The case", "", _case_table(case), "", "## What the agent did", ""]

    turns: dict[int, list[dict]] = {}
    for s in steps:
        turns.setdefault(s["index"], []).append(s)
    for i, calls in sorted(turns.items()):
        out.append(f"### Turn {i + 1}\nCalled " + ", ".join(f"`{c['tool']}`" for c in calls) + ".\n")
        for c in calls:
            body = f"error: {c['error']}" if c["error"] else "```json\n" + json.dumps(c["result"], indent=2) + "\n```"
            out.append(f"**{c['tool']}**\n{body}\n")

    out.append("## The proposal\n")
    proposal_path = run_dir / "proposal.json"
    if proposal_path.exists():
        p = json.loads(proposal_path.read_text())
        out.append(f"Disposition: **{p['disposition']}**\n"
                    f"Exception classes claimed: {', '.join(p['exception_classes']) or 'none'}\n"
                    f"Rationale: {p['rationale']}\n")
    else:
        out.append(f"No proposal was submitted (run ended: {meta['termination']}).\n")

    out.append("## The gate verdict\n")
    approval_path, rejection_path = run_dir / "approval.json", run_dir / "rejection.json"
    if approval_path.exists():
        a = json.loads(approval_path.read_text())
        out.append(f"**Approved.** Verified exception classes: {', '.join(a['verified_exception_classes']) or 'none'}.\n")
    elif rejection_path.exists():
        out.append(f"**Rejected.** {json.loads(rejection_path.read_text())['reason']}\n")
    else:
        out.append("No proposal reached the gate.\n")

    out += ["## Gold\n", f"Expected disposition: **{gold.disposition.value}**", f"Why: {gold.rationale}"]
    (run_dir / "transcript.md").write_text("\n".join(out))
    return run_dir / "transcript.md"


def _latest_per_scenario() -> list[Path]:
    best: dict[str, tuple[str, Path]] = {}
    for meta_path in RUNS_DIR.glob("*/meta.json"):
        meta = json.loads(meta_path.read_text())
        sid, start = meta["scenario_id"], meta["utc_start"]
        if sid not in best or start > best[sid][0]:
            best[sid] = (start, meta_path.parent)
    return [d for _, d in best.values()]


if __name__ == "__main__":
    targets = [RUNS_DIR / sys.argv[1]] if len(sys.argv) > 1 else _latest_per_scenario()
    for d in targets:
        print(render(d))
