"""Golden tests 10.1 (scaling part) and 10.5-10.7: Scaling."""
import copy
import math

from conftest import GOLDEN, assert_close, make_water

from app.calc.scaling import calculate

TOL = GOLDEN["tolerances"]
SAT_REL = TOL["saturationPct"]["rel"]
SIO2_CONC_REL = TOL["silicaConcentratePct"]["rel"]
SIO2_T_ABS = TOL["silicaTemperaturePct"]["abs"]
SDSI_T_ABS = TOL["sdsiTemperature"]["abs"]
SALTS = ("CaSO4", "BaSO4", "SrSO4", "CaF2")


def scaling(recovery, temp=25, option="none", **kw):
    s = {
        "recoveryPct": recovery,
        "temperatureC": temp,
        "option": option,
        "phAdjust": {"chemical": "H2SO4", "targetPH": 7.5},
        "softening": {"caLeakage": 0.1, "mgLeakage": 0.1},
    }
    s.update(kw)
    return s


def warning_salts(result):
    out = []
    for m in result["messages"]:
        if m["level"] == "warning" and "Saturation limits" in m["text"]:
            out.append(m["text"].split(" ")[0])
    return out


# ---- 10.1 NaCl sample ----------------------------------------------------------------------
def test_nacl_scaling_15pct(golden):
    e = golden["scaling"]["naclRecovery15"]["expect"]
    water = make_water(specifyIndividualSolutes=False, tdsInput=2000, pH=7.5)
    r = calculate(water, scaling(15))
    assert abs(r["cf"] - e["cf"]) < 0.0001
    assert_close(r["columns"]["concentrate"]["TDS"], e["tdsConc"], label="TDS conc")
    assert_close(r["columns"]["feed"]["pH"], e["pHFeed"], label="pH feed")
    assert_close(r["columns"]["concentrate"]["pH"], e["pHConc"], label="pH conc")
    # No Ca / HCO3 -> no CaCO3 risk
    assert r["columns"]["feed"]["LSI"] is None
    assert r["columns"]["feed"]["SDSI"] is None


# ---- 10.5 Feed column + recovery sweep ----------------------------------------------------
def test_feed_column(golden, tc_water_a_balanced):
    e = golden["scaling"]["tcWaterABalancedFeed25C"]
    feed = calculate(tc_water_a_balanced, scaling(50))["columns"]["feed"]
    for k in ("pH", "CO2", "SDSI", "SiO2"):
        assert_close(feed[k], e[k], label=f"feed {k}")
    for k in SALTS:
        assert_close(feed[k], e[k], rel_tol=SAT_REL, label=f"feed {k}")


def test_recovery_sweep(golden, tc_water_a_balanced):
    for case in golden["scaling"]["recoverySweep25C"]:
        rec = case["recovery"]
        c = calculate(tc_water_a_balanced, scaling(rec))["columns"]["concentrate"]
        for k in ("pH", "SDSI"):
            assert_close(c[k], case[k], label=f"{rec}% {k}")
        assert_close(c["TDS"], case["TDS"], abs_tol=0.0, label=f"{rec}% TDS (exact)")
        for k in SALTS:
            assert_close(c[k], case[k], rel_tol=SAT_REL, label=f"{rec}% {k}")
        assert_close(c["SiO2"], case["SiO2"], rel_tol=SIO2_CONC_REL, label=f"{rec}% SiO2")


def test_co2_passes_through(tc_water_a_balanced):
    r = calculate(tc_water_a_balanced, scaling(75))["columns"]
    assert r["concentrate"]["CO2"] == r["adjusted"]["CO2"]
    assert r["concentrate"]["HCO3"] == r["adjusted"]["HCO3"] * 4


def test_srso4_jump_at_tds_4000(tc_water_a_balanced):
    c75 = calculate(tc_water_a_balanced, scaling(75))["columns"]["concentrate"]["SrSO4"]
    c76 = calculate(tc_water_a_balanced, scaling(76))["columns"]["concentrate"]["SrSO4"]
    assert c76 / c75 > 5


def test_warnings(golden, tc_water_a_balanced):
    for rec, expected in golden["scaling"]["warnings"].items():
        r = calculate(tc_water_a_balanced, scaling(int(rec)))
        assert warning_salts(r) == expected, f"{rec}%"
    r = calculate(tc_water_a_balanced, scaling(75))
    texts = [m["text"] for m in r["messages"]]
    assert ("CaCO3 Saturation limits  exceeded ,Antiscalants may be required or change your system design."
            in texts)


def test_antiscalant_same_as_none(tc_water_a_balanced):
    a = calculate(tc_water_a_balanced, scaling(80, option="antiscalant"))
    n = calculate(tc_water_a_balanced, scaling(80))
    assert a["columns"]["adjusted"] == n["columns"]["adjusted"]
    assert warning_salts(a) == warning_salts(n)


