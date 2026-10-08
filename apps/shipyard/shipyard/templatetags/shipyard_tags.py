from django import template

register = template.Library()


@register.simple_tag
def shipyard_logout_url():
    """Auth's logout address, whatever it is named in this version."""
    from django.urls import NoReverseMatch, reverse

    for name in ("logout", "auth_logout", "authentication:logout"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return "/account/logout/"


@register.simple_tag
def shipyard_logout_url():
    """Auth's logout address, whatever it is named in this version."""
    from django.urls import NoReverseMatch, reverse

    for name in ("logout", "auth_logout", "authentication:logout"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return "/account/logout/"


@register.filter
def remaining(delta):
    """A timedelta as '2h 13m' / '3d 4h'; 'done' once it has passed."""
    if delta is None:
        return "–"
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "done"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


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
    return f"{sign}{a:.{max(0, digits)}f}"


@register.filter
def isk_full(value):
    """Full ISK with thousands separators."""
    if value is None:
        return "–"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "–"


@register.filter
def pct(value, digits=1):
    if value is None:
        return "–"
    try:
        return f"{float(value) * 100:.{digits}f} %"
    except (TypeError, ValueError):
        return "–"


@register.filter
def num(value, digits=1):
    if value is None:
        return "–"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "–"
    if v == int(v) and digits == 0:
        return f"{int(v):,}"
    return f"{v:,.{digits}f}"


@register.filter
def duration(seconds):
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "–"
    if s <= 0:
        return "–"
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


@register.filter
def depth(value):
    """Market depth in days; None → '–', > 999 → '999+'."""
    if value is None:
        return "–"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "–"
    if v > 999:
        return "999+"
    return f"{v:.1f}"


@register.filter
def get_item(mapping, key):
    """{{ dict|get_item:key }}"""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def variant_label(value):
    from ..services.reprocessing import variant_label as _label
    return _label(value)


@register.filter
def area_label(value):
    from ..services.reprocessing import AREA_LABELS
    return AREA_LABELS.get(value, value)


@register.filter
def slug(value):
    import re
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


@register.filter
def profit_class(value):
    if value is None:
        return "text-muted"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    return "text-success fw-semibold" if v > 0 else "text-danger"
