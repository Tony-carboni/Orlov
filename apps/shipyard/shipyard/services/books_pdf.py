"""The balance sheet as a PDF (reportlab), drawn from books.compute(): the layout of the directors'
sheets of 18 to 20 October 2026 (docs/finance/)."""

import io

M = 1e6


def _m(v, sign=False):
    if v is None:
        return "–"
    return f"{v / M:+,.1f} M" if sign else f"{v / M:,.1f} M"


def _donut(d: dict):
    """The donut of what the assets are in (look "C", owner's pick 2026-10-24), from finance_charts; 54 x 54 mm with
    its legend to the right (42 mm wide: the longest name, 23 mm, and a five-digit figure fit without touching)."""
    from reportlab.graphics.shapes import Drawing, Line, Rect, String, Wedge
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    from . import finance_charts as fc

    dn = fc.donut(d["asset_groups"])
    muted, ink = colors.HexColor("#5b6b82"), colors.HexColor("#1f2a44")
    legend_names = {"cash": "Liquid ISK", "pool": "Reward ISK in projects", "held": "Goods held", "listed": "Stock listed", "physical": "Physical stock", "lp": "Loyalty points"}
    left = Drawing(87 * mm, 60 * mm)
    cx, cy, r = 21 * mm, 30 * mm, 19 * mm
    for sg in dn["segments"]:
        left.add(Wedge(cx, cy, r, sg["end"], sg["start"], radius1=r * 0.62, fillColor=colors.HexColor(sg["colour"]), strokeColor=colors.white, strokeWidth=0.6))
    left.add(String(cx, cy + 1 * mm, f"{d['assets'] / M:,.0f}", textAnchor="middle", fontName="Helvetica-Bold", fontSize=10, fillColor=ink))
    left.add(String(cx, cy - 3 * mm, "M ISK", textAnchor="middle", fontName="Helvetica", fontSize=6, fillColor=muted))
    y = 56 * mm
    for sg in dn["segments"]:
        left.add(Rect(44 * mm, y - 1.4 * mm, 2.6 * mm, 2.6 * mm, fillColor=colors.HexColor(sg["colour"]), strokeColor=None))
        left.add(String(48 * mm, y - 1 * mm, legend_names.get(sg["key"], sg["label"])[:24], fontName="Helvetica", fontSize=6.5, fillColor=ink))
        left.add(String(86 * mm, y - 1 * mm, f"{sg['total'] / M:,.1f}", textAnchor="end", fontName="Helvetica", fontSize=6.5, fillColor=ink))
        y -= 5.2 * mm
    left.add(Line(44 * mm, y + 1.5 * mm, 86 * mm, y + 1.5 * mm, strokeColor=colors.HexColor("#c9d2e0"), strokeWidth=0.4))
    left.add(String(48 * mm, y - 1 * mm, "Owner's budget", fontName="Helvetica", fontSize=6.5, fillColor=muted))
    left.add(String(86 * mm, y - 1 * mm, f"{d['loan'] / M:,.1f}", textAnchor="end", fontName="Helvetica", fontSize=6.5, fillColor=muted))
    y -= 5.2 * mm
    left.add(String(48 * mm, y - 1 * mm, "Result", fontName="Helvetica-Bold", fontSize=6.5, fillColor=ink))
    left.add(String(86 * mm, y - 1 * mm, f"{d['result'] / M:+,.1f}", textAnchor="end", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor("#2e7d32")))
    return left


