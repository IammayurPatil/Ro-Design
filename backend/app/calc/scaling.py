"""Scaling: CF, CO2, LSI, S&DSI, Ksp saturation, silica, chemical options (prompt section 5)."""
import math

from app.calc.units import round_half_up
from app.calc.water import IONS, ORDER, compute_tds, effective_ions
from app.config import load

CFG = load("scaling")
SILICA = load("silica_table")
CHARGED = [k for k in ORDER if IONS[k]["charge"] != 0]
SALTS = ["CaSO4", "BaSO4", "SrSO4", "CaF2"]
WARN_ORDER = ["CaCO3", "CaSO4", "BaSO4", "SrSO4", "CaF2", "SiO2"]
OPTIONS = ("none", "ph_adjust", "softening", "antiscalant")


# ---- basic helpers -------------------------------------------------------------------------
def concentration_factor(recovery_pct: float) -> float:
    return 1.0 / (1.0 - recovery_pct / 100.0)


def molarity(ion: str, mgl: float) -> float:
    return mgl / (IONS[ion]["molWt"] * 1000.0)


def ionic_strength(ions: dict) -> float:
    """I = 1/2 sum(c z^2) over charged ions (B, SiO2 and CO2 excluded)."""
    return 0.5 * sum(molarity(k, ions.get(k, 0)) * IONS[k]["charge"] ** 2 for k in CHARGED)


def co2_mgl(hco3: float, ph: float) -> float:
    return hco3 * 10 ** (CFG["co2"]["pK"] - ph)


def sdsi(ph: float, ca: float, hco3: float, I: float, T: float):
    if ca <= 0 or hco3 <= 0:
        return None
    c = CFG["sdsi"]
    # TODO-CONFIRM: coefficients confirmed for I = 0.02-0.13 only (seawater provisional)
    K = c["c0"] + c["c1"] * I + c["c2"] * I * I + c["cT"] * (T - 25)
    p_ca = -math.log10(ca / c["caDivisor"])
    p_alk = -math.log10(hco3 / c["alkDivisor"])
    return ph - p_ca - p_alk - K


def lsi(ph: float, ca: float, hco3: float, tds: float, T: float):
    if ca <= 0 or hco3 <= 0 or tds <= 0:
        return None
    c = CFG["lsi"]
    if c["lsiMode"] != "standard":
        # TODO-CONFIRM: "behaviour A" is not known yet; only the standard formula exists.
        raise ValueError(f"Unsupported lsiMode {c['lsiMode']!r}")
    A = (math.log10(tds) - c["aOffset"]) / c["aDivisor"]
    B = c["bSlope"] * math.log10(T + 273.15) + c["bIntercept"]
    C = math.log10(ca * c["caToCaCO3"]) - c["cOffset"]
    D = math.log10(hco3)  # Vontron uses HCO3 mg/L directly, not as CaCO3
    phs = c["base"] + A + B - C - D
    return ph - phs


def ksp(salt_key: str, I: float, T: float) -> float:
    # TODO-CONFIRM: general Ksp(I, T) form is provisional
    s = CFG["ksp"]["salts"][salt_key]
    ref = CFG["ksp"]["refTempK"]
    return s["K"] * I ** s["n"] * math.exp(s["E"] * (1 / ref - 1 / (T + 273.15)))


def _sr_key(tds: float) -> str:
    k = CFG["ksp"]
    # TODO-CONFIRM: replicateVontronSrSO4Jump awaits a client decision
    if k["replicateVontronSrSO4Jump"] and tds > k["srso4TdsThreshold"]:
        return "SrSO4_highTDS"
    return "SrSO4"


def saturation_pct(salt: str, ions: dict, I: float, T: float, tds: float) -> float:
    key = _sr_key(tds) if salt == "SrSO4" else salt
    s = CFG["ksp"]["salts"][key]
    product = molarity(s["cation"], ions.get(s["cation"], 0)) * \
        molarity(s["anion"], ions.get(s["anion"], 0)) ** s["anionPower"]
    if product <= 0:
        return 0.0
    if I <= 0:
        return None
    return product / ksp(key, I, T) * 100.0


