"""Shared report data: runs every calculation and builds display tables (numbers stay numbers)."""
from app.calc import design as design_calc
from app.calc import scaling as scaling_calc
from app.calc import water as water_calc
from app.calc.units import flow_from_m3h, pressure_from_bar, unit_set

OPTION_LABELS = {
    "none": "No chemicals added",
    "ph_adjust": "User adjusted pH",
    "softening": "Ion exchange softening",
    "antiscalant": "Dosing Antiscalants",
}

DISCLAIMER = [
    "Water Analysis and the core Scaling formulas reproduce Vontron RO Design Software 6.1 (golden tests).",
    "PROVISIONAL logic (not yet confirmed against Vontron): the design engine (pressures, permeate quality, "
    "energy), pH adjustment, softening, antiscalant limits, the CaCO3 (LSI) warning threshold, the general "
    "Ksp form, S&DSI above I = 0.13, the SrSO4 step at TDS 4000 and all design limits per water type.",
    "Element datasheet values that are still missing are reported as errors instead of being guessed.",
]

SCALING_ROWS = [("pH", "pH"), ("TDS", "TDS (mg/L)"), ("HCO3", "HCO3 (mg/L)"), ("CO3", "CO3 (mg/L)"),
                ("CO2", "CO2 (mg/L)"), ("LSI", "LSI"), ("SDSI", "S&DSI"),
                ("CaSO4", "CaSO4 Saturation %"), ("BaSO4", "BaSO4 Saturation %"),
                ("SrSO4", "SrSO4 Saturation %"), ("CaF2", "CaF2 Saturation %"), ("SiO2", "SiO2 Saturation %")]


def calculate_all(project: dict) -> dict:
    water = water_calc.analyze(project["water"])
    scaling = scaling_calc.calculate(project["water"], project["scaling"])
    design = design_calc.calculate(project)
    messages = ([{**m, "page": "Water Analysis"} for m in water["messages"]]
                + [{**m, "page": "Scaling"} for m in scaling["messages"]]
                + [{**m, "page": "Design System"} for m in design["messages"]])
    return {"water": water, "scaling": scaling, "design": design, "messages": messages}


def _r(v, dp=2):
    return None if v is None else round(v, dp)


def water_table(res: dict):
    w = res["water"]
    rows = [[ion, _r(w["rows"][ion]["mgL"]), _r(w["rows"][ion]["ppmCaCO3"]), _r(w["rows"][ion]["meq"])]
            for ion in w["order"]]
    totals = [["TDS (mg/L)", _r(w["tds"])], ["Cations (meq/L)", _r(w["cations"], 1)],
              ["Anions (meq/L)", _r(w["anions"], 1)], ["Balance (meq/L)", _r(w["balance"], 1)]]
    return ["Ion", "mg/L", "ppm CaCO3", "meq/L"], rows, totals


def scaling_table(res: dict):
    cols = res["scaling"]["columns"]
    rows = [[label] + [_r(cols[c][key]) if cols[c][key] is not None else "N/A"
                       for c in ("feed", "adjusted", "concentrate")]
            for key, label in SCALING_ROWS]
    return ["", "Feed", "Adjusted Feed", "Concentrate"], rows


def design_units(project: dict):
    us = unit_set(project["design"].get("unitSet", "gpm_psi"))
    return us["flow"], us["pressure"]


def design_config_rows(project: dict):
    d = project["design"]
    fu, pu = design_units(project)
    rows = [["Unit set", d["unitSet"]], ["Recovery (%)", d["recoveryPct"]],
            [f"Permeate flow ({fu})", _r(flow_from_m3h(d["permeateFlow"], fu))],
            ["Feed temperature (°C)", d["feedTempC"]], ["Fouling factor", d["foulingFactor"]],
            ["Number of passes", len(d["passes"])]]
    for pi, ps in enumerate(d["passes"]):
        for si, st in enumerate(ps["stages"]):
            rows.append([f"Pass {pi + 1} stage {si + 1}",
                         f"{st['vessels']} vessel(s) x {st['elementsPerVessel']} element(s), {st['elementModel']}, "
                         f"back pressure {_r(pressure_from_bar(st['backPressure'], pu))} {pu}"])
    rows.append(["Pump efficiency", f"{d['pumpEfficiencyPct']}%" if d["pumpEfficiencyEnabled"] else "Not applied"])
    rows.append(["Recirculation", f"{_r(flow_from_m3h(d['recycle']['flow'], fu))} {fu}"
                 if d["recycle"]["enabled"] else "Off"])
    return rows


