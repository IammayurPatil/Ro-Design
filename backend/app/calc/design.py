"""Design System engine (prompt section 6).

Confirmed (6.2): feed / concentrate flows, system flux, unit conversions.
PROVISIONAL (6.3): the element-by-element simulation below. TODO-CONFIRM everything in it.
Internal units: m3/h, bar, mg/L, C, m2.
"""
import copy
import math

from scipy.optimize import brentq

from app.calc import scaling as scaling_calc
from app.calc.units import (UNITS, bar_to_psi, ft2_to_m2, gfd_to_lmh, m3h_to_gpd, m3h_to_gpm,
                            psi_to_bar)
from app.calc.water import IONS, ORDER, compute_tds, effective_ions
from app.config import load

CFG = load("design")
ION_CFG = load("ions")
WATER_TYPES = load("water_types")
ELEMENTS = {e["model"]: e for e in load("elements")}

REQUIRED_DATASHEET = ["areaFt2", "testFlowGpd", "testRejectionPct", "testPressurePsi",
                      "testNaClMgL", "testRecoveryPct", "testTempC", "dpK"]


class EngineError(Exception):
    pass


# ---- physics helpers (TODO-CONFIRM: all provisional) ----------------------------------------
def tcf(T: float) -> float:
    c = CFG["tcf"]
    k = c["kHigh"] if T >= c["switchTempC"] else c["kLow"]
    return math.exp(k * (1 / c["refTempK"] - 1 / (T + 273.15)))


def osmotic_bar(ions: dict, T: float) -> float:
    total_molarity = sum(v / (IONS[k]["molWt"] * 1000.0) for k, v in ions.items() if k in IONS)
    return CFG["osmotic"]["R"] * (T + 273.15) * total_molarity


def avg_conc_factor(r: float) -> float:
    if r < 1e-9:
        return 1.0
    return math.log(1 / (1 - r)) / r


def cpf(r: float) -> float:
    return math.exp(CFG["cpf"]["coefficient"] * r)


def pressure_drop(k: float, q_avg: float) -> float:
    return k * q_avg ** CFG["pressureDrop"]["exponent"]


# ---- element model ----------------------------------------------------------------------------
def element_constants(model: str) -> dict:
    el = ELEMENTS.get(model)
    if el is None:
        raise EngineError(f"Unknown element model {model!r}.")
    missing = [k for k in REQUIRED_DATASHEET if el.get(k) is None]
    if missing:
        raise EngineError(
            f"Element {model} is missing datasheet values: {', '.join(missing)}. "
            "Fill them in backend/app/config/elements.json to run the pressure calculation.")
    area = ft2_to_m2(el["areaFt2"])
    q_test = el["testFlowGpd"] / UNITS["gpmToGpd"] * UNITS["gpmToM3h"]
    p_test = psi_to_bar(el["testPressurePsi"])
    rej = el["testRejectionPct"] / 100.0
    r = el["testRecoveryPct"] / 100.0
    t_test = el["testTempC"]
    split = ION_CFG["tdsOnlyMode"]["split"]
    feed = {k: el["testNaClMgL"] * f for k, f in split.items()}
    pi_f = osmotic_bar(feed, t_test)
    pi_p = pi_f * (1 - rej)
    q_feed = q_test / r
    dp = pressure_drop(el["dpK"], q_feed - q_test / 2)
    ndp_test = p_test - dp / 2 - (pi_f * avg_conc_factor(r) * cpf(r) - pi_p)
    if ndp_test <= 0:
        raise EngineError(f"Element {model}: datasheet test conditions give a non-positive NDP.")
    t = tcf(t_test)
    A = q_test / (area * ndp_test) / t                    # m3/h per m2 per bar, at 25 C
    B = q_test * (1 - rej) / (rej * area) / t             # m3/h per m2, at 25 C
    return {"model": model, "area": area, "areaFt2": el["areaFt2"], "A": A, "B": B, "dpK": el["dpK"],
            "raw": el}


