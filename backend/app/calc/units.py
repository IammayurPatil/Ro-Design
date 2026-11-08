"""Unit conversions and rounding helpers. Internal units: mg/L, C, m3/h, bar."""
from decimal import ROUND_HALF_UP, Decimal

from app.config import load

UNITS = load("units")


def round_half_up(x: float, dp: int) -> float:
    """Round like a calculator (2.345 -> 2.35), not banker's rounding."""
    if x is None:
        return None
    q = Decimal(1).scaleb(-dp)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def gpm_to_m3h(gpm: float) -> float:
    return gpm * UNITS["gpmToM3h"]


def m3h_to_gpm(m3h: float) -> float:
    return m3h / UNITS["gpmToM3h"]


def m3h_to_gpd(m3h: float) -> float:
    return m3h_to_gpm(m3h) * UNITS["gpmToGpd"]


def m3h_to_m3d(m3h: float) -> float:
    return m3h * UNITS["m3hToM3d"]


def bar_to_psi(bar: float) -> float:
    return bar * UNITS["barToPsi"]


def psi_to_bar(psi: float) -> float:
    return psi / UNITS["barToPsi"]


def ft2_to_m2(ft2: float) -> float:
    return ft2 * UNITS["ft2ToM2"]


def gfd_to_lmh(gfd: float) -> float:
    return gfd * UNITS["gfdToLmh"]


def flow_from_m3h(m3h: float, unit: str) -> float:
    """Convert an internal m3/h flow to a display unit (gpd, gpm, m3/h, m3/d)."""
    if m3h is None:
        return None
    return {
        "gpd": m3h_to_gpd,
        "gpm": m3h_to_gpm,
        "m3/h": lambda v: v,
        "m3/d": m3h_to_m3d,
    }[unit](m3h)


def pressure_from_bar(bar: float, unit: str) -> float:
    if bar is None:
        return None
    return bar_to_psi(bar) if unit == "psi" else bar


def unit_set(name: str) -> dict:
    return UNITS["unitSets"].get(name, UNITS["unitSets"]["gpm_psi"])