def system_rows(project: dict, res: dict):
    s = res["design"]["system"]
    fu, pu = design_units(project)
    return [
        [f"Feed flow ({fu})", _r(flow_from_m3h(s["feedFlow"], fu))],
        [f"Permeate flow ({fu})", _r(flow_from_m3h(s["permeateFlow"], fu))],
        [f"Concentrate flow ({fu})", _r(flow_from_m3h(s["concentrateFlow"], fu))],
        ["Recovery (%)", _r(s["recoveryPct"])],
        ["Total elements", s["totalElements"]],
        ["Average flux (gfd)", _r(s["fluxGfd"], 1)],
        ["Average flux (LMH)", _r(s["fluxLmh"], 1)],
        [f"Feed pressure ({pu})", _r(pressure_from_bar(s["feedPressure"], pu))],
        ["Pump power (kW)", _r(s["pumpKw"])],
        ["Specific energy (kWh/m³)", _r(s["specificEnergy"], 3)],
        ["Feed TDS (mg/L)", _r(s["feedTDS"])],
        ["Permeate TDS (mg/L)", _r(s["permeateTDS"])],
        ["Concentrate TDS (mg/L)", _r(s["concentrateTDS"])],
    ]


def stage_table(project: dict, res: dict):
    fu, pu = design_units(project)
    head = ["Pass", "Stage", "Vessels", "Elements/vessel", "Element", f"Feed ({fu})", f"Permeate ({fu})",
            f"Concentrate ({fu})", f"Feed P ({pu})", f"Conc P ({pu})", "Flux (gfd)", "Permeate TDS"]
    rows = []
    for ps in res["design"]["passes"]:
        for st in ps["stages"]:
            rows.append([ps["pass"], st["stage"], st["vessels"], st["elementsPerVessel"], st["elementModel"],
                         _r(flow_from_m3h(st.get("feedFlow"), fu)), _r(flow_from_m3h(st.get("permeateFlow"), fu)),
                         _r(flow_from_m3h(st.get("concentrateFlow"), fu)),
                         _r(pressure_from_bar(st.get("feedPressure"), pu)),
                         _r(pressure_from_bar(st.get("concentratePressure"), pu)),
                         _r(st.get("fluxGfd"), 1), _r(st.get("permeateTDS"))])
    return head, rows


def element_table(project: dict, res: dict):
    fu, pu = design_units(project)
    head = ["Pass", "Stage", "Element", f"Feed ({fu})", f"Permeate ({fu})", f"Feed P ({pu})", f"ΔP ({pu})",
            "NDP (bar)", "Recovery (%)", "Flux (gfd)", "Permeate TDS", "Conc TDS"]
    rows = []
    for ps in res["design"]["passes"]:
        for st in ps["stages"]:
            for e in st.get("elements", []):
                rows.append([ps["pass"], st["stage"], e["position"], _r(flow_from_m3h(e["feedFlow"], fu)),
                             _r(flow_from_m3h(e["permeateFlow"], fu), 3),
                             _r(pressure_from_bar(e["feedPressure"], pu)),
                             _r(pressure_from_bar(e["pressureDrop"], pu), 3), _r(e["ndp"]),
                             _r(e["recoveryPct"]), _r(e["fluxGfd"]), _r(e["permeateTDS"]), _r(e["concentrateTDS"])])
    return head, rows
