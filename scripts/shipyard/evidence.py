#!/usr/bin/env python3
"""Evidence ledger for Shipyard gates and tasks. Stdlib only.

Usage:
  evidence.py gate  G4 --artifact docs/design/04-execution-plan.md [--artifact ...]
                       --approval "approved — J. Doe, Delivery Lead" --approver-role delivery_lead
                       [--role Orchestrator] [--tier T2]
  evidence.py task  T-017 --artifact docs/tasks/T-017.verdict.md [--artifact ...]
                       --role Verifier --tier T2 [--approval "PASS"]
  evidence.py finding SEC-003 --artifact docs/tasks/T-017.security.md --role SecurityReviewer --tier T3
  evidence.py verify                      # validates the hash chain
  evidence.py rtm                         # regenerates docs/rtm.md
  evidence.py export [--out docs/evidence/pack-<date>]

The ledger is append-only and hash-chained. Agents supply artifacts; humans supply
approval text; the script supplies hashes, sequence, timestamps and the commit SHA.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

LEDGER = pathlib.Path("docs/evidence/ledger.jsonl")


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "nogit"


def read_entries():
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def entry_hash(e: dict) -> str:
    body = {k: v for k, v in e.items() if k != "hash"}
    return sha256_text(json.dumps(body, sort_keys=True, separators=(",", ":")))


def verify_chain(entries) -> list:
    problems, prev = [], ""
    for e in entries:
        if e.get("prev", "") != prev:
            problems.append(f"seq {e.get('seq')}: prev mismatch")
        if entry_hash(e) != e.get("hash"):
            problems.append(f"seq {e.get('seq')}: hash mismatch (tampered or hand-edited)")
        prev = e.get("hash", "")
    return problems


def append(kind: str, ref: str, artifacts, role, tier, approval, approver_role) -> dict:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entries = read_entries()
    problems = verify_chain(entries)
    if problems:
        print("REFUSED: ledger chain invalid:\n  " + "\n  ".join(problems))
        sys.exit(2)
    arts = []
    for a in artifacts or []:
        p = pathlib.Path(a)
        if not p.exists():
            print(f"REFUSED: artifact not found: {a}")
            sys.exit(2)
        arts.append({"path": str(p), "sha256": sha256_file(p)})
    e = {
        "seq": (entries[-1]["seq"] + 1) if entries else 1,
        "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind, "ref": ref, "artifacts": arts, "commit": git_sha(),
        "role": role or "", "tier": tier or "", "approval": approval or "",
        "approver_role": approver_role or "", "prev": entries[-1]["hash"] if entries else "",
    }
    e["hash"] = entry_hash(e)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n")
    return e


# ---------- RTM ----------
REQ_RE = re.compile(r"\b((?:FR|NFR)-\d{3,})\b")


def cmd_rtm() -> int:
    req_file = pathlib.Path("docs/design/01-requirements.md")
    reqs = []
    if req_file.exists():
        seen = set()
        for m in REQ_RE.finditer(req_file.read_text(encoding="utf-8")):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                reqs.append(m.group(1))
    design_refs, tasks, tests, evid = {}, {}, {}, {}
    for doc in pathlib.Path("docs/design").glob("0[23]-*.md"):
        text = doc.read_text(encoding="utf-8")
        for sec in re.split(r"\n(?=## )", text):
            title = sec.splitlines()[0].strip("# ").strip() if sec.strip() else ""
            for r in set(REQ_RE.findall(sec)):
                design_refs.setdefault(r, set()).add(f"{doc.name}: {title}")
    for pack in pathlib.Path("docs/tasks").glob("T-*.md"):
        if pack.name.endswith((".verdict.md", ".security.md")):
            continue
        text = pack.read_text(encoding="utf-8")
        m = re.search(r"^rtm:\s*\[(.*?)\]", text, re.M)
        status = re.search(r"^status:\s*(\S+)", text, re.M)
        tid = pack.name.split("-")[0] + "-" + pack.name.split("-")[1]
        for r in (m.group(1).split(",") if m and m.group(1).strip() else []):
            tasks.setdefault(r.strip(), []).append(f"{tid}({status.group(1) if status else '?'})")
    for tdir in ("tests", "test", "src"):
        for f in pathlib.Path(tdir).rglob("*") if pathlib.Path(tdir).exists() else []:
            if f.is_file() and f.suffix in {".py", ".ts", ".js", ".go", ".java", ".cs", ".rs", ".kt"}:
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for r in set(REQ_RE.findall(txt)):
                    tests.setdefault(r, set()).add(str(f))
    for e in read_entries():
        for a in e.get("artifacts", []):
            for r in set(REQ_RE.findall(a["path"])):
                evid.setdefault(r, set()).add(str(e["seq"]))
        for r in set(REQ_RE.findall(e.get("ref", ""))):
            evid.setdefault(r, set()).add(str(e["seq"]))
    lines = ["# Requirements Traceability Matrix", "",
             f"Regenerated {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} "
             "by `scripts/evidence.py rtm`.", "",
             "| Req | Design § | Tasks | Tests | Evidence seq | Status |", "|---|---|---|---|---|---|"]
    gaps = 0
    for r in reqs:
        d = "; ".join(sorted(design_refs.get(r, []))) or "—"
        t = ", ".join(tasks.get(r, [])) or "—"
        ts = ", ".join(sorted(tests.get(r, []))) or "—"
        ev = ", ".join(sorted(evid.get(r, []), key=int)) or "—"
        if t == "—":
            status = "NO TASK (G4 finding)"; gaps += 1
        elif ts == "—":
            status = "NO TEST (G7 blocker)"; gaps += 1
        elif all("(done)" in x for x in tasks.get(r, [])):
            status = "covered"
        else:
            status = "in progress"
        lines.append(f"| {r} | {d} | {t} | {ts} | {ev} | {status} |")
    pathlib.Path("docs/rtm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"RTM: {len(reqs)} requirements, {gaps} gap(s)")
    return 0 if gaps == 0 else 1


# ---------- export ----------
def cmd_export(out: str) -> int:
    entries = read_entries()
    problems = verify_chain(entries)
    if problems:
        print("REFUSED: chain invalid:\n  " + "\n  ".join(problems))
        return 2
    dest = pathlib.Path(out or f"docs/evidence/pack-{dt.date.today().isoformat()}")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEDGER, dest / "ledger.jsonl")
    index = ["# Evidence pack", "", f"Generated {dt.datetime.now(dt.timezone.utc).isoformat()}",
             f"Entries: {len(entries)}  Chain: valid", "",
             "| Seq | Kind | Ref | Role | Tier | Approver role | Artifacts |", "|---|---|---|---|---|---|---|"]
    for e in entries:
        names = []
        for a in e.get("artifacts", []):
            src = pathlib.Path(a["path"])
            if src.exists():
                tgt = dest / "artifacts" / f"{e['seq']:04d}" / src.name
                tgt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tgt)
                cur = sha256_file(src)
                names.append(f"{src.name}{'' if cur == a['sha256'] else ' (CHANGED since ledger)'}")
            else:
                names.append(f"{src.name} (missing)")
        index.append(f"| {e['seq']} | {e['kind']} | {e['ref']} | {e['role']} | {e['tier']} | "
                     f"{e['approver_role']} | {', '.join(names)} |")
    (dest / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Exported {len(entries)} entries to {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for kind in ("gate", "task", "finding"):
        s = sub.add_parser(kind)
        s.add_argument("ref")
        s.add_argument("--artifact", action="append", default=[])
        s.add_argument("--role", default="")
        s.add_argument("--tier", default="")
        s.add_argument("--approval", default="")
        s.add_argument("--approver-role", default="")
    sub.add_parser("verify")
    sub.add_parser("rtm")
    ex = sub.add_parser("export")
    ex.add_argument("--out", default="")
    a = ap.parse_args()

    if a.cmd in ("gate", "task", "finding"):
        if a.cmd == "gate" and not (a.approval and a.approver_role):
            print("REFUSED: gate entries require --approval (verbatim human/CI text) and --approver-role")
            return 2
        e = append(a.cmd, a.ref, a.artifact, a.role, a.tier, a.approval, a.approver_role)
        print(f"ledger seq {e['seq']} {e['kind']} {e['ref']} hash {e['hash'][:12]}")
        return 0
    if a.cmd == "verify":
        p = verify_chain(read_entries())
        print("chain valid" if not p else "chain INVALID:\n  " + "\n  ".join(p))
        return 0 if not p else 1
    if a.cmd == "rtm":
        return cmd_rtm()
    if a.cmd == "export":
        return cmd_export(a.out)
    return 1


if __name__ == "__main__":
    sys.exit(main())
