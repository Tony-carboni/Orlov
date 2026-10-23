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
        Paragraph("Orlov Arms International · simplified balance sheet", h1),
        Paragraph(f"As of {cut.day} {cut:%B %Y}, {cut:%H:%M} EVE time. Movements since {e(d['since_label'])}"
                  + (f" ({base.day} {base:%B}, {base:%H:%M} EVE)" if d.get("period") is not None and d["period"].source else "")
                  + ". Figures from EVE (ESI) through auth. All amounts in millions of ISK. Prepared for the directors of The Orlov Family.", sub),
        Paragraph("1. Position against the baseline", h2),
        Paragraph(f"On {d['origin'].day} {d['origin']:%B} the corporation's money was separated from the owner's. The corporation works with a budget of {d['loan'] / M:,.0f} M lent by "
                  "the owner, interest-free and without a repayment date. That loan counts as nothing: the corporation's result is everything above or below it."
                  + (f" Since {e(d['since_label'])} the result moved {_m(d['period_result'], True)} (the opening was {_m(d['opening_result'], True)} above the loan)." if d.get("period") is not None and d["period"].source else ""), p),
        Spacer(1, 4),
    ]
    shade_rows = []
    rows = []
    for g in d["asset_groups"]:
        shade_rows.append(len(rows) + 1)
        rows.append([f"<b>{e(g['label'])}</b>", f"<b>{_m(g['total'])}</b>", e(g.get("note", ""))])
        for label, value, note_ in g["rows"]:
            rows.append([f"&nbsp;&nbsp;&nbsp;{e(label)}", _m(value), e(note_)])
    n = len(rows)
    rows += [["<b>Total assets</b>", f"<b>{_m(d['assets'])}</b>", ""], ["<b>Liabilities</b>", "", ""],
             ["Loan from the owner (the working budget)", _m(d["loan"]), "Interest-free, perpetual, extractable when the corporation can bear it"],
             ["<b>Result: assets above the loan</b>", f"<font color='#2e7d32'><b>{_m(d['result'], True)}</b></font>", "The corporation's own money"]]
    t = table(["Assets", "ISK", "How it is valued"], rows, [78 * mm, 26 * mm, 70 * mm], total_rows=(n + 1,), green_rows=(len(rows),))
    t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), colors.HexColor("#f4f6fa")) for b in shade_rows]))
    story.append(t)
    outside = []
    if d["director"] is not None:
        outside.append(f"wallet division 7 (the Director division, {d['director'] / M:,.1f} M), the owner's characters' shared wallet")
    text = "Not included: " + (outside[0] + ". " if outside else "")
    text += (f"Project goods paid for before the baseline and not sold yet, an estimated {d['older'][0] / M:,.0f} M at cost ({d['older'][1] / M:,.0f} M at Jita buy), "
             "were never part of the budget; they count when they sell.")
    if d["structure_income"] is not None:
        text += f" Structure income earned since the last transfer to the corporation, {d['structure_income'] / M:.1f} M, still sits in the structure corporation's wallet."
    hg = d.get("hangar") or {}
    if hg.get("read_at"):
        text += f" The goods held from project buybacks are the projects hangar as read from EVE at {hg['read_at']:%Y-%m-%d %H:%M} EVE ({hg.get('types', 0)} item types), at what the projects paid."
    else:
        text += " The goods held from project buybacks follow the ledger (the hangar has not been read from EVE yet)."
    ign = d.get("ignored") or {}
    if ign.get("count"):
        text += f" {ign['count']} journal lines are left out of the books ({_m(ign['net'], True)} together): mistakes being corrected, which net to zero once the corrections land."
    story.append(Paragraph(text, note))

    story.append(Paragraph(f"2. What happened since {e(d['since_label'])}" + (f" ({base.day} {base:%B}, {base:%H:%M} EVE)" if d.get("period") is not None and d["period"].source else ""), h2))
    story.append(Paragraph("Every journal line since the baseline lands in exactly one category, so the categories add up to the result.", p))
    story.append(Spacer(1, 4))
    shade_rows = []
    mrows = []
    for g in d["move_groups"]:
        shade_rows.append(len(mrows) + 1)
        mrows.append([f"<b>{e(g['label'])}</b>", f"<b>{_m(g['total'], True)}</b>", e(g["note"])])
        for label, v, n_ in g["rows"]:
            mrows.append([f"&nbsp;&nbsp;&nbsp;{e(label)}", _m(v, True), e(n_)])
    mrows.append([f"<b>Total since {e(d['since_label'])}</b>", f"<font color='#2e7d32'><b>{_m(d['period_result'], True)}</b></font>",
                  f"The result in section 1 minus the opening of {_m(d['opening_result'], True)}" if d.get("period") is not None and d["period"].source else "Equals the result in section 1"])
    t = table(["Category", "ISK", "Note"], mrows, [72 * mm, 24 * mm, 78 * mm], total_rows=(len(mrows),))
    t.setStyle(TableStyle([("BACKGROUND", (0, b), (-1, b), colors.HexColor("#f4f6fa")) for b in shade_rows]))
    story.append(t)

    pb = d.get("project_bb") or {}
    if pb.get("active"):
        part = [Paragraph("3. Project buybacks", h2),
                Paragraph("Per month: what the corporation projects paid members, what the corporation sold of those goods at what the projects paid for them "
                          "(first in, first out; ores count through the minerals they reprocess into), with sales tax and broker fees, and what is still held.", p),
                Spacer(1, 4)]
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
            pct = f" ({mo['pct'] * 100:.0f} % over what the projects paid)" if mo["pct"] is not None else ""
            more = (f", {_m(mo['expected'], True)} more projected on the {_m(mo['held_cost'])} still held: {_m(mo['total'], True)} in total" if mo["expected"] else "")
            block += [Spacer(1, 3), Paragraph(f"<b>Summary:</b> {_m(mo['paid_total'])} paid to {mo['members']} members; {_m(mo['sold_value'])} of project goods sold. "
                                              f"Net profit {_m(mo['realised'], True)}{pct}{more}.", p), Spacer(1, 6)]
            if first:
                story.append(KeepTogether(part + block[:1]))
                story.extend(block[1:])
                first = False
            else:
                story.extend(block)
        story.append(Paragraph(f"Paid to members comes from the contributions read every hour (section 2 uses the fall of the projects' pool: {_m(pb['paid_pool'])}). "
                               "Goods still held are valued at Jita's highest buy, less sales tax at the rate paid so far. Older stock, "
                               f"{_m(pb['older'])} at cost, is not in these figures.", note))

    bb = d.get("buyback") or {}
    if bb.get("active"):
        part = [Paragraph("4. LP buybacks and conversions", h2),
                Paragraph("Per month: the LP the corporation bought and converted, what it became in the LP store, what that sold for after sales tax and broker "
                          "fees, and what is still on sell orders. Items bought to convert but not converted yet are ordinary stock in section 1.", p), Spacer(1, 4)]
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
            summary = []
            if mo["lp_bought"]:
                summary.append(f"{_m(mo['lp_isk'])} of LP bought")
            if mo["converted"]:
                listed = f", {_m(mo['listed_value'])} still listed" if mo["listed_value"] else ""
                summary.append(f"converted into {_m(mo['output_value'])} of sell orders ({_m(mo['sold_value'])} sold{listed})")
            more = f", {_m(mo['expected'], True)} more projected: {_m(mo['total'], True)} in total" if mo["expected"] else ""
            block += [Spacer(1, 3), Paragraph(f"<b>Summary:</b> {', '.join(summary) or 'no LP activity'}. Net profit {_m(mo['realised'], True)}{more}.", p), Spacer(1, 6)]
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
            Paragraph("5. Running costs: structure fuel", h2),
            Paragraph(f"Fuel need of the online service modules, priced at today's cheapest fuel block at {e(d['market'])} ({e(d['fuel_name'])}, {d['fuel_price']:,.0f} ISK). "
                      "Sponsored structures cost the alliance nothing.", p),
            Spacer(1, 4),
            table(["Structure", "Blocks / hour", "Blocks / day", "ISK / day", "ISK / 30 days"], frows, [74 * mm, 22 * mm, 24 * mm, 26 * mm, 28 * mm],
                  total_rows=(len(frows),), numeric=(1, 2, 3, 4)),
            Paragraph(f"Burned since the baseline by the structures the alliance pays for: {d['fuel_burned']:,} blocks, {d['fuel_burned_isk'] / M:.1f} M.", note),
        ]))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"OARMI balance sheet {cut:%Y-%m-%d}", author="The Orlov Family")
    doc.build(story)
    return buf.getvalue()
