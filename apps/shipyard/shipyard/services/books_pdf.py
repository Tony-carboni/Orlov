"""The balance sheet as a PDF (reportlab), drawn from books.compute(): the layout of the directors'
sheets of 18 to 20 October 2026 (docs/finance/)."""

import io

M = 1e6


def _m(v, sign=False):
    if v is None:
        return "–"
    return f"{v / M:+,.1f} M" if sign else f"{v / M:,.1f} M"


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
    line, shade, green = colors.HexColor("#1f2a44"), colors.HexColor("#eef2f8"), colors.HexColor("#e7f4e8")
    e = lambda s: escape(str(s))  # noqa: E731

    def table(header, rows, widths, total_rows=(), green_rows=(), numeric=(1,)):
        data = [[Paragraph(f"<b>{e(h)}</b>", num if i in numeric else cell) for i, h in enumerate(header)]]
        for r in rows:
            data.append([Paragraph(str(c), num if i in numeric else cell) for i, c in enumerate(r)])
        t = Table(data, colWidths=widths, repeatRows=1)
        st = [("LINEBELOW", (0, 0), (-1, 0), 0.8, line), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 4)]
        for i in total_rows:
            st += [("BACKGROUND", (0, i), (-1, i), shade), ("LINEABOVE", (0, i), (-1, i), 0.8, line)]
        for i in green_rows:
            st += [("BACKGROUND", (0, i), (-1, i), green)]
        t.setStyle(TableStyle(st))
        return t

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
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), shade), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 5)]))
    story += [kt, Paragraph("1. Position", h2), Spacer(1, 2)]
    shade_rows = []
    rows = []
    for g in d["asset_groups"]:
        shade_rows.append(len(rows) + 1)
        rows.append([f"<b>{e(g['label'])}</b>", f"<b>{_m(g['total'])}</b>", e(g.get("note", ""))])
        for label, value, note_ in g["rows"]:
            rows.append([f"&nbsp;&nbsp;&nbsp;{e(label)}", _m(value), e(note_)])
    n = len(rows)
    rows += [["<b>Total assets</b>", f"<b>{_m(d['assets'])}</b>", ""],
             ["Owner's budget (loan)", _m(d["loan"]), ""],
             ["<b>Result</b>", f"<font color='#2e7d32'><b>{_m(d['result'], True)}</b></font>", ""]]
    t = table(["Assets", "M ISK", ""], rows, [78 * mm, 26 * mm, 70 * mm], total_rows=(n + 1,), green_rows=(len(rows),))
    t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), colors.HexColor("#f4f6fa")) for b in shade_rows]))
    story.append(t)
    bits = []
    if d["director"] is not None:
        bits.append(f"Director division {_m(d['director'])}")
    if d["structure_income"] is not None:
        bits.append(f"structure income waiting {_m(d['structure_income'])}")
    if d["older"][0] >= 0.05 * M:
        bits.append(f"older goods {_m(d['older'][0])} at cost")
    text = ("Not counted: " + ", ".join(bits) + ". ") if bits else ""
    hg = d.get("hangar") or {}
    if hg.get("read_at"):
        text += f"Goods held = the projects hangar read at {hg['read_at']:%H:%M} EVE ({hg.get('types', 0)} types), at what the projects paid."
    else:
        text += "Goods held follow the ledger (hangar not read yet)."
    ign = d.get("ignored") or {}
    if ign.get("count"):
        text += f" {ign['count']} journal lines ignored ({_m(ign['net'], True)}), corrections pending."
    story.append(Paragraph(text, note))

    story.append(Paragraph(f"2. Movements since {e(d['since_label'])}" + (f" ({base.day} {base:%B}, {base:%H:%M} EVE)" if d.get("period") is not None and d["period"].source else ""), h2))
    story.append(Spacer(1, 2))
    shade_rows = []
    mrows = []
    for g in d["move_groups"]:
        shade_rows.append(len(mrows) + 1)
        mrows.append([f"<b>{e(g['label'])}</b>", f"<b>{_m(g['total'], True)}</b>", e(g["note"])])
        for label, v, n_ in g["rows"]:
            mrows.append([f"&nbsp;&nbsp;&nbsp;{e(label)}", _m(v, True), e(n_)])
    mrows.append(["<b>Total</b>", f"<font color='#2e7d32'><b>{_m(d['period_result'], True)}</b></font>",
                  f"result {_m(d['result'], True)} less the opening {_m(d['opening_result'], True)}" if d.get("period") is not None and d["period"].source else ""])
    t = table(["Category", "M ISK", ""], mrows, [72 * mm, 24 * mm, 78 * mm], total_rows=(len(mrows),))
    t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), colors.HexColor("#f4f6fa")) for b in shade_rows]))
    story.append(t)

    pb = d.get("project_bb") or {}
    if pb.get("active"):
        part = [Paragraph("3. Project buybacks", h2), Spacer(1, 2)]
        at = pb.get("all_time") or {}
        if at.get("first"):
            margin = f"{at['margin'] * 100:.0f} %" if at.get("margin") is not None else "–"
            part.append(Paragraph(f"<b>Since the first project ({at['first']:%-d %B %Y}):</b> {_m(at['paid'])} paid to {at['members']} members; "
                                  f"net profit {_m(at['net'], True)} on what sold ({_m(at['sold'])} sold against {_m(at['cost'])} paid and {_m(abs(at['fees']))} of fees), margin {margin}, sold stock only"
                                  + (f"; {_m(at['written_off'])} written off on the stock take left out" if at.get("written_off") else "") + ".", p))
            part.append(Spacer(1, 4))
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
                for r in g["rows"]:
                    extra = []
                    if r["delivered"]:
                        extra.append(f"{r['delivered']:,.0f} delivered" + (f" by {r['members']}" if r["members"] else ""))
                    if r["sold"]:
                        extra.append(f"{r['sold']:,.0f} sold")
                    if r["unmatched"]:
                        extra.append(f"plus {_m(r['unmatched'])} from older stock")
                    rows.append([f"&nbsp;&nbsp;&nbsp;{e(r['name'])}" + (f" <font size='6.5' color='#5b6b82'>{e(' · '.join(extra))}</font>" if extra else ""),
                                 _m(r["paid"]) if r["paid"] else "–", _m(r["revenue"]) if r["revenue"] else "–", _m(r["cost"]) if r["cost"] else "–",
                                 _m(r["fees"]) if r["fees"] else "–", _m(r["net"], True) if r["revenue"] else "–",
                                 f"{r['pct'] * 100:.0f} %" if r["pct"] is not None else "–", _m(r["held_cost"]) if r["held_cost"] else "–",
                                 _m(r["expected"], True) if r["held_cost"] else "–"])
            rows.append(["<b>Total</b>", f"<b>{_m(mo['paid_total'])}</b>", f"<b>{_m(mo['sold_value'])}</b>", f"<b>{_m(mo['cost_sold'])}</b>", f"<b>{_m(mo['fees'])}</b>",
                         f"<b>{_m(mo['realised'], True)}</b>", f"<b>{mo['pct'] * 100:.0f} %</b>" if mo["pct"] is not None else "", f"<b>{_m(mo['held_cost'])}</b>",
                         f"<b>{_m(mo['expected'], True)}</b>" if mo["held_cost"] else ""])
            t = table(["", "Paid to members", "Sold for", "Cost", "Tax and fees", "Net profit", "Margin", "Still held", "Projected"], rows,
                      [49 * mm, 19 * mm, 17 * mm, 17 * mm, 16 * mm, 18 * mm, 15 * mm, 17 * mm, 20 * mm], total_rows=(len(rows),), numeric=(1, 2, 3, 4, 5, 6, 7, 8))
            t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), colors.HexColor("#f4f6fa")) for b in bold]))
            block.append(t)
            block += [Spacer(1, 6)]
            if first:
                story.append(KeepTogether(part + block[:1]))
                story.extend(block[1:])
                first = False
            else:
                story.extend(block)
        story.append(Paragraph("Projected = goods held at Jita's highest buy, less sales tax at the rate paid so far, less cost.", note))

    bb = d.get("buyback") or {}
    if bb.get("active"):
        part = [Paragraph("4. LP buybacks and conversions", h2), Spacer(1, 2)]
        first = True
        for mo in bb["months"]:
            block = [Paragraph(f"<b>{e(mo['label'])}</b>", p)]
            lp_line = (f"{mo['lp_bought']:,} LP for {_m(mo['lp_isk'])} ({mo['lp_avg']:,.0f} ISK per LP)" if mo["lp_bought"] else "none")
            sold_line = (f" LP sold directly: {mo['lp_sold']:,} LP for {_m(mo['lp_sold_isk'])} ({mo['lp_sold_avg']:,.0f} ISK per LP), {_m(mo['lp_sold_cost'])} at cost, "
                         f"profit {_m(mo['lp_sold_net'], True)}." if mo.get("lp_sold") else "")
            block.append(Paragraph(f"LP bought: {lp_line}. LP converted: {mo['lp_converted']:,} LP.{sold_line}", p))
            if mo["converted"]:
                crows = []
                for c in mo["converted"]:
                    inputs = f" + {c['input_units']:,.0f} {e(c['input'])} ({_m(c['input_cost'])})" if c["input_units"] else ""
                    crows.append([e(c["name"]), f"{c['units']:,.0f}", _m(c["cost"]), f"{c['unit_cost']:,.0f}",
                                  f"<font size='7'>{c['lp']:,} LP ({_m(c['lp_value'])}){inputs} + LP store ISK {_m(c['isk'])}</font>"])
                block += [Spacer(1, 3), table(["Converted into", "Units", "Cost", "Cost each", "Made of"], crows, [48 * mm, 16 * mm, 20 * mm, 20 * mm, 70 * mm], numeric=(1, 2, 3))]
            if mo["sales"] or mo["still"]:
                srows = [[e(x["name"]), f"{x['sold']:,.0f}", _m(x["revenue"]), _m(x["tax"]), _m(x["broker"]), _m(x["cost"]), f"<b>{_m(x['net'], True)}</b>"] for x in mo["sales"]]
                for v in mo["still"]:
                    srows.append([f"{e(v['name'])}, still on sell orders", f"{v['units']:,}", f"{_m(v['value'])} at list", "", "", _m(v["cost"]), f"{_m(v['expected'], True)} projected"])
                block += [Spacer(1, 3), table(["Sales on converted items", "Sold", "Revenue", "Sales tax", "Broker", "Cost", "Net profit"], srows,
                                              [56 * mm, 14 * mm, 24 * mm, 18 * mm, 16 * mm, 20 * mm, 26 * mm], numeric=(1, 2, 3, 4, 5, 6))]
            more = f", {_m(mo['expected'], True)} projected" if mo["expected"] else ""
            block += [Spacer(1, 3), Paragraph(f"<b>Net profit {_m(mo['realised'], True)}</b>{more}.", p), Spacer(1, 6)]
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
