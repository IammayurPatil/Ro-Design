"""Golden test 10.1 (design part) and behaviour checks for the PROVISIONAL engine.

The engine tests use a SYNTHETIC test element defined here (not in config): the real
LP22-8040 datasheet values are still TODO.
"""
import copy
import math

import pytest

from conftest import assert_close, make_water

from app.calc import design
from app.calc.units import UNITS

GPM = UNITS["gpmToM3h"]

SYNTHETIC_ELEMENT = {
    "model": "TEST-8040",
    "areaFt2": 400,
    "testFlowGpd": 10500,
    "testRejectionPct": 99.5,
    "testPressurePsi": 225,
    "testNaClMgL": 2000,
    "testRecoveryPct": 15,
    "testTempC": 25,
    "maxPressurePsi": 600,
    "maxFeedGpm": 75,
    "minConcGpm": 12,
    "dpK": 0.002,
}


def make_project(permeate_gpm=5, recovery=15, vessels=1, epv=1, model="LP22-8040", water=None, **design_kw):
    d = {
        "unitSet": "gpm_psi",
        "recoveryPct": recovery,
        "permeateFlow": permeate_gpm * GPM,
        "feedTempC": 25,
        "foulingFactor": 0.85,
        "passes": [{"stages": [{"vessels": vessels, "elementsPerVessel": epv, "elementModel": model,
                                "backPressure": 0}],
                    "sameElementInPass": True, "sameBackPressure": True}],
        "pumpEfficiencyEnabled": False,
        "pumpEfficiencyPct": 80,
        "intakeBothEnds": False,
        "frontEndPct": 50,
        "recycle": {"enabled": False, "flow": 0},
    }
    d.update(design_kw)
    return {
        "version": "1.0",
        "project": {"name": "t", "date": "2026-01-01", "designedBy": "Untitled", "company": "Untitled"},
        "water": water or make_water(specifyIndividualSolutes=False, tdsInput=2000),
        "scaling": {"recoveryPct": recovery, "temperatureC": 25, "option": "none",
                    "phAdjust": {"chemical": "H2SO4", "targetPH": 7.5},
                    "softening": {"caLeakage": 0.1, "mgLeakage": 0.1}},
        "design": d,
        "results": {},
    }


@pytest.fixture
def synthetic(monkeypatch):
    monkeypatch.setattr(design, "ELEMENTS", {**design.ELEMENTS, "TEST-8040": SYNTHETIC_ELEMENT})


# ---- 10.1 design (confirmed formulas) ------------------------------------------------------
def test_nacl_design_flows_and_flux(golden):
    g = golden["design"]["naclSample"]
    r = design.calculate(make_project(g["permeateGpm"], g["recoveryPct"], g["vessels"],
                                      g["elementsPerVessel"], g["elementModel"]))
    s = r["system"]
    assert_close(s["feedFlow"] / GPM, g["expect"]["feedGpm"], label="feed gpm")
    assert_close(s["fluxGfd"], g["expect"]["fluxGfd"], dp=1, label="flux gfd")
    assert math.isclose(s["fluxLmh"], s["fluxGfd"] * 1.698)
    assert math.isclose(s["concentrateFlow"], s["feedFlow"] - s["permeateFlow"])
    assert s["totalElements"] == 1


def test_missing_datasheet_gives_clear_error():
    r = design.calculate(make_project())
    assert r["engineOk"] is False
    errors = [m["text"] for m in r["messages"] if m["level"] == "error"]
    assert errors and "LP22-8040" in errors[0] and "testFlowGpd" in errors[0]
    assert r["system"]["feedPressure"] is None


# ---- engine with a synthetic element -------------------------------------------------------
def test_engine_hits_target_permeate(synthetic):
    p = make_project(permeate_gpm=20, recovery=50, vessels=2, epv=6, model="TEST-8040")
    r = design.calculate(p)
    assert r["engineOk"], r["messages"]
    s = r["system"]
    target = 20 * GPM
    assert abs(s["simulatedPermeateFlow"] - target) / target <= 0.001
    assert s["feedPressure"] > 0
    assert 0 < s["permeateTDS"] < s["feedTDS"] < s["concentrateTDS"]
    elements = r["passes"][0]["stages"][0]["elements"]
    assert len(elements) == 6
    # pressure falls along the vessel; flux falls too
    assert all(a["feedPressure"] > b["feedPressure"] for a, b in zip(elements, elements[1:]))
    assert elements[0]["fluxGfd"] > elements[-1]["fluxGfd"]
    # mass balance per element
    for el in elements:
        assert math.isclose(el["feedFlow"], el["permeateFlow"] + el["concentrateFlow"], rel_tol=1e-9)


def test_engine_two_stages_and_pump(synthetic):
    p = make_project(permeate_gpm=30, recovery=70, model="TEST-8040", pumpEfficiencyEnabled=True,
                     pumpEfficiencyPct=80)
    p["design"]["passes"][0]["stages"] = [
        {"vessels": 2, "elementsPerVessel": 6, "elementModel": "TEST-8040", "backPressure": 0},
        {"vessels": 1, "elementsPerVessel": 6, "elementModel": "TEST-8040", "backPressure": 0},
    ]
    r = design.calculate(p)
    assert r["engineOk"], r["messages"]
    s = r["system"]
    assert s["totalElements"] == 18
    expected_kw = s["feedFlow"] * s["feedPressure"] / (36 * 0.8)
    assert math.isclose(s["pumpKw"], expected_kw, rel_tol=1e-9)
    assert math.isclose(s["specificEnergy"], s["pumpKw"] / s["permeateFlow"], rel_tol=1e-9)
    st1, st2 = r["passes"][0]["stages"]
    assert math.isclose(st2["feedFlow"], st1["concentrateFlow"], rel_tol=1e-9)


def test_engine_temperature_effect(synthetic):
    p25 = make_project(permeate_gpm=20, recovery=50, vessels=2, epv=6, model="TEST-8040")
    p10 = copy.deepcopy(p25)
    p10["design"]["feedTempC"] = 10
    assert design.calculate(p10)["system"]["feedPressure"] > design.calculate(p25)["system"]["feedPressure"]


def test_engine_recycle_converges(synthetic):
    p = make_project(permeate_gpm=20, recovery=50, vessels=2, epv=6, model="TEST-8040",
                     recycle={"enabled": True, "flow": 5 * GPM})
    r = design.calculate(p)
    assert r["engineOk"], r["messages"]
    assert r["system"]["recycleFlow"] > 0
    assert math.isclose(r["system"]["feedFlow"], 40 * GPM, rel_tol=1e-9)


def test_engine_limit_warnings(synthetic):
    # 1 vessel with 1 element pushing 60 gpm of permeate: way over the 75 gpm feed limit
    p = make_project(permeate_gpm=12, recovery=15, vessels=1, epv=1, model="TEST-8040")
    r = design.calculate(p)
    texts = " ".join(m["text"] for m in r["messages"])
    assert "75" in texts


def test_tcf():
    assert math.isclose(design.tcf(25), 1.0)
    assert design.tcf(10) < 1 < design.tcf(35)
    assert math.isclose(design.tcf(10), math.exp(3020 * (1 / 298.15 - 1 / 283.15)))
