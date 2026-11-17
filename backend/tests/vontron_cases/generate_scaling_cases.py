"""Generate Scaling Vontron test cases.

Run from backend/:   python tests/vontron_cases/generate_scaling_cases.py

For every case it writes
  scaling/<case>.json            inputs + EMPTY (null) slots for Vontron's Scaling table. You fill the nulls.
  projects/scaling_<case>.json   a project you can load with "Open project (.json)"; then open the Scaling tab.
Existing capture files are never overwritten (use --force to reset them).

Vontron's Scaling table rows: pH, TDS, HCO3, CO3, CO2, LSI, S&DSI, CaSO4, BaSO4, SrSO4, CaF2, SiO2 (saturation %),
columns Feed | Adjusted Feed | Concentrate. Write "N/A" where Vontron shows N/A.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))

from app.calc import scaling as S  # noqa: E402
from app.calc import water as W  # noqa: E402

KEYS = ["pH", "TDS", "HCO3", "CO3", "CO2", "LSI", "SDSI", "CaSO4", "BaSO4", "SrSO4", "CaF2", "SiO2"]
ZERO = {k: 0.0 for k in W.ORDER}


def water(ph=7.6, temp=25, tds=None, **ions):
    d = dict(ZERO)
    d.update({k: float(v) for k, v in ions.items()})
    return {"inputUnit": "mg/L", "specifyIndividualSolutes": tds is None, "tdsInput": tds,
            "temperatureC": temp, "pH": ph, "waterType": "RO Permeate SDI < 1", "ions": d}


def balanced(w):
    """Run Vontron-style Auto Balance so the water is balanced (so a case is not confused by a warning)."""
    return W.auto_balance(w)


# Scaling water S1: brackish with Ba, Sr, F so every salt index is non-zero. Balanced with Auto Balance.
S1 = balanced(water(7.6, Na=120, Ca=75, Mg=28, K=6, Ba=0.05, Sr=1.0, Cl=180, HCO3=260, F=0.8, SO4=110, NO3=5, SiO2=18))
SEA = balanced(water(8.1, Na=10760, Ca=412, Mg=1294, K=399, Sr=8, B=4.5, Cl=19350, HCO3=142, F=1.3, SO4=2710, SiO2=1))
ALL = balanced(water(7.5, Na=80, Ca=45, Mg=50, K=6, Ba=0.05, Sr=0.8, NH4=0.5, B=0.4, Cl=110, HCO3=180,
                     F=0.7, NO3=8.5, SO4=65, SiO2=22))
NACL = water(7.5, tds=2000)


def sc(recovery=75, temp=25, option="none", ph_chem="H2SO4", ph_target=7.5, ca_leak=0.1, mg_leak=0.1):
    return {"recoveryPct": recovery, "temperatureC": temp, "option": option,
            "phAdjust": {"chemical": ph_chem, "targetPH": ph_target},
            "softening": {"caLeakage": ca_leak, "mgLeakage": mg_leak}}


def with_(w, **kw):
    w = copy.deepcopy(w)
    for k, v in kw.items():
        if k == "ph":
            w["pH"] = v
        elif k == "temp":
            w["temperatureC"] = v
        else:
            w["ions"][k] = v
    return w


CASES = []


def add(case, tier, title, purpose, w, s):
    CASES.append(dict(case=case, tier=tier, title=title, purpose=purpose, water=w, scaling=s))


# ---- Tier 1: core, option "none" ---------------------------------------------------------------
add("sc_01_base_75", 1, "Brackish, 75% recovery", "Core formulas, all salts non-zero", S1, sc(75))
add("sc_02_base_50", 1, "Brackish, 50% recovery", "Recovery effect", S1, sc(50))
add("sc_03_base_85", 1, "Brackish, 85% recovery", "High CF, expect several warnings", S1, sc(85))
add("sc_04_temp10", 1, "Brackish, 10 C", "Temperature effect (Ksp, LSI, S&DSI, silica)", S1, sc(75, temp=10))
add("sc_05_temp40", 1, "Brackish, 40 C", "Upper temperature", S1, sc(75, temp=40))
add("sc_06_ph6p5", 1, "Brackish, pH 6.5", "Low pH (CO2, LSI, silica table)", with_(S1, ph=6.5), sc(75))
add("sc_07_ph8p8", 1, "Brackish, pH 8.8", "High pH (LSI, silica table, concentrate pH)", with_(S1, ph=8.8), sc(75))
add("sc_08_seawater_45", 1, "Seawater, 45% recovery", "Ionic strength above 0.13: S&DSI and Ksp provisional", SEA, sc(45))
add("sc_09_all_ions_75", 1, "All 15 ions (balanced), 75%", "F, NH4, B, NO3 present", ALL, sc(75))
add("sc_10_nacl2000_70", 1, "NaCl TDS 2000, 70%", "No Ca/HCO3: LSI and S&DSI should be N/A", NACL, sc(70))
add("sc_11_silica_high", 1, "High silica, pH 8.5", "Silica saturation and warning", with_(S1, ph=8.5, SiO2=80), sc(75))


# ---- Tier 2: thresholds -------------------------------------------------------------------------
def _find(fn, lo, hi, target, n=60):
    for _ in range(n):
        mid = (lo + hi) / 2
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def conc_lsi_at_ph(ph):
    return S.calculate(with_(S1, ph=ph), sc(75))["columns"]["concentrate"]["LSI"]


for tag, target in (("m10", -0.10), ("m03", -0.03), ("p03", 0.03), ("p10", 0.10)):
    ph = round(_find(conc_lsi_at_ph, 5.0, 9.0, target), 2)
    add(f"sc_lsi_{tag}", 2, f"CaCO3 warning threshold, concentrate LSI about {target:+.2f}",
        "Does Vontron show the CaCO3 warning? (project: when LSI > 0, PROVISIONAL)", with_(S1, ph=ph), sc(75))


def tds_conc_at_na(na):
    return S.calculate(with_(S1, Na=na), sc(75))["columns"]["concentrate"]["TDS"]


for tag, target in (("below", 3980), ("above", 4020)):
    na = round(_find(tds_conc_at_na, 0, 3000, target), 2)
    add(f"sc_sr_{tag}", 2, f"SrSO4 branch, concentrate TDS about {target}",
        "Vontron switches SrSO4 constants at TDS 4000 (project replicates this, awaiting confirmation)",
        with_(S1, Na=na), sc(75))
add("sc_recovery_0", 2, "Recovery 0%", "CF = 1: concentrate equals feed", S1, sc(0))

# ---- Tier 3: chemical options (no Vontron data yet) ----------------------------------------------
add("sc_ph_h2so4_6p5", 3, "pH adjust: H2SO4 to 6.5", "Acid dose, new SO4/HCO3/CO2 (PROVISIONAL)", S1,
    sc(75, option="ph_adjust", ph_chem="H2SO4", ph_target=6.5))
add("sc_ph_hcl_6p5", 3, "pH adjust: HCl to 6.5", "Cl added instead of SO4 (PROVISIONAL)", S1,
    sc(75, option="ph_adjust", ph_chem="HCl", ph_target=6.5))
add("sc_ph_target_above", 3, "pH adjust: target above feed pH", "What does Vontron do or say? (project: warns, no change)",
    S1, sc(75, option="ph_adjust", ph_chem="H2SO4", ph_target=8.5))
add("sc_soft_default", 3, "Softening, leakage 0.1 / 0.1", "Na exchange (PROVISIONAL)", S1,
    sc(75, option="softening", ca_leak=0.1, mg_leak=0.1))
add("sc_soft_leak1", 3, "Softening, leakage 1 / 1", "Leakage handling", S1,
    sc(75, option="softening", ca_leak=1, mg_leak=1))
add("sc_antiscalant_85", 3, "Antiscalant, 85%", "Which limits apply with antiscalant? (PROVISIONAL)", S1,
    sc(85, option="antiscalant"))


# ---- output ---------------------------------------------------------------------------------------
def slots():
    return {c: {k: None for k in KEYS} for c in ("feed", "adjusted", "concentrate")}


def reference(w, s):
    r = S.calculate(w, s)
    cols = {}
    for c in ("feed", "adjusted", "concentrate"):
        col = r["columns"][c]
        cols[c] = {k: (None if col.get(k) is None else round(col[k], 2)) for k in KEYS}
    warn = [m["index"] for m in r["messages"] if m.get("index")]
    return {"columns": cols, "warnings": warn, "cf": round(r["cf"], 4),
            "acidDose": r.get("acidDose")}


def main():
    force = "--force" in sys.argv
    (HERE / "scaling").mkdir(exist_ok=True)
    (HERE / "projects").mkdir(exist_ok=True)
    made = kept = 0
    for c in CASES:
        cap = {
            "case": c["case"], "tier": c["tier"], "title": c["title"], "purpose": c["purpose"],
            "vontronVersion": "6.1", "capturedOn": None,
            "howTo": ("Open projects/scaling_<case>.json in our app (or type the same water into Vontron's Water Analysis "
                      "tab, then set Recovery / Temp / option on the Scaling tab) and press Scale Calculation. Replace every "
                      "null under 'vontron' with the value Vontron shows; write \"N/A\" where Vontron shows N/A. "
                      "'warnings' = list of names in Vontron's red messages, e.g. [\"CaCO3\",\"BaSO4\"], or [] if none."),
            "input": {"water": c["water"], "scaling": c["scaling"]},
            "vontron": {**slots(), "warnings": None, "acidDose": None},
            "projectExpectsForReference": reference(c["water"], c["scaling"]),
        }
        path = HERE / "scaling" / f"{c['case']}.json"
        if path.exists() and not force:
            kept += 1
        else:
            path.write_text(json.dumps(cap, indent=2) + "\n", encoding="utf-8")
            made += 1
        project = {
            "version": "1.0",
            "project": {"name": c["case"], "date": "2026-11-15", "designedBy": "Vontron check", "company": "Untitled"},
            "water": c["water"], "scaling": c["scaling"],
            "design": {"unitSet": "gpm_psi", "recoveryPct": 15, "permeateFlow": 1.1355, "feedTempC": 25,
                       "foulingFactor": 0.85,
                       "passes": [{"stages": [{"vessels": 1, "elementsPerVessel": 1, "elementModel": "LP22-8040",
                                               "backPressure": 0}], "sameElementInPass": True, "sameBackPressure": True}],
                       "pumpEfficiencyEnabled": False, "pumpEfficiencyPct": 80, "intakeBothEnds": False,
                       "frontEndPct": 50, "recycle": {"enabled": False, "flow": 0}},
            "results": {"water": None, "scaling": None, "design": None},
        }
        (HERE / "projects" / f"scaling_{c['case']}.json").write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    print(f"{len(CASES)} scaling cases: {made} capture files written, {kept} kept.")


if __name__ == "__main__":
    main()
