import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

GOLDEN = json.loads((Path(__file__).parent / "golden_cases.json").read_text(encoding="utf-8"))

ION_KEYS = ["Na", "Ca", "Mg", "K", "Ba", "Sr", "NH4", "B", "Cl", "CO3", "HCO3", "F", "NO3", "SO4", "SiO2"]


def round_half_up(x, dp):
    from app.calc.units import round_half_up as r
    return r(x, dp)


def displayed(actual, dp=2):
    """The value as Vontron would display it."""
    return round_half_up(actual, dp)


def assert_close(actual, expected, *, abs_tol=0.01, rel_tol=None, dp=2, label=""):
    """Compare the displayed (rounded) value with the golden value."""
    assert actual is not None, f"{label}: got None, expected {expected}"
    shown = displayed(actual, dp)
    tol = abs_tol if rel_tol is None else max(abs(expected) * rel_tol, 0.01)
    assert abs(shown - expected) <= tol + 1e-9, (
        f"{label}: displayed {shown} (raw {actual}) vs golden {expected} (tol {tol})"
    )


def make_water(ions=None, **kw):
    water = {
        "inputUnit": "mg/L",
        "specifyIndividualSolutes": True,
        "tdsInput": None,
        "temperatureC": 25,
        "pH": 7.5,
        "waterType": "RO Permeate SDI < 1",
        "ions": {k: 0.0 for k in ION_KEYS},
    }
    if ions:
        water["ions"].update(ions)
    water.update(kw)
    return water


@pytest.fixture
def golden():
    return GOLDEN


@pytest.fixture
def tc_water_a(golden):
    g = golden["water"]["tcWaterA"]
    return make_water(dict(g["ions"]), pH=g["pH"], temperatureC=g["temperatureC"])


@pytest.fixture
def tc_water_a_balanced(tc_water_a):
    from app.calc.water import auto_balance
    return auto_balance(tc_water_a)
