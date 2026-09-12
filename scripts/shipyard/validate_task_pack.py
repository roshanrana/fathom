#!/usr/bin/env python3
"""Validate task packs before Gate G4 (and after any re-plan).

Usage: python validate_task_pack.py <docs/tasks dir | single pack.md> [--config config/model-routing.yaml]

Checks: frontmatter keys and enums, budget ceilings by complexity, high-risk routing,
required sections, non-empty scope / acceptance criteria / validation commands,
unique ids, filename matches id, depends_on resolves, no dependency cycles.
Exit code 0 = all packs valid. Stdlib only; PyYAML used for config if installed.
"""
import argparse
import pathlib
import re
import sys

REQUIRED_KEYS = ["id", "title", "milestone", "risk", "tier", "complexity",
                 "reasoning", "budget", "depends_on", "rtm", "status"]
ENUMS = {
    "risk": {"low", "medium", "high"},
    "tier": {"T1", "T2", "T3"},
    "complexity": {"template", "normal", "high"},
    "reasoning": {"on", "off", "true", "false"},
    "status": {"todo", "in_progress", "verify", "blocked", "done"},
}
REQUIRED_SECTIONS = ["## Goal", "## Spec references", "## Scope", "## Acceptance criteria",
                     "## Validation commands", "## Verification checklist",
                     "## Threat-model boundary", "## Handoff"]
DEFAULT_BUDGETS = {
    "template": {"input_tokens": 15000, "tool_calls": 10, "wall_clock_min": 10},
    "normal": {"input_tokens": 40000, "tool_calls": 40, "wall_clock_min": 45},
    "high": {"input_tokens": 80000, "tool_calls": 80, "wall_clock_min": 120},
}
ID_RE = re.compile(r"^T-\d{3,}$")


def parse_scalar(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [x.strip().strip("'\"") for x in inner.split(",")] if inner else []
    if v.startswith("{") and v.endswith("}"):
        out = {}
        for part in v[1:-1].split(","):
            if ":" in part:
                k, val = part.split(":", 1)
                val = val.strip()
                out[k.strip()] = int(val) if val.isdigit() else val
        return out
    return v.strip("'\"")


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = parse_scalar(v)
    return fm


def load_budgets(cfg_path):
    if not cfg_path or not pathlib.Path(cfg_path).exists():
        return DEFAULT_BUDGETS
    try:
        import yaml  # type: ignore
    except ImportError:
        return DEFAULT_BUDGETS
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    b = cfg.get("budgets", {})
    return {k: b.get(k, DEFAULT_BUDGETS[k]) for k in DEFAULT_BUDGETS}


def section_body(text: str, header: str) -> str:
    idx = text.find(header)
    if idx < 0:
        return ""
    rest = text[idx + len(header):]
    nxt = re.search(r"\n## ", rest)
    return rest[: nxt.start()] if nxt else rest


def bullets(body: str):
    return [l for l in body.splitlines() if re.match(r"^\s*[-*]\s+\S", l)
            and "<" not in l]  # ignore template placeholders


def validate(path: pathlib.Path, budgets) -> list:
    errs = []
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm is None:
        return ["no YAML frontmatter"]
    for k in REQUIRED_KEYS:
        if k not in fm:
            errs.append(f"missing frontmatter key: {k}")
    if errs:
        return errs
    if not ID_RE.match(str(fm["id"])):
        errs.append(f"id '{fm['id']}' not of form T-###")
    if not path.name.startswith(str(fm["id"]) + "-") and path.name != f"{fm['id']}.md":
        errs.append(f"filename should start with '{fm['id']}-'")
    for k, allowed in ENUMS.items():
        if str(fm[k]) not in allowed:
            errs.append(f"{k}='{fm[k]}' not in {sorted(allowed)}")
    b = fm["budget"] if isinstance(fm["budget"], dict) else {}
    for k in ("input_tokens", "tool_calls", "wall_clock_min"):
        if k not in b:
            errs.append(f"budget missing {k}")
    ceiling = budgets.get(str(fm["complexity"]), DEFAULT_BUDGETS["normal"])
    for k, cap in ceiling.items():
        if k in b and isinstance(b[k], int) and b[k] > cap:
            errs.append(f"budget.{k}={b[k]} exceeds ceiling {cap} for complexity={fm['complexity']}")
    if fm["complexity"] == "template" and fm["tier"] != "T1":
        errs.append("complexity=template should route to T1 (prefer down)")
    if fm["complexity"] == "high" and str(fm["reasoning"]) in {"off", "false"}:
        errs.append("complexity=high requires reasoning: on")
    if fm["risk"] == "high" and fm["tier"] == "T1":
        errs.append("risk=high must not be implemented at T1")
    for s in REQUIRED_SECTIONS:
        if s not in text:
            errs.append(f"missing section: {s}")
    if not bullets(section_body(text, "## Scope")):
        errs.append("Scope has no files listed")
    acs = [l for l in bullets(section_body(text, "## Acceptance criteria")) if "AC" in l]
    if not acs:
        errs.append("no acceptance criteria (AC1: ...)")
    if not bullets(section_body(text, "## Validation commands")):
        errs.append("no validation commands")
    spec = section_body(text, "## Spec references")
    if len(spec.splitlines()) > 40:
        errs.append("Spec references exceeds 30-line excerpt guideline (split task or fix LLD)")
    if fm["risk"] == "high" and "none" in section_body(text, "## Threat-model boundary").lower():
        errs.append("risk=high but threat-model boundary is 'none'")
    if not fm["rtm"]:
        errs.append("rtm links empty — every task must trace to a requirement")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--config", default="config/model-routing.yaml")
    args = ap.parse_args()
    target = pathlib.Path(args.target)
    files = [target] if target.is_file() else sorted(
        p for p in target.glob("T-*.md") if not p.name.endswith((".verdict.md", ".security.md")))
    if not files:
        print("no task packs found")
        return 1
    budgets = load_budgets(args.config)
    ids, deps, total = {}, {}, 0
    for f in files:
        errs = validate(f, budgets)
        fm = parse_frontmatter(f.read_text(encoding="utf-8")) or {}
        tid = str(fm.get("id", f.stem))
        if tid in ids:
            errs.append(f"duplicate id {tid} (also {ids[tid]})")
        ids[tid] = f.name
        deps[tid] = [d for d in (fm.get("depends_on") or []) if d]
        if errs:
            total += len(errs)
            print(f"FAIL {f.name}")
            for e in errs:
                print(f"   - {e}")
    for tid, ds in deps.items():
        for d in ds:
            if d not in ids:
                total += 1
                print(f"FAIL {ids[tid]}\n   - depends_on {d} does not exist")
    # cycle check
    state = {}

    def visit(n, stack):
        if state.get(n) == 1:
            return [n] + stack
        if state.get(n) == 2:
            return None
        state[n] = 1
        for d in deps.get(n, []):
            cyc = visit(d, [n] + stack)
            if cyc:
                return cyc
        state[n] = 2
        return None

    for tid in deps:
        cyc = visit(tid, [])
        if cyc:
            total += 1
            print(f"FAIL dependency cycle: {' -> '.join(reversed(cyc))}")
            break
    print(f"{len(files)} pack(s) checked, {total} problem(s)")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
