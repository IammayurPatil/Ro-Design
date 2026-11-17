"""Compare filled-in Vontron captures with our Water Analysis engine.

Command line (from backend/):   python tests/vontron_compare.py
Also used by tests/test_vontron_water.py. A null in a capture file means "not captured yet" and is skipped.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.calc import water as W  # noqa: E402

CASE_DIR = Path(__file__).parent / "vontron_cases" / "water"
TOL = 0.01  # same as golden_cases.json default.abs


def load_cases():
    return sorted(CASE_DIR.glob("*.json"))


def _check(diffs, label, vontron, ours, tol=TOL):
    if vontron is None:
        return 0
    if ours is None:
        diffs.append((label, vontron, None, None))
        return 1
    if abs(vontron - ours) > tol + 1e-9:
        diffs.append((label, vontron, ours, ours - vontron))
    return 1


def _compare_block(diffs, a, block, prefix=""):
    """Compare one Vontron block {rows, totals, imbalanceWarning} with an analysis result."""
    checked = 0
    for ion, slots in (block.get("rows") or {}).items():
        r = a["rows"][ion]
        checked += _check(diffs, f"{prefix}{ion} mg/L", slots["mgL"], r["mgL"])
        checked += _check(diffs, f"{prefix}{ion} ppmCaCO3", slots["ppmCaCO3"], r["ppmCaCO3"])
        checked += _check(diffs, f"{prefix}{ion} meq", slots["meq"], r["meq"])
    t = block.get("totals") or {}
    checked += _check(diffs, f"{prefix}cations meq", t.get("cations"), a["cations"])
    checked += _check(diffs, f"{prefix}anions meq", t.get("anions"), a["anions"])
    checked += _check(diffs, f"{prefix}balance meq", t.get("balance"), a["balance"])
    checked += _check(diffs, f"{prefix}TDS", t.get("tds"), a["tds"])
    if block.get("imbalanceWarning") is not None:
        checked += 1
        if bool(block["imbalanceWarning"]) != bool(a["imbalance"]):
            diffs.append((f"{prefix}imbalance warning", block["imbalanceWarning"], a["imbalance"], None))
    return checked


def compare_case(path: Path):
    """Return (values_checked, mismatches). mismatches = [(label, vontron, ours, diff)]."""
    cap = json.loads(path.read_text(encoding="utf-8"))
    water, v = cap["input"], cap["vontron"]
    diffs = []
    checked = _compare_block(diffs, W.analyze(water), v)
    ab = v.get("autoBalance")
    if ab and ab.get("ionChanged") is not None:
        bal = W.auto_balance(water)
        before, after = W.effective_ions(water), bal["ions"]
        changed = [k for k in W.ORDER if abs(after[k] - before[k]) > 1e-9]
        ours_ion = changed[0] if changed else None
        checked += 1
        if ours_ion != ab["ionChanged"]:
            diffs.append(("auto-balance ion", ab["ionChanged"], ours_ion, None))
        if ab.get("newMgL") is not None and ab["ionChanged"] in after:
            checked += _check(diffs, f"auto-balance new {ab['ionChanged']} mg/L", ab["newMgL"], after[ab["ionChanged"]])
        # everything Vontron shows after clicking Auto Balance
        if v.get("afterAutoBalance"):
            checked += _compare_block(diffs, W.analyze(bal), v["afterAutoBalance"], "after AB: ")
    return checked, diffs


def main():
    total_bad = 0
    print(f"{'case':28} {'checked':>8} {'status'}")
    for p in load_cases():
        checked, diffs = compare_case(p)
        status = "NOT CAPTURED" if checked == 0 else ("OK" if not diffs else f"{len(diffs)} MISMATCH")
        print(f"{p.stem:28} {checked:>8} {status}")
        for label, vv, oo, dd in diffs:
            extra = "" if dd is None else f"  diff {dd:+.4f}"
            print(f"      - {label}: Vontron={vv}  ours={oo}{extra}")
        total_bad += len(diffs)
    print(f"\n{total_bad} mismatch(es). Tolerance: {TOL}")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
