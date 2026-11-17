"""API smoke tests: every endpoint answers, reports are valid files."""
import io
import zipfile

from fastapi.testclient import TestClient

from conftest import GOLDEN

from app.main import app

client = TestClient(app)


def project(**water):
    g = GOLDEN["water"]["tcWaterA"]
    return {
        "project": {"name": "Plant A", "date": "2026-11-08"},
        "water": {"ions": g["ions"], "pH": g["pH"], "temperatureC": 25, **water},
        "scaling": {"recoveryPct": 75},
        "design": {"permeateFlow": 1.1355, "recoveryPct": 15},
    }


def test_water_analyze_and_balance():
    r = client.post("/api/water/analyze", json=project()["water"])
    assert r.status_code == 200 and round(r.json()["tds"], 2) == 945.42
    r = client.post("/api/water/auto-balance", json=project()["water"])
    assert r.json()["water"]["ions"]["Na"] == 184.5


def test_scaling_and_design():
    p = project()
    r = client.post("/api/scaling/calculate", json={"water": p["water"], "scaling": p["scaling"]})
    assert r.status_code == 200 and "concentrate" in r.json()["columns"]
    r = client.post("/api/design/calculate", json=p)
    assert r.status_code == 200 and round(r.json()["system"]["fluxGfd"], 1) == 18.0
    r = client.post("/api/calculate-all", json=p)
    assert set(r.json()) >= {"water", "scaling", "design", "messages"}


def test_reference_endpoints():
    assert client.get("/api/elements").json()[0]["model"] == "LP22-8040"
    assert len(client.get("/api/water-types").json()) == 9
    assert client.get("/api/config/ions").json()["ions"]["Na"]["eqWt"] == 23.0


def test_pdf_report():
    r = client.post("/api/report/pdf", json=project())
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert 'filename="Plant_A_20261108.pdf"' in r.headers["content-disposition"]


def test_xlsx_report():
    r = client.post("/api/report/xlsx", json=project())
    assert r.status_code == 200
    assert zipfile.is_zipfile(io.BytesIO(r.content))
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    assert {"Project", "Water Analysis", "Scaling", "Design", "Notes"} <= set(wb.sheetnames)
    ws = wb["Water Analysis"]
    assert isinstance(ws["B2"].value, (int, float))  # numbers stored as numbers
