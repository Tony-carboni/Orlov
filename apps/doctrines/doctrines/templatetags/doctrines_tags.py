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
def isk_auto(value):
    """ISK with the decimals the size allows (the owner's rule, as on the Shipyard's reprocessing tab):
    under 10 k two decimals ('1.23 k'), from 10 k one ('12.3 k'), from 100 k none ('154 k'),
    millions three ('2.850 M'); None → '–'."""
    try:
        a = abs(float(value))
    except (TypeError, ValueError):
        return "–"
    return isk(value, 3 if a >= 1e6 else 0 if a >= 1e5 else 1 if a >= 1e4 else 2)


@register.filter
def isk_full(value):
    if value is None:
        return "–"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "–"


KEYWORD_SEPARATORS = (" - ", " – ", " — ", ": ")
KEYWORD_MAX = 24  # a longer "keyword" is a sentence with a colon in it, not a label


def split_keyword(line):
    """'DPS: the damage dealers' -> ('DPS', 'the damage dealers'); a plain line -> ('', line)."""
    for sep in KEYWORD_SEPARATORS:
        if sep in line:
            key, desc = line.split(sep, 1)
            key, desc = key.strip(), desc.strip()
            if key and desc and len(key) <= KEYWORD_MAX:
                return key, desc
            break
    return "", line


def tag_html(keyword):
    """The keyword as a tag: a role gets its icon and colour (data-role), anything else the neutral look."""
    from ..services.fittings import ROLE_ICONS, role_key

    key = role_key(keyword)
    icon = ROLE_ICONS.get(keyword.strip().lower(), "")
    icon_html = f'<i class="fas {icon} fa-fw" aria-hidden="true"></i>' if icon else ""
    return f'<span class="doctrines-tag" data-role="{key}">{icon_html}{escape(keyword)}</span>'


def item_html(item):
    key, desc = split_keyword(item)
    if not key:
        return f"<li>{escape(item)}</li>"
    return f'<li class="doctrines-kv">{tag_html(key)}<span class="doctrines-kv-text">{escape(desc)}</span></li>'


@register.filter
def paragraphs(text):
    """Plain text to HTML: a blank line starts a paragraph, lines starting with '- ' make a list, and a list
    line written as 'Keyword: explanation' shows the keyword as a tag (coloured when it is a fleet role)."""
    out, para, items = [], [], []

    def flush():
        nonlocal para, items
        if items:
            cls = ' class="doctrines-kv-list"' if any(split_keyword(i)[0] for i in items) else ""
            out.append(f"<ul{cls}>" + "".join(item_html(i) for i in items) + "</ul>")
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
def keyed(text):
    """Pros and cons as (keyword, description) per line: 'King of the hill - holds a point' → ('King of the hill',
    'holds a point'). A line without a separator (' - ', ' – ', ' — ' or ': ') is all description."""
    out = []
    for ln in lines(text):
        for sep in (" - ", " – ", " — ", ": "):
            if sep in ln:
                key, desc = ln.split(sep, 1)
                out.append((key.strip(), desc.strip()))
                break
        else:
            out.append(("", ln))
    return out


@register.filter
def ratios(text):
    """The doctrine's composition as [(role, number, icon, key)] from 'Role: number' lines."""
    from ..services.fittings import ROLE_ICONS, role_key

    out = []
    for key, value in keyed(text):
        if not key:
            continue
        try:
            n = int(value.strip().rstrip("x× ").strip())
        except ValueError:
            continue
        out.append((key, n, ROLE_ICONS.get(key.strip().lower(), "fa-user-group"), role_key(key)))
    return out


@register.filter
def ratio_total(parts):
    """The pilots in one unit of the composition: the sum of the numbers from ratios()."""
    return sum(n for _, n, _, _ in parts)


@register.filter
def ratio_words(parts):
    """'6 DPS, 2 Logistics, 1 Tackle and 1 Support' for the hover text."""
    words = [f"{n} {role}" for role, n, _, _ in parts]
    return ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)


@register.filter
def logout_url(_):
    from django.urls import NoReverseMatch, reverse

    for name in ("logout", "auth_logout", "authentication:logout"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return "/account/logout/"
