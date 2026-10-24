"""The Finance tab's two pictures (owner's pick "C", 2026-10-24): a donut of what the assets are in, and a
waterfall from the period's opening through the categories to the result. Pure geometry from books.compute();
the page draws it as inline SVG, the PDF with reportlab's shapes, both from the same numbers."""

M = 1e6
ASSET_COLOURS = {"cash": "#4cc3ff", "pool": "#2a8fc4", "held": "#ffd75e", "listed": "#8adaff", "physical": "#d7dfea", "lp": "#b197e6"}
POS, NEG, RESULT, OPENING = "#5bd48a", "#f28b94", "#4cc3ff", "#8da2c0"
SHORT = {"project_sales": "Buyback sales", "project_rewards": "Rewards", "lp": "LP", "stock": "Stock", "market": "Market",
         "structure": "Structure", "transfers": "Transfers", "gap": "Not explained"}


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


def waterfall(move_groups, opening: float = 0.0, width: int = 420, height: int = 190) -> dict:
    """Bars from the opening through every category with a movement to the result. Coordinates for a
    viewBox of width x height: the floor is at height - 40, labels sit under it, values above each bar."""
    steps = []
    if abs(opening) >= 0.05 * M:
        steps.append({"key": "opening", "label": "Opening", "value": float(opening), "kind": "opening"})
    for g in move_groups:
        value = float(g["total"])
        if abs(value) < 0.05 * M:
            continue
        steps.append({"key": g["key"], "label": SHORT.get(g["key"], g["label"]), "value": value, "kind": "pos" if value >= 0 else "neg"})
    result = float(opening) + sum(float(g["total"]) for g in move_groups)
    steps.append({"key": "result", "label": "Result", "value": result, "kind": "result"})
    # the running level after each step; the opening and the result bars stand on zero
    levels, run = [], 0.0
    for s in steps:
        if s["kind"] in ("opening", "result"):
            lo, hi = min(0.0, s["value"]), max(0.0, s["value"])
            run = s["value"]
        else:
            lo, hi = min(run, run + s["value"]), max(run, run + s["value"])
            run += s["value"]
        levels.append((lo, hi))
    top, floor = 26.0, float(height - 40)
    vmin = min([0.0] + [lo for lo, _ in levels])
    vmax = max([0.0] + [hi for _, hi in levels])
    span = (vmax - vmin) or 1.0
    k = (floor - top) / span

    def y(v):
        return floor - (v - vmin) * k

    n = len(steps)
    gap = 10.0
    w = max(8.0, (width - 20 - gap * (n - 1)) / n)
    bars = []
    for i, (s, (lo, hi)) in enumerate(zip(steps, levels)):
        x = 10 + i * (w + gap)
        y_top, y_bot = y(hi), y(lo)
        h = max(2.0, y_bot - y_top)
        colour = {"opening": OPENING, "result": RESULT, "pos": POS, "neg": NEG}[s["kind"]]
        text = f"{s['value'] / M:+,.0f}" if s["kind"] in ("pos", "neg") else f"{s['value'] / M:,.0f}"
        bars.append({**s, "x": round(x, 1), "y": round(y_top, 1), "w": round(w, 1), "h": round(h, 1), "cx": round(x + w / 2, 1),
                     "colour": colour, "text": text, "text_y": round(max(10.0, y_top - 5), 1), "label_y": floor + 16})
    return {"width": width, "height": height, "floor": floor, "zero": round(y(0.0), 1), "bars": bars, "result": result}
