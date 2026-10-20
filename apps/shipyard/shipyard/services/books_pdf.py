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
        Paragraph(f"As of {cut.day} {cut:%B %Y}, {cut:%H:%M} EVE time. Movements since the working-budget baseline of {base.day} {base:%B}, {base:%H:%M} EVE. "
                  "Figures from EVE (ESI) through auth. All amounts in millions of ISK. Prepared for the directors of The Orlov Family.", sub),
        Paragraph("1. Position against the baseline", h2),
        Paragraph(f"On {base.day} {base:%B} the corporation's money was separated from the owner's. The corporation works with a budget of {d['loan'] / M:,.0f} M lent by "
                  "the owner, interest-free and without a repayment date. That loan counts as nothing: the corporation's result is everything above or below it.", p),
        Spacer(1, 4),
    ]
    rows = [["Master wallet, division 1 (liquid)", _m(d["wallet"]), "Balance from the corporation's journal"],
            [f"Reward ISK still inside the {d['n_projects']} active corporation projects", _m(d["pool"]), "Rewards not yet paid out, read from EVE"]]
    for s in d["stock"]:
        if s["units"] or s["sold"]:
            listed = f" (listed at {s['list_price']:g} in {e(s['location'].split(' - ')[0])})" if s["list_price"] else ""
            rows.append([f"{e(s['name'])} stock, {s['units']:,.0f} units{listed}", _m(s["value"]), f"At buy value, {s['unit_cost']:g} ISK a unit; {s['sold']:,.0f} units sold since the baseline"])
    held_list = ", ".join(f"{e(k)} {v / M:.1f}" for k, v in d["held"] if v >= 0.05 * M)
    rows.append(["Goods bought through projects since the baseline, not sold yet", _m(d["held_total"]),
                 f"At what the projects paid for them ({d['held_value'] / M:.1f} M at Jita's highest buy){'; ' + held_list if held_list else ''}"])
    if d["lp_cost"]:
        rows.append([f"Loyalty points, {d['lp_units']:,} LP", _m(d["lp_cost"]), "At cost, as paid from the corporation's wallets"])
    if abs(d["other_divs"]) >= 0.05 * M:
        rows.append(["Wallet divisions 2 to 6", _m(d["other_divs"]), "Balances from the corporation's journal"])
    n = len(rows)
    rows += [["<b>Total assets</b>", f"<b>{_m(d['assets'])}</b>", ""], ["<b>Liabilities</b>", "", ""],
             ["Loan from the owner (the working budget)", _m(d["loan"]), "Interest-free, perpetual, extractable when the corporation can bear it"],
             ["<b>Result: assets above the loan</b>", f"<font color='#2e7d32'><b>{_m(d['result'], True)}</b></font>", "The corporation's own money"]]
    story.append(table(["Assets", "ISK", "How it is valued"], rows, [78 * mm, 26 * mm, 70 * mm], total_rows=(n + 1,), green_rows=(len(rows),)))
    outside = []
    if d["director"] is not None:
        outside.append(f"wallet division 7 (the Director division, {d['director'] / M:,.1f} M), the owner's characters' shared wallet")
    text = "Not included: " + (outside[0] + ". " if outside else "")
    text += (f"Project goods paid for before the baseline and not sold yet, an estimated {d['older'][0] / M:,.0f} M at cost ({d['older'][1] / M:,.0f} M at Jita buy), "
             "were never part of the budget; they count when they sell.")
    if d["structure_income"] is not None:
        text += f" Structure income earned since the last transfer to the corporation, {d['structure_income'] / M:.1f} M, still sits in the structure corporation's wallet."
    story.append(Paragraph(text, note))

    story.append(Paragraph(f"2. What happened since the baseline ({base.day} {base:%B}, {base:%H:%M} EVE)", h2))
    mrows = [[e(label), _m(v, True), e(n_)] for label, v, n_ in d["moves"]]
    mrows.append(["<b>Total since the baseline</b>", f"<font color='#2e7d32'><b>{_m(sum(m[1] for m in d['moves']), True)}</b></font>", "Equals the result in section 1"])
    story.append(table(["Movement", "ISK", "Note"], mrows, [72 * mm, 24 * mm, 78 * mm], total_rows=(len(mrows),)))

    if d["fuel_rows"]:
        frows = []
        for f in d["fuel_rows"]:
            frows.append([e(f["name"]) + (", fuel sponsored" if f["sponsored"] else ""), str(f["bph"]), str(f["bph"] * 24), _m(f["day"]), _m(f["month"])])
        pay = d["fuel_paying_bph"]
        frows.append(["<b>Cost to the alliance</b>", f"<b>{pay}</b>", f"<b>{pay * 24}</b>", f"<b>{_m(pay * 24 * d['fuel_price'])}</b>", f"<b>{_m(pay * 24 * 30 * d['fuel_price'])}</b>"])
        story.append(KeepTogether([
            Paragraph("3. Running costs: structure fuel", h2),
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
