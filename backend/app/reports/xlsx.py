"""Excel report (openpyxl): one sheet per section, numbers stored as numbers."""
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.reports.common import (DISCLAIMER, OPTION_LABELS, calculate_all, design_config_rows, element_table,
                                scaling_table, stage_table, system_rows, water_table)

BOLD = Font(bold=True)
HEAD_FILL = PatternFill("solid", fgColor="E5E7EB")
RED = Font(color="B91C1C")


def _write(ws, rows, head=None, start_row=None):
    r = start_row or ws.max_row + (2 if ws.max_row > 1 else 0)
    if head:
        for c, v in enumerate(head, 1):
            cell = ws.cell(r, c, v)
            cell.font, cell.fill = BOLD, HEAD_FILL
        r += 1
    for row in rows:
        for c, v in enumerate(row, 1):
            ws.cell(r, c, v)
        r += 1
    return r


def _messages(ws, messages):
    r = ws.max_row + 2
    for m in messages:
        ws.cell(r, 1, m["text"]).font = RED if m["level"] != "info" else Font()
        r += 1


def _autosize(ws):
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, 10), 60)


def build(project: dict) -> bytes:
    res = calculate_all(project)
    wb = Workbook()

    ws = wb.active
    ws.title = "Project"
    info = project["project"]
    _write(ws, [["Project", info.get("name")], ["Date", info.get("date")], ["Designed by", info.get("designedBy")],
                ["Company", info.get("company")], ["Water type", project["water"].get("waterType")]], start_row=1)

    ws = wb.create_sheet("Water Analysis")
    head, rows, totals = water_table(res)
    _write(ws, rows, head, start_row=1)
    _write(ws, totals + [["Temperature (°C)", project["water"]["temperatureC"]], ["pH", project["water"]["pH"]]])
    _messages(ws, res["water"]["messages"])

    ws = wb.create_sheet("Scaling")
    sc = res["scaling"]
    _write(ws, [["Option", OPTION_LABELS.get(sc["option"], sc["option"])], ["Recovery (%)", sc["recoveryPct"]],
                ["Temperature (°C)", sc["temperatureC"]], ["Concentration factor", round(sc["cf"], 4)]], start_row=1)
    if sc.get("acidDose"):
        _write(ws, [["Acid", sc["acidDose"]["chemical"]], ["Acid dose (mg/L)", round(sc["acidDose"]["mgL"], 2)]])
    head, rows = scaling_table(res)
    _write(ws, rows, head)
    _messages(ws, sc["messages"])

    ws = wb.create_sheet("Design")
    _write(ws, design_config_rows(project), ["Configuration", ""], start_row=1)
    _write(ws, system_rows(project, res), ["System results", ""])
    _messages(ws, res["design"]["messages"])

    if res["design"]["engineOk"]:
        ws = wb.create_sheet("Stages")
        head, rows = stage_table(project, res)
        _write(ws, rows, head, start_row=1)
        ws = wb.create_sheet("Elements")
        head, rows = element_table(project, res)
        _write(ws, rows, head, start_row=1)

    ws = wb.create_sheet("Notes")
    _write(ws, [[line] for line in DISCLAIMER], start_row=1)

    for sheet in wb.worksheets:
        _autosize(sheet)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