def simulate_element(el: dict, qf: float, pf: float, ions_f: dict, T: float, pp: float, ff: float) -> dict:
    """One element. Iterates until the permeate flow is stable."""
    s = CFG["solver"]
    t = tcf(T)
    ratio = CFG["ionPassageRatio"]
    pi_f = osmotic_bar(ions_f, T)
    b = {k: el["B"] * ratio.get(k, 1.0) * el["area"] * t for k in ions_f}

    def state(qp):
        r = min(max(qp / qf, 0.0), 0.99)
        caf, beta = avg_conc_factor(r), cpf(r)
        qc = qf - qp
        dp = pressure_drop(el["dpK"], (qf + qc) / 2)
        cp = {k: (b[k] * c * caf * beta / (qp + b[k]) if qp > 0 else 0.0) for k, c in ions_f.items()}
        pi_p = osmotic_bar(cp, T)
        ndp = pf - dp / 2 - pp - (pi_f * caf * beta - pi_p)
        q_new = el["A"] * el["area"] * t * ff * max(ndp, 0.0)
        return q_new, dict(r=r, beta=beta, dp=dp, cp=cp, ndp=ndp, pi_f=pi_f, pi_p=pi_p, caf=caf)

    qp = min(el["A"] * el["area"] * t * ff * max(pf - pi_f, 0.0), 0.5 * qf)
    converged = False
    for _ in range(s["elementMaxIterations"]):
        q_new, _st = state(qp)
        q_next = min(0.5 * qp + 0.5 * q_new, 0.99 * qf)
        if abs(q_next - qp) <= s["elementTolerance"] * max(qf, 1e-12):
            qp = q_next
            converged = True
            break
        qp = q_next
    if not converged:  # fall back to a bracketing root finder
        g = lambda q: q - state(q)[0]
        hi = 0.99 * qf
        qp = brentq(g, 0.0, hi, xtol=1e-12) if g(hi) > 0 else hi
    _, st = state(qp)
    qc = qf - qp
    cc = {k: (qf * c - qp * st["cp"][k]) / qc for k, c in ions_f.items()}
    flux_gfd = m3h_to_gpd(qp) / el["areaFt2"]
    return {
        "model": el["model"],
        "feedFlow": qf, "permeateFlow": qp, "concentrateFlow": qc,
        "recoveryPct": qp / qf * 100,
        "feedPressure": pf, "concentratePressure": pf - st["dp"], "pressureDrop": st["dp"],
        "ndp": st["ndp"], "beta": st["beta"],
        "osmoticFeed": st["pi_f"], "osmoticPermeate": st["pi_p"],
        "fluxGfd": flux_gfd, "fluxLmh": gfd_to_lmh(flux_gfd),
        "feedTDS": compute_tds(ions_f), "permeateTDS": compute_tds(st["cp"]), "concentrateTDS": compute_tds(cc),
        "feedIons": ions_f, "permeateIons": st["cp"], "concentrateIons": cc,
    }


def _mix(streams):
    """Flow-weighted mix of [(flow, ions)]."""
    total = sum(q for q, _ in streams)
    if total <= 0:
        return {k: 0.0 for k in ORDER}
    return {k: sum(q * ions.get(k, 0) for q, ions in streams) / total for k in ORDER}


