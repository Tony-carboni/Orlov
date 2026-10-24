"""The balance sheet as a PDF (reportlab), drawn from books.compute(): the layout of the directors'
sheets of 18 to 20 October 2026 (docs/finance/)."""

import io

M = 1e6


def _m(v, sign=False):
    if v is None:
        return "–"
    return f"{v / M:+,.1f} M" if sign else f"{v / M:,.1f} M"


def _pictures(d: dict):
    """The donut and the waterfall side by side (look "C", owner's pick 2026-10-24), from finance_charts."""
    from reportlab.graphics.shapes import Drawing, Line, Rect, String, Wedge
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle

    from . import finance_charts as fc

    opening = d["opening_result"] if d.get("period") is not None and d["period"].source else 0.0
    dn, wf = fc.donut(d["asset_groups"]), fc.waterfall(d["move_groups"], opening, width=300, height=150)
    muted, ink = colors.HexColor("#5b6b82"), colors.HexColor("#1f2a44")
    legend_names = {"cash": "Liquid ISK", "pool": "Reward ISK in projects", "held": "Goods held", "listed": "Stock listed", "physical": "Physical stock", "lp": "Loyalty points"}
    bar_names = {"project_sales": "Sales", "project_rewards": "Rewards", "lp": "LP", "stock": "Stock", "market": "Market", "structure": "Structure", "transfers": "Transfers", "gap": "Gap", "opening": "Opening", "result": "Result"}
    # the donut: 60 x 60 mm, legend to its right
    left = Drawing(84 * mm, 60 * mm)
    cx, cy, r = 24 * mm, 30 * mm, 22 * mm
    for sg in dn["segments"]:
        left.add(Wedge(cx, cy, r, sg["end"], sg["start"], radius1=r * 0.62, fillColor=colors.HexColor(sg["colour"]), strokeColor=colors.white, strokeWidth=0.6))
    left.add(String(cx, cy + 1 * mm, f"{d['assets'] / M:,.0f}", textAnchor="middle", fontName="Helvetica-Bold", fontSize=10, fillColor=ink))
    left.add(String(cx, cy - 3 * mm, "M ISK", textAnchor="middle", fontName="Helvetica", fontSize=6, fillColor=muted))
    y = 56 * mm
    for sg in dn["segments"]:
        left.add(Rect(50 * mm, y - 1.4 * mm, 2.6 * mm, 2.6 * mm, fillColor=colors.HexColor(sg["colour"]), strokeColor=None))
        left.add(String(54 * mm, y - 1 * mm, legend_names.get(sg["key"], sg["label"])[:24], fontName="Helvetica", fontSize=6.5, fillColor=ink))
        left.add(String(84 * mm, y - 1 * mm, f"{sg['total'] / M:,.1f}", textAnchor="end", fontName="Helvetica", fontSize=6.5, fillColor=ink))
        y -= 5.2 * mm
    left.add(Line(50 * mm, y + 1.5 * mm, 84 * mm, y + 1.5 * mm, strokeColor=colors.HexColor("#c9d2e0"), strokeWidth=0.4))
    left.add(String(54 * mm, y - 1 * mm, "Owner's budget", fontName="Helvetica", fontSize=6.5, fillColor=muted))
    left.add(String(84 * mm, y - 1 * mm, f"{d['loan'] / M:,.1f}", textAnchor="end", fontName="Helvetica", fontSize=6.5, fillColor=muted))
    y -= 5.2 * mm
    left.add(String(54 * mm, y - 1 * mm, "Result", fontName="Helvetica-Bold", fontSize=6.5, fillColor=ink))
    left.add(String(84 * mm, y - 1 * mm, f"{d['result'] / M:+,.1f}", textAnchor="end", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor("#2e7d32")))
    # the waterfall: 84 x 60 mm, the SVG geometry scaled from 300 x 150
    sx, sy = (84 * mm) / wf["width"], (60 * mm) / wf["height"]
    right = Drawing(84 * mm, 60 * mm)
    H = wf["height"]
    right.add(Line(0, (H - wf["zero"]) * sy, 84 * mm, (H - wf["zero"]) * sy, strokeColor=colors.HexColor("#c9d2e0"), strokeWidth=0.5))
    shades = {fc.POS: "#2e9e5b", fc.NEG: "#c84a57", fc.RESULT: "#2a8fc4", fc.OPENING: "#8da2c0"}
    for b in wf["bars"]:
        c = colors.HexColor(shades.get(b["colour"], b["colour"]))
        right.add(Rect(b["x"] * sx, (H - b["y"] - b["h"]) * sy, b["w"] * sx, b["h"] * sy, fillColor=c, strokeColor=None))
        right.add(String(b["cx"] * sx, (H - b["text_y"]) * sy, b["text"], textAnchor="middle", fontName="Helvetica-Bold", fontSize=6, fillColor=c))
        right.add(String(b["cx"] * sx, (H - b["label_y"]) * sy, bar_names.get(b["key"], b["label"]), textAnchor="middle", fontName="Helvetica", fontSize=5.5, fillColor=muted))
    t = Table([[left, right]], colWidths=[87 * mm, 87 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t


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

    def tiles(items, per_row=4):
        """Stat tiles as on the page: (label, value, sub, colour) each; a shaded cell per tile."""
        cells = [[Paragraph(e(l), tile_l), Paragraph(f"<font color='{c or '#1f2a44'}'><b>{e(v)}</b></font>", tile_v)] for l, v, sub, c in items]  # label and figure only (owner, 2026-10-24)
        data = [[cells[i] if i < len(cells) else "" for i in range(r, r + per_row)] for r in range(0, len(cells), per_row)]
        width = (174 * mm) / per_row
        t = Table(data, colWidths=[width] * per_row)
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
    kt = Table(kpis, colWidths=[40 * mm, 30 * mm, 104 * mm])
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), shade), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4cc3ff")),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 5)]))
    story += [kt, Spacer(1, 6), _pictures(d), Paragraph("1. Position", h2), Spacer(1, 2)]
    shade_rows = []
    rows = []
    for g in d["asset_groups"]:
        shade_rows.append(len(rows) + 1)
        rows.append([f"<b>{e(g['label'])}</b>", f"<b>{_m(g['total'])}</b>"])
        for label, value, note_ in g["rows"]:
            rows.append([f"&nbsp;&nbsp;&nbsp;{e(label)}", _m(value)])
    n = len(rows)
    rows += [["<b>Total assets</b>", f"<b>{_m(d['assets'])}</b>"],
             ["Owner's budget (loan)", _m(d["loan"])],
             ["<b>Result</b>", f"<font color='#2e7d32'><b>{_m(d['result'], True)}</b></font>"]]
    t = table(["Assets", "M ISK"], rows, [140 * mm, 34 * mm], total_rows=(n + 1,), green_rows=(len(rows),))
    t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), tint) for b in shade_rows]))
    story.append(t)

    story.append(Paragraph(f"2. Movements since {e(d['since_label'])}" + (f" ({base.day} {base:%B}, {base:%H:%M} EVE)" if d.get("period") is not None and d["period"].source else ""), h2))
    story.append(Spacer(1, 2))
    shade_rows = []
    mrows = []
    import re as _re
    for g in d["move_groups"]:
        shade_rows.append(len(mrows) + 1)
        mrows.append([f"<b>{e(g['label'])}</b>", f"<b>{_m(g['total'], True)}</b>"])
        if g["key"] in ("transfers", "lp"):
            continue  # one summed line (owner, 2026-10-24): the page has the movements, and section 4 has the LP detail
        direct = [(label, v, n_) for label, v, n_ in g["rows"] if label.startswith("Goods sold directly")]
        for label, v, n_ in g["rows"]:
            if label.startswith("Goods sold directly") or label.startswith("LP store:"):
                continue  # direct sales are summed below; a conversion moves nothing (having sold the items implies the store)
            mrows.append([f"&nbsp;&nbsp;&nbsp;{e(label)}", _m(v, True)])
        if direct:  # one line for all direct sales (owner, 2026-10-24), the item lists stay on the page
            left = 0.0
            for _, _, n_ in direct:
                m_ = _re.search(r"([\d.,]+) M of stock left the books", n_ or "")
                left += float(m_.group(1).replace(",", "")) if m_ else 0.0
            mrows.append([f"&nbsp;&nbsp;&nbsp;Direct sales ({len(direct)})", _m(sum(v for _, v, _ in direct), True)])
    mrows.append(["<b>Total</b>", f"<font color='#2e7d32'><b>{_m(d['period_result'], True)}</b></font>"])
    t = table(["Category", "M ISK"], mrows, [140 * mm, 34 * mm], total_rows=(len(mrows),))
    t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), tint) for b in shade_rows]))
    story.append(t)

    pb = d.get("project_bb") or {}
    if pb.get("active"):
        part = [Paragraph("3. Project buybacks", h2), Spacer(1, 2),
                tiles([("Net profit, this period", _m(pb["realised"], True), "after cost, tax and fees", sign_colour(pb["realised"])),
                       ("Margin on what sold", pct_(pb.get("margin")), f"{_m(pb['sold_value'])} sold, {_m(pb['cost_sold'])} paid for it", sign_colour(pb.get("margin"))),
                       ("Projected on goods held", _m(pb["expected"], True), f"{_m(pb['held'])} at cost, {_m(pb['held_value'])} at Jita buy", None),
                       ("Paid to members, this period", _m(pb["paid_total"]), "", None)]), Spacer(1, 3)]
        first = True
        for mo in pb["months"]:
            block = [Paragraph(f"<b>{e(mo['label'])}</b>", p)]
            rows = []
            bold = []
            for g in mo["groups"]:
                bold.append(len(rows) + 1)
                rows.append([f"<b>{e(g['label'])}</b> <font size='6.5' color='#5b6b82'>{len(g['rows'])} items" + (f", {g['members']} members" if g["members"] else "") + "</font>",
                             f"<b>{_m(g['paid'])}</b>", f"<b>{_m(g['revenue'])}</b>", f"<b>{_m(g['cost'])}</b>", f"<b>{_m(g['fees'])}</b>", f"<b>{_m(g['net'], True)}</b>",
                             f"<b>{g['pct'] * 100:.0f} %</b>" if g["pct"] is not None else "–", f"<b>{_m(g['held_cost'])}</b>", f"<b>{_m(g['expected'], True)}</b>" if g["held_cost"] else "–"])
            rows.append(["<b>Total</b>", f"<b>{_m(mo['paid_total'])}</b>", f"<b>{_m(mo['sold_value'])}</b>", f"<b>{_m(mo['cost_sold'])}</b>", f"<b>{_m(mo['fees'])}</b>",
                         f"<b>{_m(mo['realised'], True)}</b>", f"<b>{mo['pct'] * 100:.0f} %</b>" if mo["pct"] is not None else "", f"<b>{_m(mo['held_cost'])}</b>",
                         f"<b>{_m(mo['expected'], True)}</b>" if mo["held_cost"] else ""])
            t = table(["", "Paid to members", "Sold for", "Cost", "Tax and fees", "Net profit", "Margin", "Still held", "Projected"], rows,
                      [49 * mm, 19 * mm, 17 * mm, 17 * mm, 16 * mm, 18 * mm, 15 * mm, 17 * mm, 20 * mm], total_rows=(len(rows),), numeric=(1, 2, 3, 4, 5, 6, 7, 8))
            t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), tint) for b in bold]))
            block.append(t)
            block += [Spacer(1, 6)]
            if first:
                story.append(KeepTogether(part + block[:1]))
                story.extend(block[1:])
                first = False
            else:
                story.extend(block)
        story.append(Spacer(1, 2))

    bb = d.get("buyback") or {}
    if bb.get("active"):
        part = [Paragraph("4. LP buybacks and conversions", h2), Spacer(1, 2),
                tiles([("Net profit", _m(bb["realised"], True), "after cost, tax and fees", sign_colour(bb["realised"])),
                       ("Margin on what sold", pct_(bb.get("margin")), f"{_m(bb['sold_value'])} sold, {_m(bb['cost_sold'])} of LP, inputs and ISK", sign_colour(bb.get("margin"))),
                       ("Projected on what is listed", _m(bb["expected"], True), "at list price, after sales tax", None),
                       ("LP not converted", f"{bb['lp_left']:,.0f} LP", f"{_m(bb['lp_left_value'])} at cost", None)]), Spacer(1, 4)]
        first = True
        for mo in bb["months"]:
            block = [Paragraph(f"<b>{e(mo['label'])}</b>", p),
                     tiles([("LP bought", f"{mo['lp_bought']:,} LP" if mo["lp_bought"] else "none", f"{_m(mo['lp_isk'])}, {mo['lp_avg']:,.0f} ISK per LP" if mo["lp_bought"] else "", None),
                            ("LP converted", f"{mo['lp_converted']:,} LP", "", None),
                            ("LP sold directly", f"{mo['lp_sold']:,} LP" if mo.get("lp_sold") else "none", f"{_m(mo['lp_sold_isk'])}, {mo['lp_sold_avg']:,.0f} ISK per LP" if mo.get("lp_sold") else "", None),
                            ("Net profit", _m(mo["realised"], True), f"{_m(mo['expected'], True)} projected" if mo["expected"] else "", sign_colour(mo["realised"]))])]
            if mo["sales"] or mo["still"] or mo.get("lp_sold"):
                srows = [[e(x["name"]), f"{x['sold']:,.0f}", _m(x["revenue"]), _m(x["tax"]), _m(x["broker"]), _m(x["cost"]), f"<b>{_m(x['net'], True)}</b>"] for x in mo["sales"]]
                if mo.get("lp_sold"):
                    srows.append(["LP sold directly", f"{mo['lp_sold']:,}", _m(mo["lp_sold_isk"]), "", "", _m(mo["lp_sold_cost"]), f"<b>{_m(mo['lp_sold_net'], True)}</b>"])
                for v in mo["still"]:
                    srows.append([f"{e(v['name'])}, listed", f"{v['units']:,}", _m(v["value"]), "", "", _m(v["cost"]), f"{_m(v['expected'], True)} projected"])
                sold = sum(x["sold"] for x in mo["sales"]) + (mo.get("lp_sold") or 0)
                revenue = sum(x["revenue"] for x in mo["sales"]) + (mo.get("lp_sold_isk") or 0)
                cost = sum(x["cost"] for x in mo["sales"]) + (mo.get("lp_sold_cost") or 0)
                srows.append(["<b>Total</b>", f"<b>{sold:,.0f}</b>", f"<b>{_m(revenue)}</b>", f"<b>{_m(sum(x['tax'] for x in mo['sales']))}</b>",
                              f"<b>{_m(sum(x['broker'] for x in mo['sales']))}</b>", f"<b>{_m(cost)}</b>",
                              f"<font color='#2e7d32'><b>{_m(mo['realised'], True)}</b></font>" + (f" <font size='6.5' color='#5b6b82'>{_m(mo['expected'], True)} projected</font>" if mo["expected"] else "")])
                block += [Spacer(1, 3), table(["Sales", "Sold", "Revenue", "Sales tax", "Broker", "Cost", "Net profit"], srows,
                                              [56 * mm, 14 * mm, 24 * mm, 18 * mm, 16 * mm, 20 * mm, 26 * mm], total_rows=(len(srows),), numeric=(1, 2, 3, 4, 5, 6))]
            block += [Spacer(1, 6)]
            if first:
                story.append(KeepTogether(part + block))
                first = False
            else:
                story.append(KeepTogether(block))
        buying = bb.get("buying") or []
        if buying:
            brows = [[e(o["name"]), f"{o['remain']:,} / {o['total']:,}", f"{o['price']:,.2f}", _m(o["escrow"])] for o in buying]
            story += [Spacer(1, 4), table(["Buying now", "Still to buy", "Price", "ISK in escrow"], brows, [74 * mm, 34 * mm, 30 * mm, 36 * mm], numeric=(1, 2, 3))]

    if d["fuel_rows"]:
        frows = []
        for f in d["fuel_rows"]:
            frows.append([e(f["name"]) + (", fuel sponsored" if f["sponsored"] else ""), str(f["bph"]), str(f["bph"] * 24), _m(f["day"]), _m(f["month"])])
        pay = d["fuel_paying_bph"]
        frows.append(["<b>Cost to the alliance</b>", f"<b>{pay}</b>", f"<b>{pay * 24}</b>", f"<b>{_m(pay * 24 * d['fuel_price'])}</b>", f"<b>{_m(pay * 24 * 30 * d['fuel_price'])}</b>"])
        story.append(KeepTogether([
            Paragraph(f"5. Structure fuel <font size='8' color='#5b6b82'>{e(d['fuel_name'])} {d['fuel_price']:,.0f} ISK at {e(d['market'])}</font>", h2),
            Spacer(1, 2),
            table(["Structure", "Blocks / hour", "Blocks / day", "ISK / day", "ISK / 30 days"], frows, [74 * mm, 22 * mm, 24 * mm, 26 * mm, 28 * mm],
                  total_rows=(len(frows),), numeric=(1, 2, 3, 4)),
            Paragraph(f"Burned since the baseline: {d['fuel_burned']:,} blocks, {d['fuel_burned_isk'] / M:.1f} M.", note),
        ]))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"OARMI balance sheet {cut:%Y-%m-%d}", author="The Orlov Family")
    doc.build(story)
    return buf.getvalue()
