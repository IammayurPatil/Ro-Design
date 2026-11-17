"""Compare filled-in Vontron Scaling captures with our Scaling engine.

Command line (from backend/):   python tests/vontron_compare_scaling.py
null = not captured (skipped). "N/A" in a capture means our engine must return None.
Tolerances follow golden_cases.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.calc import scaling as S  # noqa: E402

CASE_DIR = Path(__file__).parent / "vontron_cases" / "scaling"
TOL = json.loads((Path(__file__).parent / "golden_cases.json").read_text(encoding="utf-8"))["tolerances"]
SALTS = ("CaSO4", "BaSO4", "SrSO4", "CaF2")


def load_cases():
    return sorted(CASE_DIR.glob("*.json"))


def _tol(key, col, expected, temp):
    if key in SALTS:
        return max(abs(expected) * TOL["saturationPct"]["rel"], 0.01)
    if key == "SiO2":
        if col == "concentrate":
            return max(abs(expected) * TOL["silicaConcentratePct"]["rel"], 0.01)
        return TOL["silicaTemperaturePct"]["abs"] if temp != 25 else 0.01
    if key == "SDSI" and temp != 25:
        return TOL["sdsiTemperature"]["abs"]
    return TOL["default"]["abs"]


def compare_case(path: Path):
    cap = json.loads(path.read_text(encoding="utf-8"))
    w, s, v = cap["input"]["water"], cap["input"]["scaling"], cap["vontron"]
    r = S.calculate(w, s)
    temp = s.get("temperatureC", 25)
    diffs, checked = [], 0
    for col in ("feed", "adjusted", "concentrate"):
        ours_col = r["columns"][col]
        for key, expected in (v.get(col) or {}).items():
            if expected is None:
                continue
            checked += 1
            ours = ours_col.get(key)
            label = f"{col} {key}"
            if isinstance(expected, str):  # "N/A"
                if ours is not None:
                    diffs.append((label, expected, round(ours, 4), None))
                continue
            if ours is None:
                diffs.append((label, expected, "N/A", None))
                continue
            tol = _tol(key, col, expected, temp)
            if abs(ours - expected) > tol + 1e-9:
                diffs.append((label, expected, round(ours, 4), ours - expected))
    if v.get("warnings") is not None:
        checked += 1
        ours_w = sorted(m["index"] for m in r["messages"] if m.get("index"))
        if sorted(v["warnings"]) != ours_w:
            diffs.append(("warnings", sorted(v["warnings"]), ours_w, None))
    dose = v.get("acidDose")
    if isinstance(dose, dict) and dose.get("mgL") is not None:
        checked += 1
        ours = (r.get("acidDose") or {}).get("mgL")
        if ours is None or abs(ours - dose["mgL"]) > 0.01 + 1e-9:
            diffs.append(("acid dose mg/L", dose["mgL"], ours, None))
    return checked, diffs


def main():
    bad = 0
    print(f"{'case':26} {'tier':>4} {'checked':>8} status")
    for p in load_cases():
        tier = json.loads(p.read_text(encoding="utf-8")).get("tier", "")
        checked, diffs = compare_case(p)
        status = "NOT CAPTURED" if checked == 0 else ("OK" if not diffs else f"{len(diffs)} MISMATCH")
        print(f"{p.stem:26} {tier:>4} {checked:>8} {status}")
        for label, vv, oo, dd in diffs:
            extra = "" if dd is None else f"  diff {dd:+.4f}"
            print(f"      - {label}: Vontron={vv}  ours={oo}{extra}")
        bad += len(diffs)
    print(f"\n{bad} mismatch(es).")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