def simulate_pass(pass_cfg: dict, qf: float, pf: float, ions_f: dict, T: float, ff: float) -> dict:
    stages_cfg = _resolved_stages(pass_cfg)
    stages = []
    q, p, ions = qf, pf, ions_f
    permeates = []
    for i, st in enumerate(stages_cfg):
        el = element_constants(st["elementModel"])
        nv = int(st["vessels"])
        q_vessel = q / nv
        booster = 0.0  # TODO-CONFIRM: booster pressure model not defined yet
        p_in = p + booster
        elements = []
        qe, pe, ie = q_vessel, p_in, ions
        for _ in range(int(st["elementsPerVessel"])):
            res = simulate_element(el, qe, pe, ie, T, st["backPressure"], ff)
            elements.append(res)
            qe, pe, ie = res["concentrateFlow"], res["concentratePressure"], res["concentrateIons"]
        perm_ions = _mix([(e["permeateFlow"], e["permeateIons"]) for e in elements])
        qp_stage = sum(e["permeateFlow"] for e in elements) * nv
        n_el = nv * int(st["elementsPerVessel"])
        flux = m3h_to_gpd(qp_stage) / (n_el * el["areaFt2"])
        stages.append({
            "stage": i + 1, "vessels": nv, "elementsPerVessel": int(st["elementsPerVessel"]),
            "elementModel": st["elementModel"], "backPressure": st["backPressure"],
            "boosterPressure": booster,
            "feedFlow": q, "permeateFlow": qp_stage, "concentrateFlow": qe * nv,
            "feedPressure": p_in, "concentratePressure": pe, "pressureDrop": p_in - pe,
            "fluxGfd": flux, "fluxLmh": gfd_to_lmh(flux),
            "feedTDS": compute_tds(ions), "permeateTDS": compute_tds(perm_ions), "concentrateTDS": compute_tds(ie),
            "permeateIons": perm_ions, "concentrateIons": ie,
            "elements": [{**{k: v for k, v in e.items() if not k.endswith("Ions")}, "position": j + 1}
                         for j, e in enumerate(elements)],
        })
        permeates.append((qp_stage, perm_ions))
        q, p, ions = qe * nv, pe, ie
    perm_ions = _mix(permeates)
    return {
        "stages": stages,
        "feedFlow": qf, "feedPressure": pf, "feedIons": ions_f,
        "permeateFlow": sum(x for x, _ in permeates), "permeateIons": perm_ions,
        "concentrateFlow": q, "concentrateIons": ions, "concentratePressure": p,
    }


def _resolved_stages(pass_cfg: dict) -> list:
    stages = copy.deepcopy(pass_cfg["stages"])
    if pass_cfg.get("sameElementInPass", True):
        for s in stages:
            s["elementModel"] = stages[0]["elementModel"]
    if pass_cfg.get("sameBackPressure", True):
        for s in stages:
            s["backPressure"] = stages[0].get("backPressure", 0)
    for s in stages:
        s["backPressure"] = float(s.get("backPressure") or 0)
    return stages


def solve_pass(pass_cfg, qf, ions_f, T, ff, target_qp) -> dict:
    """Find the feed pressure (brentq) so the pass permeate equals the target."""
    s = CFG["solver"]
    lo, hi = s["minFeedPressureBar"], s["maxFeedPressureBar"]
    f = lambda p: simulate_pass(pass_cfg, qf, p, ions_f, T, ff)["permeateFlow"] - target_qp
    f_hi = f(hi)
    if f_hi < 0:
        raise EngineError(f"The target permeate flow cannot be reached below {hi:g} bar "
                          f"({bar_to_psi(hi):.0f} psi). Add elements or lower the recovery.")
    f_lo = f(lo)
    p = lo if f_lo >= 0 else brentq(f, lo, hi, xtol=1e-7)
    res = simulate_pass(pass_cfg, qf, p, ions_f, T, ff)
    if f_lo < 0 and abs(res["permeateFlow"] - target_qp) > s["permeateTolerance"] * target_qp:
        raise EngineError("The feed pressure solver did not converge.")
    return res


# ---- limits ------------------------------------------------------------------------------------
def water_type_limits(name: str) -> dict:
    lim = copy.deepcopy(WATER_TYPES["defaults"])
    for t in WATER_TYPES["types"]:
        if t["name"] == name:
            lim.update(t.get("limits") or {})
    return lim


