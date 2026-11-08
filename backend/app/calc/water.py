"""Water Analysis: unit conversions, TDS, charge balance, auto balance (prompt section 4)."""
import copy

from app.calc.units import round_half_up
from app.config import load

CFG = load("ions")
IONS = CFG["ions"]
ORDER = CFG["order"]
CATIONS = [k for k in ORDER if IONS[k]["group"] == "cation"]
ANIONS = [k for k in ORDER if IONS[k]["group"] == "anion"]


def _round_mgl(v: float) -> float:
    if CFG["rounding"]["roundMgLTo2Decimals"]:
        return round_half_up(v, CFG["rounding"]["mgLDecimals"])
    return v


def effective_ions(water: dict) -> dict:
    """mg/L of every ion as used by the calculation.

    In TDS-only mode ("Specify Individual Solutes" unticked) every ion is 0 except Na and Cl,
    which are split from the TDS input.
    """
    if not water.get("specifyIndividualSolutes", True):
        tds = float(water.get("tdsInput") or 0)
        ions = {k: 0.0 for k in ORDER}
        for ion, frac in CFG["tdsOnlyMode"]["split"].items():
            ions[ion] = _round_mgl(tds * frac)
        return ions
    src = water.get("ions") or {}
    return {k: float(src.get(k) or 0) for k in ORDER}


def meq(ion: str, mgl: float):
    eq = IONS[ion]["eqWt"]
    return None if eq is None else mgl / eq


def ppm_caco3(ion: str, mgl: float):
    f = IONS[ion]["caco3Factor"]
    return None if f is None else mgl * f


def compute_tds(ions: dict) -> float:
    """TDS = sum of all ions (incl. SiO2) with boron counted as boric acid."""
    factor = CFG["tds"]["boronAsBoricAcidFactor"]
    return sum(v for k, v in ions.items() if k != "B" and k in IONS) + ions.get("B", 0) * factor


def charge_totals(ions: dict):
    cations = sum(meq(k, ions.get(k, 0)) for k in CATIONS)
    anions = sum(meq(k, ions.get(k, 0)) for k in ANIONS)
    return cations, anions, cations - anions


def _validate(water: dict) -> list:
    msgs = []
    v = CFG["validation"]
    t = water.get("temperatureC")
    if t is None or not (v["temperatureC"]["min"] <= t <= v["temperatureC"]["max"]):
        msgs.append({"level": "error",
                     "text": f"Temperature must be between {v['temperatureC']['min']} and "
                             f"{v['temperatureC']['max']} °C."})
    ph = water.get("pH")
    if ph is None or not (v["pH"]["min"] <= ph <= v["pH"]["max"]):
        msgs.append({"level": "error",
                     "text": f"pH must be between {v['pH']['min']} and {v['pH']['max']}."})
    if not water.get("specifyIndividualSolutes", True) and not water.get("tdsInput"):
        msgs.append({"level": "info", "text": "Enter the TDS of the water."})
    if any((water.get("ions") or {}).get(k, 0) < 0 for k in ORDER):
        msgs.append({"level": "error", "text": "Ion concentrations cannot be negative."})
    return msgs


def analyze(water: dict) -> dict:
    ions = effective_ions(water)
    rows = {
        k: {"mgL": ions[k], "ppmCaCO3": ppm_caco3(k, ions[k]), "meq": meq(k, ions[k]),
            "group": IONS[k]["group"]}
        for k in ORDER
    }
    cations, anions, balance = charge_totals(ions)
    biggest = max(cations, anions)
    fraction = abs(balance) / biggest if biggest > 0 else 0.0
    # TODO-CONFIRM: imbalance threshold is provisional (config balance.imbalanceWarningFraction)
    imbalance = fraction > CFG["balance"]["imbalanceWarningFraction"]
    messages = []
    if imbalance:
        messages.append({"level": "warning", "text": CFG["balance"]["warningText"]})
    messages += _validate(water)
    return {
        "rows": rows,
        "order": ORDER,
        "ionsMgL": ions,
        "tds": compute_tds(ions),
        "cations": cations,
        "anions": anions,
        "balance": balance,
        "imbalanceFraction": fraction,
        "imbalance": imbalance,
        "messages": messages,
    }


def auto_balance(water: dict) -> dict:
    """Return a copy of the water with Na (anion excess) or Cl (cation excess) adjusted."""
    out = copy.deepcopy(water)
    ions = effective_ions(water)
    _, _, balance = charge_totals(ions)
    b = abs(balance)
    if CFG["balance"]["autoBalanceRoundTo1Decimal"]:
        b = round_half_up(b, 1)
    if b == 0:
        return out
    if balance < 0:
        ion = CFG["balance"]["anionExcessIon"]
    else:
        ion = CFG["balance"]["cationExcessIon"]  # TODO-CONFIRM: provisional
    ions[ion] = _round_mgl(ions[ion] + b * IONS[ion]["eqWt"])
    # Balancing switches the water to individual solutes so the correction is kept.
    out["specifyIndividualSolutes"] = True
    out["ions"] = ions
    return out