def silica_table_value(ph: float) -> float:
    pts = SILICA["points"]
    if ph <= pts[0][0]:
        return pts[0][1]
    if ph >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= ph <= x1:
            return y0 + (y1 - y0) * (ph - x0) / (x1 - x0)
    return pts[-1][1]


def silica_limit(ph: float, T: float) -> float:
    return silica_table_value(ph) * (T + SILICA["tempOffset"]) / SILICA["tempDivisor"]


def silica_pct(sio2: float, ph: float, T: float) -> float:
    return sio2 / silica_limit(ph, T) * 100.0


# ---- one column of the result table ---------------------------------------------------------
def column(ions: dict, ph: float, T: float, co2: float = None, tds: float = None) -> dict:
    tds = compute_tds(ions) if tds is None else tds
    I = ionic_strength(ions)
    ca, hco3 = ions.get("Ca", 0), ions.get("HCO3", 0)
    col = {
        "pH": ph,
        "TDS": tds,
        "HCO3": hco3,
        "CO3": ions.get("CO3", 0),
        "CO2": co2_mgl(hco3, ph) if co2 is None else co2,
        "LSI": lsi(ph, ca, hco3, tds, T),
        "SDSI": sdsi(ph, ca, hco3, I, T),
        "ionicStrength": I,
        "SiO2": silica_pct(ions.get("SiO2", 0), ph, T),
        "ions": dict(ions),
    }
    for s in SALTS:
        col[s] = saturation_pct(s, ions, I, T, tds)
    return col


# ---- chemical options -------------------------------------------------------------------------
def _ph_adjust(ions: dict, ph: float, opts: dict, messages: list):
    """Acid dosing: convert HCO3 -> CO2 to reach the target pH. TODO-CONFIRM (no Vontron data)."""
    pk = CFG["co2"]["pK"]
    target = float(opts.get("targetPH", ph))
    chem = opts.get("chemical", "H2SO4")
    acid = CFG["phAdjust"]["acids"].get(chem)
    if acid is None:
        messages.append({"level": "error", "text": f"Unknown acid {chem!r}. Use H2SO4 or HCl."})
        return dict(ions), ph, None
    if target > ph:
        messages.append({"level": "warning",
                         "text": "The target pH is higher than the feed pH. Only acid dosing is "
                                 "supported, so the feed was not changed."})
        return dict(ions), ph, None
    mw = IONS["HCO3"]["molWt"]
    h = ions.get("HCO3", 0) / mw                      # mmol/L
    total_c = h * (1 + 10 ** (pk - ph))               # HCO3 + CO2 (mmol/L), conserved
    h_new = total_c / (1 + 10 ** (pk - target))
    acid_meq = h - h_new
    out = dict(ions)
    out["HCO3"] = h_new * mw
    out[acid["addsIon"]] = out.get(acid["addsIon"], 0) + acid_meq * acid["ionMgPerMeq"]
    dose = {"chemical": chem, "meqPerL": acid_meq, "mgL": acid_meq * acid["doseMgPerMeq"]}
    return out, target, dose


def _soften(ions: dict, opts: dict):
    """Ion exchange softening. TODO-CONFIRM (no Vontron data)."""
    s = CFG["softening"]
    ca_leak = float(opts.get("caLeakage", 0))
    mg_leak = float(opts.get("mgLeakage", 0))
    out = dict(ions)
    ca, mg = ions.get("Ca", 0), ions.get("Mg", 0)
    ca_new, mg_new = min(ca, ca_leak), min(mg, mg_leak)
    out["Ca"], out["Mg"] = ca_new, mg_new
    out["Na"] = ions.get("Na", 0) + ((ca - ca_new) / s["caEqWt"] + (mg - mg_new) / s["mgEqWt"]) * s["naEqWt"]
    return out


def warning_text(x: str) -> str:
    return CFG["warnings"]["textTemplate"].replace("{X}", x)


def _limits(option: str):
    w = CFG["warnings"]
    if option == "antiscalant":
        # TODO-CONFIRM: antiscalant limits are provisional
        a = w["antiscalantLimits"]
        return a["lsiThreshold"], a["saturationLimitPct"]
    return w["lsiThreshold"], w["saturationLimitPct"]


