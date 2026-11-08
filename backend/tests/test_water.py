"""Golden tests 10.1-10.4: Water Analysis."""
import copy

from conftest import assert_close, make_water

from app.calc.water import analyze, auto_balance


def row(result, ion):
    return result["rows"][ion]


# ---- 10.1 NaCl-only sample (TDS-only mode, TDS = 2000) ----------------------------------
def test_nacl_tds_only_2000(golden):
    g = golden["water"]["naclTds2000"]
    water = make_water(**g["water"])
    r = analyze(water)
    e = g["expect"]
    assert_close(row(r, "Na")["mgL"], e["Na"], label="Na mg/L")
    assert_close(row(r, "Na")["ppmCaCO3"], e["Na_ppm"], label="Na ppm")
    assert_close(row(r, "Cl")["mgL"], e["Cl"], label="Cl mg/L")
    assert_close(row(r, "Cl")["ppmCaCO3"], e["Cl_ppm"], label="Cl ppm")
    assert_close(r["tds"], e["tds"], label="TDS")


def test_tds_only_mode_locks_other_ions():
    water = make_water({"Ca": 50, "SO4": 99}, specifyIndividualSolutes=False, tdsInput=1000)
    r = analyze(water)
    for ion in ("Ca", "SO4", "Mg", "SiO2", "B"):
        assert row(r, ion)["mgL"] == 0
    assert r["ionsMgL"]["Ca"] == 0


# ---- 10.2 TDS-only mode -------------------------------------------------------------------
def test_tds_only_cases(golden):
    for case in golden["water"]["tdsOnly"]:
        r = analyze(make_water(specifyIndividualSolutes=False, tdsInput=case["tds"]))
        e = case["expect"]
        assert_close(row(r, "Na")["mgL"], e["Na"], label=f"TDS {case['tds']} Na")
        assert_close(row(r, "Na")["meq"], e["Na_meq"], label=f"TDS {case['tds']} Na meq")
        assert_close(row(r, "Cl")["mgL"], e["Cl"], label=f"TDS {case['tds']} Cl")
        assert_close(row(r, "Cl")["meq"], e["Cl_meq"], label=f"TDS {case['tds']} Cl meq")
        if "balance" in e:
            assert_close(r["balance"], e["balance"], dp=1, label="balance")


# ---- 10.3 TC-Water A before balancing -----------------------------------------------------
def test_tc_water_a_conversions(golden, tc_water_a):
    g = golden["water"]["tcWaterA"]
    r = analyze(tc_water_a)
    for ion, v in g["expectPpm"].items():
        assert_close(row(r, ion)["ppmCaCO3"], v, label=f"{ion} ppm")
    for ion, v in g["expectMeq"].items():
        assert_close(row(r, ion)["meq"], v, label=f"{ion} meq")
    t = g["expectTotals"]
    assert_close(r["tds"], t["tds"], label="TDS")
    assert_close(r["cations"], t["cations"], dp=1, label="cations")
    assert_close(r["anions"], t["anions"], dp=1, label="anions")
    assert_close(r["balance"], t["balance"], dp=1, label="balance")
    assert r["imbalance"] is True
    assert "Warning:Ions out of Balance." in r["messages"][0]["text"]


def test_neutral_ions_have_no_ppm_or_meq(tc_water_a):
    r = analyze(tc_water_a)
    for ion in ("B", "SiO2"):
        assert row(r, ion)["ppmCaCO3"] is None
        assert row(r, ion)["meq"] is None


def test_small_imbalance_does_not_warn():
    # Na/Cl almost exactly balanced (TDS-only split): |balance| / max = ~0.1%
    r = analyze(make_water(specifyIndividualSolutes=False, tdsInput=5000))
    assert r["imbalance"] is False
    assert not any(m["level"] == "warning" for m in r["messages"])


# ---- 10.4 TC-Water A after Auto Balance ---------------------------------------------------
def test_auto_balance(golden, tc_water_a):
    g = golden["water"]["tcWaterA"]["afterBalance"]
    balanced = auto_balance(tc_water_a)
    r = analyze(balanced)
    assert_close(balanced["ions"]["Na"], g["Na"], label="Na")
    assert_close(row(r, "Na")["meq"], g["Na_meq"], label="Na meq")
    assert_close(row(r, "Na")["ppmCaCO3"], g["Na_ppm"], label="Na ppm")
    assert_close(r["tds"], g["tds"], label="TDS")
    assert_close(r["balance"], g["balance"], dp=1, label="balance")
    for v in g["tdsVariants"]:
        w = copy.deepcopy(balanced)
        w["ions"].update(v["change"])
        assert_close(analyze(w)["tds"], v["tds"], label=f"TDS with {v['change']}")


def test_auto_balance_cation_excess_adds_cl():
    w = make_water({"Na": 100, "Cl": 50})
    b = auto_balance(w)
    assert b["ions"]["Na"] == 100
    assert b["ions"]["Cl"] > 50


def test_tds_is_recomputed_not_stored(tc_water_a):
    # A stale tdsInput in individual-solute mode must be ignored (Vontron bug not replicated).
    tc_water_a["tdsInput"] = 12345
    assert abs(analyze(tc_water_a)["tds"] - 945.422) < 1e-6


def test_validation_messages():
    r = analyze(make_water(temperatureC=50, pH=14))
    texts = " ".join(m["text"] for m in r["messages"])
    assert "Temperature" in texts and "pH" in texts