# ---- 10.6 Temperature ------------------------------------------------------------------------
def test_temperature_75pct(golden, tc_water_a_balanced):
    for case in golden["scaling"]["temperature75"]:
        T = case["T"]
        r = calculate(tc_water_a_balanced, scaling(75, temp=T))["columns"]
        for col, exp in (("feed", case["feed"]), ("concentrate", case["conc"])):
            for k in SALTS:
                assert_close(r[col][k], exp[k], rel_tol=SAT_REL, label=f"{T}C {col} {k}")
        assert_close(r["feed"]["SiO2"], case["feed"]["SiO2"], abs_tol=SIO2_T_ABS, label=f"{T}C feed SiO2")
        assert_close(r["concentrate"]["SiO2"], case["conc"]["SiO2"], rel_tol=SIO2_CONC_REL,
                     label=f"{T}C conc SiO2")


def test_sdsi_temperature(golden, tc_water_a_balanced):
    for case in golden["scaling"]["sdsiTemperature50pH7"]:
        w = copy.deepcopy(tc_water_a_balanced)
        w["pH"] = 7.0
        r = calculate(w, scaling(50, temp=case["T"]))["columns"]
        assert_close(r["feed"]["SDSI"], case["feed"], abs_tol=SDSI_T_ABS, label=f"{case['T']}C feed")
        assert_close(r["concentrate"]["SDSI"], case["conc"], abs_tol=SDSI_T_ABS, label=f"{case['T']}C conc")


# ---- 10.7 pH sweep -------------------------------------------------------------------------
def _at_ph(water, ph):
    w = copy.deepcopy(water)
    w["pH"] = ph
    return calculate(w, scaling(50))["columns"]


def test_ph_sweep_sdsi(golden, tc_water_a_balanced):
    g = golden["scaling"]["pHSweep50"]
    for ph in g["sdsiPHs"]:
        r = _at_ph(tc_water_a_balanced, ph)
        feed_expected = round(ph + g["sdsiFeedOffset"], 2)
        assert_close(r["feed"]["SDSI"], feed_expected, label=f"pH {ph} SDSI feed")
        assert_close(r["concentrate"]["SDSI"], round(feed_expected + g["sdsiConcMinusFeed"], 2),
                     label=f"pH {ph} SDSI conc")


def test_ph_sweep_lsi(golden, tc_water_a_balanced):
    for case in golden["scaling"]["pHSweep50"]["lsi"]:
        r = _at_ph(tc_water_a_balanced, case["pH"])
        assert_close(r["feed"]["LSI"], case["feed"], label=f"pH {case['pH']} LSI feed")
        assert_close(r["concentrate"]["LSI"], case["conc"], label=f"pH {case['pH']} LSI conc")


def test_ph_sweep_silica(golden, tc_water_a_balanced):
    for case in golden["scaling"]["pHSweep50"]["silicaFeed"]:
        r = _at_ph(tc_water_a_balanced, case["pH"])
        assert_close(r["feed"]["SiO2"], case["SiO2"], label=f"pH {case['pH']} SiO2")


# ---- Provisional options (behaviour checks, no Vontron data yet) -------------------------
def test_ph_adjust_with_acid(tc_water_a_balanced):
    r = calculate(tc_water_a_balanced, scaling(75, option="ph_adjust",
                                                phAdjust={"chemical": "H2SO4", "targetPH": 6.5}))
    feed, adj = r["columns"]["feed"], r["columns"]["adjusted"]
    assert adj["pH"] == 6.5
    assert adj["HCO3"] < feed["HCO3"]
    assert adj["ions"]["SO4"] > feed["ions"]["SO4"]
    meq = (feed["HCO3"] - adj["HCO3"]) / 61.017
    assert math.isclose(r["acidDose"]["meqPerL"], meq, rel_tol=1e-9)
    assert math.isclose(r["acidDose"]["mgL"], meq * 49.04, rel_tol=1e-9)
    # total carbonate conserved (molar basis)
    ct_feed = feed["HCO3"] / 61.017 * (1 + 10 ** (6.3 - feed["pH"]))
    ct_adj = adj["HCO3"] / 61.017 * (1 + 10 ** (6.3 - adj["pH"]))
    assert math.isclose(ct_feed, ct_adj, rel_tol=1e-9)
    assert adj["LSI"] < feed["LSI"]


def test_ph_adjust_hcl_adds_chloride(tc_water_a_balanced):
    r = calculate(tc_water_a_balanced, scaling(50, option="ph_adjust",
                                                phAdjust={"chemical": "HCl", "targetPH": 7.0}))
    assert r["columns"]["adjusted"]["ions"]["Cl"] > r["columns"]["feed"]["ions"]["Cl"]
    assert math.isclose(r["acidDose"]["mgL"], r["acidDose"]["meqPerL"] * 36.46)


def test_softening(tc_water_a_balanced):
    r = calculate(tc_water_a_balanced, scaling(75, option="softening",
                                                softening={"caLeakage": 0.1, "mgLeakage": 0.1}))
    adj = r["columns"]["adjusted"]["ions"]
    assert adj["Ca"] == 0.1 and adj["Mg"] == 0.1
    expected_na = 184.5 + ((80 - 0.1) / 20.04 + (25 - 0.1) / 12.15) * 23.00
    assert math.isclose(adj["Na"], expected_na, rel_tol=1e-9)
    assert "CaSO4" not in [m["text"].split(" ")[0] for m in r["messages"]]
