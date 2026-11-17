"""Generate Water Analysis Vontron test cases.

Run from the backend folder:   python tests/vontron_cases/generate_cases.py

Creates, for every case:
  water/<case>.json      -> inputs + EMPTY (null) Vontron output slots. Fill the nulls from Vontron.
  projects/<case>.json   -> a project file you can load with "Open project (.json)" in the web app,
                            so the inputs do not have to be typed by hand.
Existing capture files are NOT overwritten (so values you already pasted are kept). Use --force to reset.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))  # backend/

from app.calc import water as W  # noqa: E402

ORDER = W.ORDER
ZERO = {k: 0.0 for k in ORDER}


def ions(**kw):
    d = dict(ZERO)
    d.update({k: float(v) for k, v in kw.items()})
    return d


def balanced_base():
    """A water whose cations equal its anions (Cl is solved to 2 decimals)."""
    d = ions(Na=150, Ca=60, Mg=20, K=5, HCO3=200, SO4=100, NO3=10)
    cat, an, _ = W.charge_totals(d)
    d["Cl"] = round(d["Cl"] + (cat - an) * W.IONS["Cl"]["eqWt"], 2)
    return d


CASES = []


def add(case, title, purpose, ions_=None, tds=None, ph=7.5, temp=25, auto_balance=False):
    CASES.append(dict(case=case, title=title, purpose=purpose, ions=ions_, tds=tds, ph=ph,
                      temp=temp, auto_balance=auto_balance))


add("water_01_tds500", "TDS only, 500 mg/L", "Na/Cl split at low TDS", tds=500)
add("water_02_tds35000", "TDS only, 35000 mg/L", "Na/Cl split and rounding at high TDS", tds=35000)
add("water_03_brackish", "Brackish well water", "Normal conversions",
    ions(Na=126.9, Ca=75, Mg=28, K=6, Cl=180, HCO3=260, SO4=110, NO3=5, SiO2=18), ph=7.6)
add("water_04_seawater", "Seawater", "Large values, TDS sum, boron",
    ions(Na=10760, Ca=412, Mg=1294, K=399, Sr=8, B=4.5, Cl=19350, HCO3=142, F=1.3, SO4=2710, SiO2=1), ph=8.1)
add("water_05_all_ions", "All 15 ions present", "Every factor, and TDS with boron (x 5.72)",
    ions(Na=80, Ca=45, Mg=50, K=6, Ba=0.05, Sr=0.8, NH4=0.5, B=0.4, Cl=110, CO3=0, HCO3=180,
         F=0.7, NO3=8.5, SO4=65, SiO2=22))
add("water_06_anion_excess", "Anion excess", "Auto balance adds Na (confirmed rule)",
    ions(Na=50, Ca=30, Mg=10, K=3, Cl=150, HCO3=120, SO4=80), auto_balance=True)
add("water_07_cation_excess", "Cation excess", "Auto balance when cations exceed anions (Cl rule is PROVISIONAL)",
    ions(Na=300, Ca=80, Mg=25, K=10, Cl=100, HCO3=150, SO4=60), auto_balance=True)
add("water_08_decimals", "Values with many decimals", "mg/L rounding to 2 decimals and ppm/meq rounding",
    ions(Na=123.456, Ca=45.678, Mg=12.345, K=3.215, Cl=190.555, HCO3=150.125, SO4=75.995, SiO2=10.005))

# imbalance sweep: cations exceed anions by a target fraction (Na is raised)
base = balanced_base()
for pct in (1, 2, 3, 4, 5, 6, 7, 10):
    d = dict(base)
    cat, an, _ = W.charge_totals(d)
    target_cat = an / (1 - pct / 100)
    d["Na"] = round(d["Na"] + (target_cat - cat) * W.IONS["Na"]["eqWt"], 2)
    add(f"water_sweep_{pct:02d}pct", f"Imbalance sweep, about {pct}%",
        "Find the % where Vontron starts showing 'Ions out of Balance' (project: 5%, PROVISIONAL)", d)


def row_slots():
    return {k: {"mgL": None, "ppmCaCO3": None, "meq": None} for k in ORDER}


def build(c):
    water_ions = c["ions"] if c["ions"] is not None else dict(ZERO)
    water = {
        "inputUnit": "mg/L",
        "specifyIndividualSolutes": c["tds"] is None,
        "tdsInput": c["tds"],
        "temperatureC": c["temp"],
        "pH": c["ph"],
        "waterType": "RO Permeate SDI < 1",
        "ions": water_ions,
    }
    analysis = W.analyze(water)
    cap = {
        "case": c["case"],
        "title": c["title"],
        "purpose": c["purpose"],
        "vontronVersion": "6.1",
        "capturedOn": None,
        "howTo": ("In Vontron enter the 'input' below (or open projects/<case>.json in our app and "
                  "copy the same values). Then replace every null under 'vontron' with the number "
                  "Vontron shows. Leave B and SiO2 ppmCaCO3 / meq as null."),
        "input": water,
        "vontron": {
            "rows": row_slots(),
            "totals": {"cations": None, "anions": None, "balance": None, "tds": None},
            "imbalanceWarning": None,
            "warningText": None,
            "autoBalance": ({"ionChanged": None, "newMgL": None} if c["auto_balance"] else None),
        },
        "projectExpectsForReference": {
            "tds": round(analysis["tds"], 2),
            "cations": round(analysis["cations"], 3),
            "anions": round(analysis["anions"], 3),
            "imbalancePct": round(analysis["imbalanceFraction"] * 100, 2),
            "imbalanceWarning": analysis["imbalance"],
        },
    }
    project = {
        "version": "1.0",
        "project": {"name": c["case"], "date": "2026-11-15", "designedBy": "Vontron check", "company": "Untitled"},
        "water": water,
        # The app's "Open project" requires both "water" and "design"; these mirror the app defaults.
        "scaling": {"recoveryPct": 15, "temperatureC": c["temp"], "option": "none",
                    "phAdjust": {"chemical": "H2SO4", "targetPH": 7.5},
                    "softening": {"caLeakage": 0.1, "mgLeakage": 0.1}},
        "design": {"unitSet": "gpm_psi", "recoveryPct": 15, "permeateFlow": 1.1355, "feedTempC": c["temp"],
                   "foulingFactor": 0.85,
                   "passes": [{"stages": [{"vessels": 1, "elementsPerVessel": 1, "elementModel": "LP22-8040",
                                           "backPressure": 0}],
                               "sameElementInPass": True, "sameBackPressure": True}],
                   "pumpEfficiencyEnabled": False, "pumpEfficiencyPct": 80, "intakeBothEnds": False,
                   "frontEndPct": 50, "recycle": {"enabled": False, "flow": 0}},
        "results": {"water": None, "scaling": None, "design": None},
    }
    return cap, project


def main():
    force = "--force" in sys.argv
    (HERE / "water").mkdir(exist_ok=True)
    (HERE / "projects").mkdir(exist_ok=True)
    made, kept = 0, 0
    for c in CASES:
        cap, project = build(c)
        cap_path = HERE / "water" / f"{c['case']}.json"
        if cap_path.exists() and not force:
            kept += 1
        else:
            cap_path.write_text(json.dumps(cap, indent=2) + "\n", encoding="utf-8")
            made += 1
        (HERE / "projects" / f"{c['case']}.json").write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    print(f"{len(CASES)} cases: {made} capture files written, {kept} kept (already existed). "
          f"Project files refreshed in {HERE / 'projects'}")


if __name__ == "__main__":
    main()