def _check_limits(passes: list, water_type: str, messages: list, engine_ok: bool):
    """TODO-CONFIRM: all design limits are provisional."""
    lim = water_type_limits(water_type)

    def warn(text):
        messages.append({"level": "warning", "text": text})

    for pi, ps in enumerate(passes):
        for st in ps["stages"]:
            where = f"Pass {pi + 1}, stage {st['stage']}"
            feed_gpm = m3h_to_gpm(st["feedFlow"] / st["vessels"])
            if lim.get("maxFeedPerVesselGpm") is not None and feed_gpm > lim["maxFeedPerVesselGpm"]:
                warn(f"{where}: feed flow per vessel is {feed_gpm:.1f} gpm, above the limit of "
                     f"{lim['maxFeedPerVesselGpm']:g} gpm.")
            if not engine_ok:
                continue
            conc_gpm = m3h_to_gpm(st["concentrateFlow"] / st["vessels"])
            if lim.get("minConcPerVesselGpm") is not None and conc_gpm < lim["minConcPerVesselGpm"]:
                warn(f"{where}: concentrate flow per vessel is {conc_gpm:.1f} gpm, below the minimum of "
                     f"{lim['minConcPerVesselGpm']:g} gpm.")
            dp_psi = bar_to_psi(st["pressureDrop"])
            if lim.get("maxDpPerVesselPsi") is not None and dp_psi > lim["maxDpPerVesselPsi"]:
                warn(f"{where}: pressure drop per vessel is {dp_psi:.1f} psi, above the limit of "
                     f"{lim['maxDpPerVesselPsi']:g} psi.")
            fl = lim.get("avgFluxGfd") or {}
            if fl.get("min") is not None and st["fluxGfd"] < fl["min"]:
                warn(f"{where}: average flux {st['fluxGfd']:.1f} gfd is below {fl['min']:g} gfd.")
            if fl.get("max") is not None and st["fluxGfd"] > fl["max"]:
                warn(f"{where}: average flux {st['fluxGfd']:.1f} gfd is above {fl['max']:g} gfd.")
            el_raw = ELEMENTS.get(st["elementModel"], {})
            for e in st.get("elements", []):
                tag = f"{where}, element {e['position']}"
                if lim.get("maxElementRecoveryPct") is not None and e["recoveryPct"] > lim["maxElementRecoveryPct"]:
                    warn(f"{tag}: recovery {e['recoveryPct']:.1f}% is above {lim['maxElementRecoveryPct']:g}%.")
                if el_raw.get("maxFeedGpm") is not None and m3h_to_gpm(e["feedFlow"]) > el_raw["maxFeedGpm"]:
                    warn(f"{tag}: feed flow is above the element maximum of {el_raw['maxFeedGpm']:g} gpm.")
                if el_raw.get("minConcGpm") is not None and m3h_to_gpm(e["concentrateFlow"]) < el_raw["minConcGpm"]:
                    warn(f"{tag}: concentrate flow is below the element minimum of {el_raw['minConcGpm']:g} gpm.")
                if el_raw.get("maxPressurePsi") is not None and bar_to_psi(e["feedPressure"]) > el_raw["maxPressurePsi"]:
                    warn(f"{tag}: feed pressure is above the element maximum of {el_raw['maxPressurePsi']:g} psi.")


