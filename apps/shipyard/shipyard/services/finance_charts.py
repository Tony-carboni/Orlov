"""The Finance tab's donut of what the assets are in (owner's pick "C", 2026-10-24). Pure geometry from
books.compute(); the page draws it as inline SVG, the PDF with reportlab's shapes, both from the same numbers.
The waterfall that stood next to it made way for four period tiles (0.34.0)."""

M = 1e6
ASSET_COLOURS = {"cash": "#4cc3ff", "pool": "#2a8fc4", "held": "#ffd75e", "listed": "#8adaff", "physical": "#d7dfea", "lp": "#b197e6"}


def donut(asset_groups) -> dict:
    """Segments of a ring (circumference 100, as SVG stroke-dasharray on r=15.9) and their angles for the PDF.
    Returns {"total", "segments": [{key, label, total, pct, colour, dash, offset, start, end}]}."""
    total = sum(float(g["total"]) for g in asset_groups)
    out, acc = [], 0.0
    for g in asset_groups:
        value = float(g["total"])
        if value <= 0 or total <= 0:
            continue
        pct = value / total * 100
        out.append({"key": g["key"], "label": g["label"], "total": value, "pct": pct, "colour": ASSET_COLOURS.get(g["key"], "#6c757d"),
                    "dash": f"{pct:.2f} {100 - pct:.2f}", "offset": f"{25 - acc:.2f}",
                    "start": 90 - acc * 3.6, "end": 90 - (acc + pct) * 3.6})  # degrees, clockwise from the top
        acc += pct
    return {"total": total, "segments": out}

