from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def isk(value, digits=1):
    """92683787 → '92.7 M'; None → '–'."""
    if value is None:
        return "–"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "–"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        return f"{sign}{a / 1e9:.{digits}f} B"
    if a >= 1e6:
        return f"{sign}{a / 1e6:.{digits}f} M"
    if a >= 1e3:
        return f"{sign}{a / 1e3:.{digits}f} k"
    return f"{sign}{a:.0f}"


@register.filter
def isk_full(value):
    if value is None:
        return "–"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "–"


@register.filter
def paragraphs(text):
    """Plain text to HTML: a blank line starts a paragraph, lines starting with '- ' make a list."""
    out, para, items = [], [], []

    def flush():
        nonlocal para, items
        if items:
            out.append("<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>")
            items = []
        if para:
            out.append("<p>" + "<br>".join(escape(line) for line in para) + "</p>")
            para = []

    for raw in (text or "").replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith("- ") or line.startswith("* "):
            if para:
                flush()
            items.append(line[2:].strip())
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return mark_safe("".join(out))


@register.filter
def lines(text):
    """One list item per non-empty line (for pros and cons)."""
    return [ln.strip().lstrip("-* ").strip() for ln in (text or "").replace("\r", "").split("\n") if ln.strip()]


@register.filter
def logout_url(_):
    from django.urls import NoReverseMatch, reverse

    for name in ("logout", "auth_logout", "authentication:logout"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return "/account/logout/"