# ---- main entry --------------------------------------------------------------------------
def _validate_design(d: dict, messages: list) -> bool:
    ok = True
    lim = CFG["limits"]

    def err(text):
        nonlocal ok
        ok = False
        messages.append({"level": "error", "text": text})

    rec = d.get("recoveryPct", 0)
    if not (0 < rec < 100):
        err("Recovery must be between 0% and 100%.")
    if not d.get("permeateFlow") or d["permeateFlow"] <= 0:
        err("Permeate flow must be greater than 0.")
    ff = d.get("foulingFactor", CFG["foulingFactor"]["default"])
    if not (CFG["foulingFactor"]["min"] <= ff <= CFG["foulingFactor"]["max"]):
        err(f"Fouling factor must be between {CFG['foulingFactor']['min']} and {CFG['foulingFactor']['max']}.")
    passes = d.get("passes") or []
    if not (1 <= len(passes) <= lim["maxPasses"]):
        err(f"Number of passes must be 1 to {lim['maxPasses']}.")
    for pi, ps in enumerate(passes):
        if not (1 <= len(ps.get("stages") or []) <= lim["maxStagesPerPass"]):
            err(f"Pass {pi + 1}: stages must be 1 to {lim['maxStagesPerPass']}.")
        for si, st in enumerate(ps.get("stages") or []):
            if int(st.get("vessels") or 0) < 1:
                err(f"Pass {pi + 1}, stage {si + 1}: at least 1 pressure vessel is needed.")
            if not (1 <= int(st.get("elementsPerVessel") or 0) <= lim["maxElementsPerVessel"]):
                err(f"Pass {pi + 1}, stage {si + 1}: elements per vessel must be 1 to {lim['maxElementsPerVessel']}.")
    t = d.get("feedTempC", 25)
    if not (1 <= t <= 45):
        err("Feed temperature must be between 1 and 45 °C.")
    return ok