def render(d: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], alignment=0, fontSize=18, leading=22, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#5b6b82"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=4)
    p = ParagraphStyle("p", parent=ss["Normal"], fontSize=8.8, leading=11.5)
    cell = ParagraphStyle("cell", parent=p, fontSize=8.5, leading=10.5)
    num = ParagraphStyle("num", parent=cell, alignment=TA_RIGHT)
    note = ParagraphStyle("note", parent=p, fontSize=7.3, leading=9.2, textColor=colors.HexColor("#5b6b82"))
    line, shade, green = colors.HexColor("#2a8fc4"), colors.HexColor("#d9eefc"), colors.HexColor("#e7f4e8")
    tint, head_bg = colors.HexColor("#eef6fc"), colors.HexColor("#e1f1fb")
    h2.textColor = colors.HexColor("#1f6f9c")
    e = lambda s: escape(str(s))  # noqa: E731

    def table(header, rows, widths, total_rows=(), green_rows=(), numeric=(1,)):
        data = [[Paragraph(f"<b>{e(h)}</b>", num if i in numeric else cell) for i, h in enumerate(header)]]
        for r in rows:
            data.append([Paragraph(str(c), num if i in numeric else cell) for i, c in enumerate(r)])
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("LINEBELOW", (0, 0), (-1, 0), 0.8, line), ("BACKGROUND", (0, 0), (-1, 0), head_bg), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 4)]
        for i in total_rows:
            st += [("BACKGROUND", (0, i), (-1, i), shade), ("LINEABOVE", (0, i), (-1, i), 0.8, line)]
        for i in green_rows:
            st += [("BACKGROUND", (0, i), (-1, i), green)]
        t.setStyle(TableStyle(st))
        return t

    tile_l = ParagraphStyle("tl", parent=note, fontSize=7, leading=8.5)
    tile_v = ParagraphStyle("tv", parent=cell, fontSize=11, leading=13)

    def tiles(items, per_row=4, width=174 * mm):
        """Stat tiles as on the page: (label, value, sub, colour) each; a shaded cell per tile."""
        cells = [[Paragraph(e(l), tile_l), Paragraph(f"<font color='{c or '#1f2a44'}'><b>{e(v)}</b></font>", tile_v)] for l, v, sub, c in items]  # label and figure only (owner, 2026-10-24)
        data = [[cells[i] if i < len(cells) else "" for i in range(r, r + per_row)] for r in range(0, len(cells), per_row)]
        t = Table(data, colWidths=[width / per_row] * per_row)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), tint), ("BOX", (0, 0), (-1, -1), 0.4, colors.white), ("INNERGRID", (0, 0), (-1, -1), 1.2, colors.white),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
        return t

    def pct_(v):
        return f"{v * 100:.0f} %" if v is not None else "–"

    def sign_colour(v):
        return "#2e7d32" if (v or 0) >= 0 else "#c62828"

    cut, base = d["cut"], d["base"]
    story = [
        Paragraph("Orlov Arms International · balance sheet", h1),
        Paragraph(f"{cut.day} {cut:%B %Y}, {cut:%H:%M} EVE · movements since {e(d['since_label'])}"
                  + (f" ({base.day} {base:%B}, {base:%H:%M} EVE)" if d.get("period") is not None and d["period"].source else "")
                  + " · M ISK · from EVE through auth, for the directors of The Orlov Family", sub),
        Spacer(1, 6),
    ]
    # the headline figures, as the page's cards
    kpis = [[Paragraph("<b>Result</b>", cell), Paragraph(f"<b>{_m(d['result'], True)}</b>", num), Paragraph(f"above the {d['loan'] / M:,.0f} M budget", note)]]
    if d.get("period") is not None and d["period"].source:
        kpis.append([Paragraph(f"<b>Since {e(d['since_label'])}</b>", cell), Paragraph(f"<b>{_m(d['period_result'], True)}</b>", num), Paragraph(f"opening {_m(d['opening_result'], True)}", note)])
    kpis.append([Paragraph("<b>Total assets</b>", cell), Paragraph(f"<b>{_m(d['assets'])}</b>", num), Paragraph("", note)])
    kpis.append([Paragraph("<b>Master wallet</b>", cell), Paragraph(f"<b>{_m(d['wallet'])}</b>", num), Paragraph(f"{_m(d['pool'])} in {d['n_projects']} active projects", note)])
    om = d.get("outside_master") or {}
    if om.get("owed", 0.0) >= 1:
        kpis.append([Paragraph("<b><font color='#c62828'>Funded outside the master wallet</font></b>", cell), Paragraph(f"<b><font color='#c62828'>{_m(om['owed'])}</font></b>", num),
                     Paragraph(f"still owed to the funding wallet: {len(om['open'])} open projects, {_m(om['funded'])} funded, {_m(om['corrected'])} corrected", note)])
    kt = Table(kpis, colWidths=[40 * mm, 30 * mm, 104 * mm])
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), shade), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4cc3ff")),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 5)]))
    at_ = d.get("asset_tiles") or {}
    # the donut on the left, the period's four figures on the right (owner, 2026-10-24, in place of the waterfall)
    pt = d.get("period_tiles") or {}
    period = tiles([("Turnover, all sales", _m(pt.get("turnover", 0.0)), "", None), ("LP bought", f"{pt.get('lp_units', 0):,.0f} LP", "", None),
                    ("Net income", _m(pt.get("net", 0.0), True), "", sign_colour(pt.get("net"))), ("Project rewards paid out", _m(pt.get("rewards", 0.0)), "", None)],
                   per_row=2, width=84 * mm)
    pics = Table([[_donut(d), period]], colWidths=[90 * mm, 84 * mm])
    pics.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    story += [kt, Spacer(1, 6), pics, Paragraph("1. Position", h2), Spacer(1, 2),
              tiles([("Liquid ISK", _m(at_.get("cash", 0.0)), "", None), ("Reward ISK in active projects", _m(at_.get("pool", 0.0)), "", None),
                     ("Stock", _m(at_.get("stock", 0.0)), "", None), ("Goods held from project buybacks", _m(at_.get("held", 0.0)), "", None)]), Spacer(1, 4)]
    # Key numbers only, no detail lines (owner, 2026-10-30): every section is tiles; section 1 is the four tiles above.

    story.append(Paragraph(f"2. Movements since {e(d['since_label'])}" + (f" ({base.day} {base:%B}, {base:%H:%M} EVE)" if d.get("period") is not None and d["period"].source else ""), h2))
    story.append(Spacer(1, 2))
    groups = [g for g in d["move_groups"] if abs(g["total"]) >= 1 or g["key"] == "gap"]
    items = [(g["label"], _m(g["total"], True), "", sign_colour(g["total"])) for g in groups if g["key"] != "gap"]
    items.append(("Result of the period", _m(d["period_result"], True), "", sign_colour(d["period_result"])))
    story.append(tiles(items, per_row=4))

    pb = d.get("project_bb") or {}
    if pb.get("active"):
        at = pb.get("all_time") or {}
        since = f" since {at['first'].day} {at['first']:%b}" if at.get("first") else ""
        part = [Paragraph("3. Project buybacks", h2), Spacer(1, 2),
                tiles([("Paid to members, this period", _m(pb["paid_total"]), "", None),
                       ("Margin on goods sold, this period", pct_(pb.get("margin")), "", sign_colour(pb.get("margin"))),
                       ("Net profit, this period", _m(pb["realised"], True), "", sign_colour(pb["realised"])),
                       (f"Total project payout{since}", _m(at.get("paid", 0.0)), "", None),
                       (f"Total project margin{since}", pct_(at.get("margin")), "", sign_colour(at.get("margin")))], per_row=5), Spacer(1, 3)]
        for mo in pb["months"]:
            part += [Paragraph(f"<b>{e(mo['label'])}</b>", p),
                     tiles([("Paid to members", _m(mo["paid_total"]), "", None), ("Sold for", _m(mo["sold_value"]), "", None),
                            ("Net profit", _m(mo["realised"], True), "", sign_colour(mo["realised"])),
                            ("Margin", f"{mo['pct'] * 100:.0f} %" if mo["pct"] is not None else "–", "", sign_colour(mo["pct"])),
                            ("Still held, at cost", _m(mo["held_cost"]), "", None)], per_row=5), Spacer(1, 3)]
        story.append(KeepTogether(part))

    bb = d.get("buyback") or {}
    if bb.get("active"):
        part = [Paragraph("4. LP buybacks and conversions", h2), Spacer(1, 2),
                tiles([("Net profit", _m(bb["realised"], True), "", sign_colour(bb["realised"])),
                       ("Margin on what sold", pct_(bb.get("margin")), "", sign_colour(bb.get("margin"))),
                       ("Projected on what is listed", _m(bb["expected"], True), "", None),
                       ("LP not converted", f"{bb['lp_left']:,.0f} LP", "", None)]), Spacer(1, 3)]
        for mo in bb["months"]:
            part += [Paragraph(f"<b>{e(mo['label'])}</b>", p),
                     tiles([("LP bought", f"{mo['lp_bought']:,} LP" if mo["lp_bought"] else "none", "", None),
                            ("LP converted", f"{mo['lp_converted']:,} LP", "", None),
                            ("LP sold directly", f"{mo['lp_sold']:,} LP" if mo.get("lp_sold") else "none", "", None),
                            ("Net profit", _m(mo["realised"], True), "", sign_colour(mo["realised"]))]), Spacer(1, 3)]
        story.append(KeepTogether(part))

    if d["fuel_rows"]:
        story.append(KeepTogether([
            Paragraph(f"5. Structure fuel <font size='8' color='#5b6b82'>{e(d['fuel_name'])} {d['fuel_price']:,.0f} ISK at {e(d['market'])}</font>", h2),
            Spacer(1, 2),
            tiles([("Fuel blocks per month", f"{d['fuel_month_blocks']:,.0f} blocks", "", None),
                   ("Cost of these blocks per month", _m(d["fuel_month_isk"]), "", "#c62828"),
                   ("Burned since the baseline", f"{d['fuel_burned']:,} blocks", "", None),
                   ("Total structure income", _m(d.get("structure_income_total", 0.0), True), "", "#2e7d32")]),
        ]))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"OARMI balance sheet {cut:%Y-%m-%d}", author="The Orlov Family")
    doc.build(story)
    return buf.getvalue()
