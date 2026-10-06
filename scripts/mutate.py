"""Source-level mutation pass over the deterministic trust base.

    python scripts/mutate.py                 # gate.py, taxonomy.py, match.py
    python scripts/mutate.py --out runs/mutation.json

Copies iscops/ and tests/ to a temporary directory, changes one thing at a
time, and runs the suite against each change. A change the suite does not
notice is a survivor. Survivors are listed; nothing is hidden in a score.

The instrument checks itself before it measures: the untouched copy must pass,
and a canary that guts detect_exceptions() must fail. If the canary survives,
the suite is not importing the mutated copy and every reading would be wrong.

Operators (the denominator depends on this list, so change it deliberately):
  cmp        >  >=  <  <=  ==  !=  in  not-in  is  is-not, each to its neighbours
  bool       and <-> or;  `not x` -> `bool(x)`
  arith      + <-> -;  * <-> /;  & <-> |   (binary and augmented)
  constant   D("x") -> x*2, x/2, 0;  D(n) -> D(n+1);  True <-> False
  call       max -> min
  delete     continue, raise, and set.add(...) statements replaced by pass
  policy     each Disposition added to or removed from each literal policy set
"""

import argparse
import ast
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

DEFAULT_TARGETS = (
    "iscops/approval/gate.py",
    "iscops/domain/taxonomy.py",
    "iscops/tools/match.py",
)
CMP = {
    ast.Gt: (ast.GtE, ast.Lt), ast.GtE: (ast.Gt,), ast.Lt: (ast.LtE, ast.Gt), ast.LtE: (ast.Lt,),
    ast.Eq: (ast.NotEq,), ast.NotEq: (ast.Eq,), ast.In: (ast.NotIn,), ast.NotIn: (ast.In,),
    ast.Is: (ast.IsNot,), ast.IsNot: (ast.Is,),
}
ARITH = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.BitAnd: ast.BitOr, ast.BitOr: ast.BitAnd,
}


def _replace_statement(tree: ast.AST, target: ast.AST) -> None:
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list):
                for i, statement in enumerate(block):
                    if statement is target:
                        block[i] = ast.Pass()


def _replace_expression(tree: ast.AST, target: ast.AST, new: ast.AST) -> None:
    class Swap(ast.NodeTransformer):
        def visit(self, node):  # noqa: N802
            if node is target:
                return new
            return self.generic_visit(node)

    Swap().visit(tree)


def mutants(tree: ast.AST, disposition_names: list[str]):
    """Yield (line, category, description, apply) for every mutation site.

    `apply` takes a deep copy of the tree; sites are addressed by position in
    ast.walk order, which a deep copy preserves.
    """
    for index, node in enumerate(ast.walk(tree)):
        line = getattr(node, "lineno", 0)

        def at(t, index=index):
            return list(ast.walk(t))[index]

        if isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                for new in CMP.get(type(op), ()):
                    def apply(t, k=k, new=new):
                        at(t).ops[k] = new()
                    yield line, "cmp", f"{type(op).__name__} -> {new.__name__}", apply
        elif isinstance(node, ast.BoolOp):
            new = ast.Or if isinstance(node.op, ast.And) else ast.And
            def apply(t, new=new):
                at(t).op = new()
            yield line, "bool", f"{type(node.op).__name__} -> {new.__name__}", apply
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            def apply(t):
                n = at(t)
                _replace_expression(t, n, ast.Call(ast.Name("bool", ast.Load()), [n.operand], []))
            yield line, "bool", "not x -> bool(x)", apply
        elif isinstance(node, (ast.BinOp, ast.AugAssign)) and type(node.op) in ARITH:
            new = ARITH[type(node.op)]
            def apply(t, new=new):
                at(t).op = new()
            yield line, "arith", f"{type(node.op).__name__} -> {new.__name__}", apply
        elif (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "D"
            and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
        ):
            value = node.args[0].value
            if isinstance(value, str):
                d = Decimal(value)
                for label, changed in (("x2", d * 2), ("/2", d / 2), ("=0", Decimal(0))):
                    def apply(t, changed=changed):
                        at(t).args[0] = ast.Constant(str(changed))
                    yield line, "constant", f'D("{value}") {label}', apply
            elif isinstance(value, int) and not isinstance(value, bool):
                def apply(t, value=value):
                    at(t).args[0] = ast.Constant(value + 1)
                yield line, "constant", f"D({value}) -> D({value + 1})", apply
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            def apply(t):
                n = at(t)
                n.value = not n.value
            yield line, "constant", f"{node.value} -> {not node.value}", apply
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "max":
            def apply(t):
                at(t).func.id = "min"
            yield line, "call", "max -> min", apply
        elif isinstance(node, (ast.Continue, ast.Raise)) or (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "add"
        ):
            what = {"Continue": "continue", "Raise": "raise"}.get(type(node).__name__, "set.add")
            def apply(t):
                _replace_statement(t, at(t))
            yield line, "delete", f"delete {what}", apply
        elif isinstance(node, ast.Set) and node.elts and all(
            isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name)
            and e.value.id == "Disposition" for e in node.elts
        ):
            present = [e.attr for e in node.elts]
            for name in present:
                def apply(t, name=name):
                    n = at(t)
                    n.elts = [e for e in n.elts if e.attr != name]
                yield line, "policy", f"remove {name}", apply
            for name in disposition_names:
                if name not in present:
                    def apply(t, name=name):
                        at(t).elts.append(
                            ast.Attribute(ast.Name("Disposition", ast.Load()), name, ast.Load())
                        )
                    yield line, "policy", f"add {name}", apply