def calculate(project: dict) -> dict:
    d = project["design"]
    messages = []
    system = {"feedFlow": None, "permeateFlow": d.get("permeateFlow"), "concentrateFlow": None,
              "recoveryPct": d.get("recoveryPct"), "totalElements": None, "fluxGfd": None, "fluxLmh": None,
              "feedPressure": None, "pumpKw": None, "specificEnergy": None, "feedTDS": None,
              "permeateTDS": None, "concentrateTDS": None, "simulatedPermeateFlow": None,
              "recycleFlow": 0.0, "feedIons": None, "permeateIons": None, "concentrateIons": None}
    result = {"system": system, "passes": [], "messages": messages, "engineOk": False}
    if not _validate_design(d, messages):
        return result

    R = d["recoveryPct"] / 100.0
    qp_target = float(d["permeateFlow"])
    n_passes = len(d["passes"])

    # ---- confirmed formulas (6.2) ----
    # TODO-CONFIRM: for 2 passes, each pass uses the same recovery (provisional).
    pass_targets = [qp_target / R ** (n_passes - 1 - i) for i in range(n_passes)]
    pass_feeds = [t / R for t in pass_targets]
    system["feedFlow"] = pass_feeds[0]
    system["concentrateFlow"] = pass_feeds[0] - qp_target
    if n_passes > 1:
        system["recoveryPct"] = qp_target / pass_feeds[0] * 100
        messages.append({"level": "info", "text": "Two-pass design: both passes use the same recovery (provisional)."})

    total_elements, area_ft2, pass1_area = 0, 0.0, 0.0
    for pi, ps in enumerate(d["passes"]):
        for st in _resolved_stages(ps):
            el = ELEMENTS.get(st["elementModel"])
            if el is None or el.get("areaFt2") is None:
                messages.append({"level": "error", "text": f"Unknown element model {st['elementModel']!r}."})
                return result
            n = int(st["vessels"]) * int(st["elementsPerVessel"])
            total_elements += n
            area_ft2 += n * el["areaFt2"]
            if pi == 0:
                pass1_area += n * el["areaFt2"]
    system["totalElements"] = total_elements
    pass1_perm = pass_targets[0]
    system["fluxGfd"] = m3h_to_gpd(pass1_perm) / pass1_area
    system["fluxLmh"] = gfd_to_lmh(system["fluxGfd"])

    # feed water: adjusted feed from the Scaling page if chemicals change the chemistry
    water = project["water"]
    feed_ions = effective_ions(water)
    sc = project.get("scaling") or {}
    if sc.get("option") in ("ph_adjust", "softening"):
        feed_ions = scaling_calc.calculate(water, sc)["columns"]["adjusted"]["ions"]
    system["feedIons"] = feed_ions
    system["feedTDS"] = compute_tds(feed_ions)

    T = float(d.get("feedTempC", 25))
    ff = float(d.get("foulingFactor", CFG["foulingFactor"]["default"]))
    eta = (d.get("pumpEfficiencyPct", 100) / 100.0) if d.get("pumpEfficiencyEnabled") else 1.0
    if d.get("intakeBothEnds"):
        messages.append({"level": "info", "text": "'Intake on both ends' is not modelled yet (open item)."})

    # ---- provisional engine (6.3) ----
    try:
        passes_out = []
        pump_kw = 0.0
        ions_in = feed_ions
        for pi, ps in enumerate(d["passes"]):
            q_raw, q_target = pass_feeds[pi], pass_targets[pi]
            recycle = d.get("recycle") or {}
            q_rec = float(recycle.get("flow") or 0) if (pi == 0 and recycle.get("enabled")) else 0.0
            if q_rec > 0:
                mixed = ions_in
                res = None
                for _ in range(CFG["solver"]["recycleMaxIterations"]):
                    res = solve_pass(ps, q_raw + q_rec, mixed, T, ff, q_target)
                    if q_rec >= res["concentrateFlow"]:
                        raise EngineError("The recycle flow is larger than the concentrate flow.")
                    new_mixed = _mix([(q_raw, ions_in), (q_rec, res["concentrateIons"])])
                    change = abs(compute_tds(new_mixed) - compute_tds(mixed)) / max(compute_tds(mixed), 1e-12)
                    mixed = new_mixed
                    if change < CFG["solver"]["recycleTolerance"]:
                        break
                res = solve_pass(ps, q_raw + q_rec, mixed, T, ff, q_target)
                system["recycleFlow"] = q_rec
            else:
                res = solve_pass(ps, q_raw, ions_in, T, ff, q_target)
            pump_flow = q_raw + q_rec
            res["pumpKw"] = pump_flow * res["feedPressure"] / (36 * eta)
            res["pass"] = pi + 1
            res["recoveryPct"] = q_target / q_raw * 100
            res["rawFeedFlow"] = q_raw
            pump_kw += res["pumpKw"]
            passes_out.append(res)
            ions_in = res["permeateIons"]
        last = passes_out[-1]
        first = passes_out[0]
        system.update({
            "feedPressure": first["feedPressure"],
            "pumpKw": pump_kw,
            "pumpEfficiencyPct": eta * 100,
            "specificEnergy": pump_kw / qp_target,
            "simulatedPermeateFlow": last["permeateFlow"],
            "permeateIons": last["permeateIons"],
            "permeateTDS": compute_tds(last["permeateIons"]),
            "concentrateIons": first["concentrateIons"],
            "concentrateTDS": compute_tds(first["concentrateIons"]),
        })
        result["passes"] = passes_out
        result["engineOk"] = True
        messages.append({"level": "info", "text": "Pressures and permeate quality come from a provisional engine."})
    except EngineError as e:
        messages.append({"level": "error", "text": str(e)})
        # still report the flow split per stage so the limit check and diagram work
        result["passes"] = [{"pass": pi + 1, "feedFlow": pass_feeds[pi], "permeateFlow": pass_targets[pi],
                             "stages": [{"stage": i + 1, "vessels": int(s["vessels"]),
                                         "elementsPerVessel": int(s["elementsPerVessel"]),
                                         "elementModel": s["elementModel"], "backPressure": s["backPressure"],
                                         "feedFlow": pass_feeds[pi] if i == 0 else None, "elements": []}
                                        for i, s in enumerate(_resolved_stages(ps))]}
                            for pi, ps in enumerate(d["passes"])]
    stages_for_check = [{"stages": [s for s in p["stages"] if s.get("feedFlow") is not None]}
                        for p in result["passes"]]
    _check_limits(stages_for_check, water.get("waterType", ""), messages, result["engineOk"])
    return result