def index_status(conc: dict, option: str) -> dict:
    """Traffic light per index for the dashboard: green / amber / red."""
    lsi_thr, sat = _limits(option)
    amber = CFG["trafficLight"]["amberFraction"]
    out = {}
    for name in SALTS + ["SiO2"]:
        v = conc.get(name)
        lim = sat[name]
        if v is None:
            out[name] = {"value": None, "limit": lim, "status": "n/a"}
            continue
        status = "red" if v > lim else "amber" if v >= amber * lim else "green"
        out[name] = {"value": v, "limit": lim, "status": status}
    v = conc.get("LSI")
    if v is None:
        out["CaCO3"] = {"value": None, "limit": lsi_thr, "status": "n/a", "index": "LSI"}
    else:
        # LSI is a difference, not a ratio: amber within a band below the threshold. TODO-CONFIRM
        band = CFG["trafficLight"]["lsiAmberBand"]
        status = "red" if v > lsi_thr else "amber" if v > lsi_thr - band else "green"
        out["CaCO3"] = {"value": v, "limit": lsi_thr, "status": status, "index": "LSI"}
    return out


# ---- main entry --------------------------------------------------------------------------
def calculate(water: dict, scaling: dict) -> dict:
    messages = []
    recovery = float(scaling.get("recoveryPct", 0))
    T = float(scaling.get("temperatureC", water.get("temperatureC", 25)))
    option = scaling.get("option", "none")
    if option not in OPTIONS:
        messages.append({"level": "error", "text": f"Unknown option {option!r}."})
        option = "none"
    if not (0 <= recovery < 100):
        messages.append({"level": "error", "text": "Recovery must be at least 0% and below 100%."})
        recovery = min(max(recovery, 0), 99)
    if not (1 <= T <= 45):
        messages.append({"level": "error", "text": "Temperature must be between 1 and 45 °C."})

    feed_ions = effective_ions(water)
    feed_ph = float(water.get("pH", 7))
    feed = column(feed_ions, feed_ph, T)

    acid_dose = None
    if option == "ph_adjust":
        # TODO-CONFIRM: provisional pH adjust logic
        adj_ions, adj_ph, acid_dose = _ph_adjust(feed_ions, feed_ph, scaling.get("phAdjust") or {}, messages)
        adjusted = column(adj_ions, adj_ph, T)
        messages.append({"level": "info", "text": "pH adjustment logic is provisional (no Vontron data yet)."})
    elif option == "softening":
        # TODO-CONFIRM: provisional softening logic
        adjusted = column(_soften(feed_ions, scaling.get("softening") or {}), feed_ph, T)
        messages.append({"level": "info", "text": "Softening logic is provisional (no Vontron data yet)."})
    else:
        adjusted = column(feed_ions, feed_ph, T)

    cf = concentration_factor(recovery)
    conc_ions = {k: v * cf for k, v in adjusted["ions"].items()}
    ct = CFG["concentrateTds"]
    feed_tds = round_half_up(adjusted["TDS"], ct["decimals"]) if ct["useRoundedFeedTds"] else adjusted["TDS"]
    # CO2 passes through the membrane: concentrate CO2 = adjusted CO2
    concentrate = column(conc_ions, adjusted["pH"] + math.log10(cf), T, co2=adjusted["CO2"], tds=feed_tds * cf)

    if concentrate["ionicStrength"] > CFG["sdsi"]["confirmedMaxIonicStrength"]:
        messages.append({"level": "info",
                         "text": "Ionic strength is above 0.13 (seawater range): S&DSI is provisional."})

    lsi_thr, sat = _limits(option)
    exceeded = []
    if concentrate["LSI"] is not None and concentrate["LSI"] > lsi_thr:  # TODO-CONFIRM threshold
        exceeded.append("CaCO3")
    for name in SALTS + ["SiO2"]:
        v = concentrate[name]
        if v is not None and v > sat[name]:
            exceeded.append(name)
    for x in WARN_ORDER:
        if x in exceeded:
            messages.append({"level": "warning", "text": warning_text(x), "index": x})

    return {
        "cf": cf,
        "recoveryPct": recovery,
        "temperatureC": T,
        "option": option,
        "columns": {"feed": feed, "adjusted": adjusted, "concentrate": concentrate},
        "acidDose": acid_dose,
        "status": index_status(concentrate, option),
        "messages": messages,
    }