def disposition_names(repo: Path) -> list[str]:
    tree = ast.parse((repo / "iscops/domain/taxonomy.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Disposition":
            return [s.targets[0].id for s in node.body if isinstance(s, ast.Assign)]
    raise SystemExit("Disposition enum not found in iscops/domain/taxonomy.py")


def suite_passes(workdir: Path, timeout: int) -> bool:
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests"],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False
    return done.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--targets", nargs="+", default=list(DEFAULT_TARGETS))
    parser.add_argument("--out", type=Path, help="write every result as JSON")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per suite run")
    args = parser.parse_args()
    repo = args.repo.resolve()
    names = disposition_names(repo)

    with tempfile.TemporaryDirectory(prefix="iscops-mutate-") as tmp:
        work = Path(tmp)
        ignore = shutil.ignore_patterns("__pycache__", ".DS_Store")
        shutil.copytree(repo / "iscops", work / "iscops", ignore=ignore)
        shutil.copytree(repo / "tests", work / "tests", ignore=ignore)

        if not suite_passes(work, args.timeout):
            raise SystemExit("the untouched copy does not pass; nothing measured")
        engine = work / "iscops/tools/match.py"
        original = engine.read_text()
        engine.write_text(original.replace(
            "    found: set[ExceptionClass] = set()\n",
            "    return frozenset()\n    found: set[ExceptionClass] = set()\n", 1,
        ))
        canary_killed = engine.read_text() != original and not suite_passes(work, args.timeout)
        engine.write_text(original)
        if not canary_killed:
            raise SystemExit("canary survived: the suite is not running the mutated copy")

        results = []
        for target in args.targets:
            path = work / target
            source = path.read_text()
            tree = ast.parse(source)
            baseline = ast.unparse(tree)
            for line, category, description, apply in mutants(tree, names):
                mutated = copy.deepcopy(tree)
                apply(mutated)
                ast.fix_missing_locations(mutated)
                text = ast.unparse(mutated)
                if text == baseline:
                    continue
                path.write_text(text)
                survived = suite_passes(work, args.timeout)
                results.append({
                    "file": target, "line": line, "category": category,
                    "mutation": description, "survived": survived,
                })
                print("S" if survived else ".", end="", flush=True)
            path.write_text(source)
        print()
        if not suite_passes(work, args.timeout):
            raise SystemExit("the copy does not pass after restore; readings are suspect")

    print(f"{'file':<30}{'category':<10}{'mutants':>8}{'survived':>10}")
    cells: dict[tuple[str, str], list[int]] = {}
    for r in results:
        cell = cells.setdefault((r["file"], r["category"]), [0, 0])
        cell[0] += 1
        cell[1] += r["survived"]
    for (target, category), (total, survived) in sorted(cells.items()):
        print(f"{target:<30}{category:<10}{total:>8}{survived:>10}")
    total = len(results)
    survived = sum(r["survived"] for r in results)
    print(f"\nkilled {total - survived}/{total}; survived {survived}/{total}")
    for r in results:
        if r["survived"]:
            print(f"  SURVIVED {r['file']}:{r['line']}  {r['category']}  {r['mutation']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
