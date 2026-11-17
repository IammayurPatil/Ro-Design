"""PDF report (ReportLab, A4, company/project header, page numbers)."""
import io

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from app.reports.common import (DISCLAIMER, OPTION_LABELS, calculate_all, design_config_rows, element_table,
                                scaling_table, stage_table, system_rows, water_table)

STYLES = getSampleStyleSheet()
H1, H2, BODY = STYLES["Heading1"], STYLES["Heading2"], STYLES["BodyText"]
SMALL = STYLES["BodyText"].clone("small", fontSize=8, leading=10)
RED = STYLES["BodyText"].clone("red", textColor=colors.HexColor("#b91c1c"))
FEED_C, CONC_C = colors.HexColor("#2563eb"), colors.HexColor("#ea580c")


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) < 1e6 else f"{v:.3e}"
    return str(v)


def _table(head, rows, col_widths=None, font=8):
    data = ([head] if head else []) + [[_fmt(c) for c in r] for r in rows]
    t = Table(data, colWidths=col_widths, repeatRows=1 if head else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), font), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
             ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if head:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def _saturation_chart(res):
    cols = res["scaling"]["columns"]
    names = ["CaSO4", "BaSO4", "SrSO4", "CaF2", "SiO2"]
    feed = [cols["feed"][n] or 0 for n in names]
    conc = [cols["concentrate"][n] or 0 for n in names]
    d = Drawing(170 * mm, 70 * mm)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 15 * mm, 10 * mm, 140 * mm, 50 * mm
    ch.data = [feed, conc]
    ch.categoryAxis.categoryNames = names
    top = max(feed + conc + [100]) * 1.1
    ch.valueAxis.valueMin, ch.valueAxis.valueMax = 0, top
    ch.bars[0].fillColor, ch.bars[1].fillColor = FEED_C, CONC_C
    d.add(ch)
    y100 = ch.y + ch.height * 100 / top
    d.add(Line(ch.x, y100, ch.x + ch.width, y100, strokeColor=colors.red, strokeDashArray=[3, 2]))
    d.add(String(ch.x + ch.width + 2, y100 - 3, "100%", fontSize=7, fillColor=colors.red))
    lg = Legend()
    lg.x, lg.y = 20 * mm, 67 * mm
    lg.alignment, lg.columnMaximum, lg.fontSize = "right", 1, 7
    lg.colorNamePairs = [(FEED_C, "Feed"), (CONC_C, "Concentrate")]
    d.add(lg)
    d.add(String(0, 67 * mm, "Saturation %", fontSize=8))
    return d


def _profile_chart(res):
    pts_flux, pts_p = [], []
    i = 0
    for ps in res["design"]["passes"]:
        for st in ps["stages"]:
            for e in st.get("elements", []):
                i += 1
                pts_flux.append((i, e["fluxGfd"]))
                pts_p.append((i, e["feedPressure"]))
    if len(pts_flux) < 2:
        return None
    d = Drawing(170 * mm, 65 * mm)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 15 * mm, 10 * mm, 140 * mm, 45 * mm
    lp.data = [pts_flux, pts_p]
    lp.lines[0].strokeColor, lp.lines[1].strokeColor = FEED_C, CONC_C
    d.add(lp)
    lg = Legend()
    lg.x, lg.y = 20 * mm, 62 * mm
    lg.alignment, lg.columnMaximum, lg.fontSize = "right", 1, 7
    lg.colorNamePairs = [(FEED_C, "Flux (gfd)"), (CONC_C, "Feed pressure (bar)")]
    d.add(lg)
    d.add(String(0, 62 * mm, "Per-element profile", fontSize=8))
    return d


def build(project: dict) -> bytes:
    res = calculate_all(project)
    info = project["project"]
    buf = io.BytesIO()

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, A4[1] - 12 * mm, info.get("company") or "Untitled")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 15 * mm, A4[1] - 12 * mm, f"{info.get('name') or 'Project'} — {info.get('date', '')}")
        canvas.line(15 * mm, A4[1] - 14 * mm, A4[0] - 15 * mm, A4[1] - 14 * mm)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title=f"RO Design Report - {info.get('name') or 'Project'}")
    s = []
    s.append(Paragraph("RO System Design Report", H1))
    s.append(Paragraph("1. Project information", H2))
    s.append(_table(None, [["Project", info.get("name")], ["Date", info.get("date")],
                           ["Designed by", info.get("designedBy")], ["Company", info.get("company")],
                           ["Water type", project["water"].get("waterType")]], [45 * mm, 120 * mm], 9))

    s.append(Paragraph("2. Water analysis", H2))
    head, rows, totals = water_table(res)
    s.append(_table(head, rows, [30 * mm, 35 * mm, 35 * mm, 35 * mm]))
    s.append(Spacer(1, 3 * mm))
    s.append(_table(None, totals, [45 * mm, 35 * mm], 9))
    s.append(Paragraph(f"Temperature {project['water']['temperatureC']} °C, pH {project['water']['pH']}", BODY))
    for m in res["water"]["messages"]:
        s.append(Paragraph(m["text"], RED if m["level"] != "info" else BODY))

    s.append(PageBreak())
    sc = res["scaling"]
    s.append(Paragraph("3. Scaling", H2))
    s.append(Paragraph(f"Option: {OPTION_LABELS.get(sc['option'], sc['option'])}. Recovery {sc['recoveryPct']:g}%, "
                       f"temperature {sc['temperatureC']:g} °C, concentration factor {sc['cf']:.4f}.", BODY))
    if sc.get("acidDose"):
        a = sc["acidDose"]
        s.append(Paragraph(f"Acid dose: {a['mgL']:.2f} mg/L {a['chemical']} ({a['meqPerL']:.3f} meq/L).", BODY))
    head, rows = scaling_table(res)
    s.append(_table(head, rows, [50 * mm, 35 * mm, 35 * mm, 35 * mm]))
    for m in sc["messages"]:
        s.append(Paragraph(m["text"], RED if m["level"] != "info" else BODY))
    s.append(Spacer(1, 4 * mm))
    s.append(KeepTogether([Paragraph("Charts", H2), _saturation_chart(res)]))

    s.append(PageBreak())
    s.append(Paragraph("4. Design", H2))
    s.append(_table(None, design_config_rows(project), [45 * mm, 120 * mm], 9))
    s.append(Spacer(1, 3 * mm))
    s.append(Paragraph("System results", STYLES["Heading3"]))
    s.append(_table(None, system_rows(project, res), [60 * mm, 40 * mm], 9))
    for m in res["design"]["messages"]:
        s.append(Paragraph(m["text"], RED if m["level"] != "info" else BODY))
    if res["design"]["engineOk"]:
        s.append(Paragraph("Per stage", STYLES["Heading3"]))
        head, rows = stage_table(project, res)
        s.append(_table(head, rows, font=6.5))
        s.append(Paragraph("Per element", STYLES["Heading3"]))
        head, rows = element_table(project, res)
        s.append(_table(head, rows, font=6.5))
        chart = _profile_chart(res)
        if chart:
            s.append(KeepTogether([Spacer(1, 4 * mm), chart]))

    s.append(Paragraph("5. Notes and disclaimer", H2))
    for line in DISCLAIMER:
        s.append(Paragraph(line, SMALL))
    doc.build(s, onFirstPage=header_footer, onLaterPages=header_footer)
    return buf.getvalue()
