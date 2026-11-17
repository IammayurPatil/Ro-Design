"""HTTP API (prompt section 9). Stateless: every request carries the data it needs."""
from datetime import date

from fastapi import APIRouter
from fastapi.responses import Response

from app.calc import design as design_calc
from app.calc import scaling as scaling_calc
from app.calc import water as water_calc
from app.config import load, strip_notes
from app.models.project import Project, Water, WaterScalingRequest
from app.reports import pdf as pdf_report
from app.reports import xlsx as xlsx_report
from app.reports.common import calculate_all

router = APIRouter(prefix="/api")


@router.post("/water/analyze")
def water_analyze(water: Water):
    return water_calc.analyze(water.model_dump())


@router.post("/water/auto-balance")
def water_auto_balance(water: Water):
    balanced = water_calc.auto_balance(water.model_dump())
    return {"water": balanced, "analysis": water_calc.analyze(balanced)}


@router.post("/scaling/calculate")
def scaling_calculate(req: WaterScalingRequest):
    return scaling_calc.calculate(req.water.model_dump(), req.scaling.model_dump())


@router.post("/design/calculate")
def design_calculate(project: Project):
    return design_calc.calculate(project.model_dump())


@router.post("/calculate-all")
def calculate_all_route(project: Project):
    return calculate_all(project.model_dump())


def _filename(project: Project, ext: str) -> str:
    name = "".join(c for c in (project.project.name or "Project") if c.isalnum() or c in "-_ ").strip() or "Project"
    d = (project.project.date or date.today().isoformat()).replace("-", "")
    return f"{name.replace(' ', '_')}_{d}.{ext}"


@router.post("/report/pdf")
def report_pdf(project: Project):
    data = pdf_report.build(project.model_dump())
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(project, "pdf")}"'})


@router.post("/report/xlsx")
def report_xlsx(project: Project):
    data = xlsx_report.build(project.model_dump())
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(project, "xlsx")}"'})


@router.get("/elements")
def elements():
    return strip_notes(load("elements"))


@router.get("/water-types")
def water_types():
    wt = strip_notes(load("water_types"))
    return [{"name": t["name"], "limits": design_calc.water_type_limits(t["name"])} for t in wt["types"]]


@router.get("/config/ions")
def ion_constants():
    """Ion constants so the UI can convert typed ppm CaCO3 / meq values to mg/L for entry."""
    cfg = load("ions")
    return {"ions": cfg["ions"], "order": cfg["order"], "rounding": cfg["rounding"],
            "validation": cfg["validation"]}


@router.get("/config/units")
def unit_constants():
    """Unit conversion factors so the UI can display flows and pressures in the chosen unit set."""
    return strip_notes(load("units"))


@router.get("/health")
def health():
    return {"status": "ok"}
