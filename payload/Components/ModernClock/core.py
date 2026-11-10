# -*- coding: utf-8 -*-
"""Portable layout and time formatting. No Enigma2 imports."""
from __future__ import unicode_literals

from xml.sax.saxutils import escape

ACCENTS = {"mint": "68E0BE", "blue": "79B8FF", "amber": "F4CA83", "white": "F2F5FA"}
TEXT_COLOURS = {"white": "F2F5FA", "grey": "B8C0CA", "yellow": "FFE272", "mint": "68E0BE"}
WEEKDAYS = ("LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM")
MONTHS = ("JAN", "FEV", "MAR", "AVR", "MAI", "JUIN", "JUIL", "AOUT", "SEP", "OCT", "NOV", "DEC")


def clock_text(now, seconds=False, twelve=False, date=True):
    hour = now.tm_hour
    period = ("PM" if hour >= 12 else "AM") if twelve else ""
    if twelve:
        hour = hour % 12 or 12
    return {
        "time": "%02d:%02d" % (hour, now.tm_min),
        "detail": ("%02d" % now.tm_sec) if seconds else period,
        "period": period if seconds else "",
        "date": ("%s %02d %s" % (WEEKDAYS[now.tm_wday], now.tm_mday, MONTHS[now.tm_mon - 1])) if date else "",
    }


def layout(desktop, style="signature", size="medium", seconds=False, twelve=False, date=True):
    scale = min(desktop[0] / 1280.0, desktop[1] / 720.0)
    scale *= {"small": 0.8, "medium": 1.0, "large": 1.3}.get(size, 1.0)
    has_detail = seconds or twelve
    width = 240 if has_detail else 204
    height = 126 if date else 94
    if style == "stacked":
        width, height = 100, (150 if date else 124)
        time_box = (8, 0, 80, 51, 42)
        detail_box = (8, 49, 80, 51, 42)
        date_box = (10, 129, 80, 18, 10)
    elif style == "watermark":
        width, height = (124 if has_detail else 88), (60 if date else (38 if seconds and twelve else 34))
        time_box = (2, 0, 80, 32, 22)
        detail_box = (86, 8, 36, 20, 15)
        date_box = (2, 37, width - 4, 20, 12)
    elif style == "compact":
        width, height = (202 if has_detail else 166), (84 if date else 58)
        time_box = (16, 7, 132, 45, 36)
        detail_box = (150, 19, 44, 28, 19)
        date_box = (16, 55, width - 28, 21, 15)
    else:
        time_box = (20, 19, 162, 60, 46)
        detail_box = (184, 34, 47, 30, 23)
        date_box = (22, 88, width - 38, 24, 17)
    if not has_detail and style != "stacked":
        detail_box = (0, 0, 1, 1, 1)
    if not date:
        date_box = (0, 0, 1, 1, 1)
    period_box = {"watermark": (86, 27, 36, 10, 8), "compact": (150, 42, 44, 13, 10)}.get(style, (184, 65, 45, 18, 12)) if seconds and twelve else (0, 0, 1, 1, 1)
    if style == "stacked":
        period_box = (10, 104, 80, 17, 12) if has_detail else (0, 0, 1, 1, 1)
    def scaled(values):
        return tuple(max(1, int(round(v * scale))) if i >= 2 else int(round(v * scale)) for i, v in enumerate(values))
    return {
        "width": max(1, int(round(width * scale))),
        "height": max(1, int(round(height * scale))),
        "time": scaled(time_box), "detail": scaled(detail_box),
        "date": scaled(date_box), "period": scaled(period_box),
        "scale": scale,
        "margin": (18, 2) if style == "watermark" else (36, 36),
    }


def position(desktop, dimensions, anchor="top_right", x=800, y=50):
    max_x = max(0, desktop[0] - dimensions["width"])
    max_y = max(0, desktop[1] - dimensions["height"])
    desktop_scale = min(desktop[0] / 1280.0, desktop[1] / 720.0)
    margin_x, margin_y = (int(round(value * desktop_scale)) for value in dimensions.get("margin", (36, 36)))
    if anchor == "custom":
        px, py = round(max_x * x / 1000.0), round(max_y * y / 1000.0)
    else:
        px = max_x - margin_x if anchor.endswith("right") else margin_x
        py = max_y - margin_y if anchor.startswith("bottom") else margin_y
    return int(max(0, min(max_x, px))), int(max(0, min(max_y, py)))


def normalized_position(desktop, dimensions, xy):
    return tuple(int(round(max(0, min(1, xy[i] / float(max(1, desktop[i] - dimensions[("width", "height")[i]])))) * 1000)) for i in (0, 1))


def text_colour(rgb, opacity):
    """Enigma2 uses inverse alpha: 00 is opaque, FF is transparent."""
    opacity = max(0, min(100, int(opacity)))
    alpha = int(round((100 - opacity) * 255 / 100.0))
    return "#%02X%s" % (alpha, rgb)


def overlay_skin(desktop, style="signature", size="medium", seconds=False, twelve=False, date=True, accent="mint", opacity="glass", preview=False, text_color="white", text_opacity="100"):
    dims = layout(desktop, style, size, seconds, twelve, date)
    width, height = dims["width"], dims["height"]
    colour = "#00" + ACCENTS.get(accent, ACCENTS["mint"])
    background = {"solid": "#000D1723", "glass": "#400D1723", "light": "#900D1723", "clear": "#ff000000"}.get(opacity, "#400D1723")
    if style in ("minimal", "watermark", "stacked"):
        background = "#ff000000"
    parts = ['<screen name="ModernClockOverlay" position="0,0" size="%d,%d" flags="wfNoBorder" zPosition="%d" backgroundColor="%s">' % (width, height, 30 if preview else -1, background)]
    if style not in ("minimal", "watermark", "stacked"):
        line = max(2, int(round(3 * dims["scale"])))
        parts.append('<eLabel position="0,0" size="%d,%d" backgroundColor="%s" />' % (line, height, colour))
    for name in ("time", "detail", "date", "period"):
        x, y, w, h, font = dims[name]
        rgb = TEXT_COLOURS.get(text_color, TEXT_COLOURS["white"]) if name == "time" or style == "watermark" else (colour[3:] if name == "detail" else "B7C4D4")
        foreground = text_colour(rgb, text_opacity)
        shadow = '' if style == "watermark" else ' shadowColor="%s" shadowOffset="1,1"' % text_colour("101925", text_opacity)
        parts.append('<widget name="%s" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" backgroundColor="%s" transparent="1" noWrap="1" valign="center"%s />' % (name, x, y, w, h, font, foreground, background, shadow))
    parts.append('</screen>')
    return "".join(parts)


def settings_skin(desktop):
    scale = min(desktop[0] / 1280.0, desktop[1] / 720.0)
    def n(value):
        return max(1, int(round(value * scale)))
    parts = ['<screen name="ModernClockSetup" position="center,center" size="%d,%d" title="Modern Clock" flags="wfNoBorder" backgroundColor="#000D1421">' % (n(1160), n(650))]
    def text(x, y, w, h, value, font=22, colour="F2F5FA"):
        parts.append('<eLabel position="%d,%d" size="%d,%d" text="%s" font="Regular;%d" foregroundColor="#00%s" backgroundColor="#000D1421" transparent="1" valign="center" />' % (n(x), n(y), n(w), n(h), escape(value, {'"': '&quot;'}), n(font), colour))
    text(38, 30, 480, 28, "M O D E R N   C L O C K", 18, "68E0BE")
    text(38, 70, 440, 62, "Le temps, simplement.", 34)
    text(38, 148, 410, 75, "Petite, sans fond, semi-transparente.\nComme un filigrane de chaine TV.", 21, "A8B8CC")
    text(38, 290, 390, 94, "20:48", 72)
    text(42, 392, 380, 30, "FILIGRANE TV", 20, "68E0BE")
    text(38, 480, 390, 68, "Opacite des chiffres : 15 a 100 %\nPosition libre a la telecommande", 18, "A8B8CC")
    text(504, 32, 610, 36, "PERSONNALISATION", 18, "A8B8CC")
    parts.append('<widget name="config" position="%d,%d" size="%d,%d" font="Regular;%d" itemHeight="%d" scrollbarMode="showOnDemand" backgroundColor="#000D1421" foregroundColor="#00F2F5FA" selectionBackgroundColor="#00243748" selectionForegroundColor="#0068E0BE" />' % (n(496), n(88), n(626), n(440), n(21), n(40)))
    text(504, 535, 610, 30, "Gauche / droite : modifier   |   Haut / bas : choisir", 16, "A8B8CC")
    for x, colour, label in ((38, "E7818D", "Annuler"), (312, "68E0BE", "Enregistrer"), (586, "F4CA83", "Apercu TV"), (860, "79B8FF", "Positionner")):
        parts.append('<eLabel position="%d,%d" size="%d,%d" backgroundColor="#00%s" />' % (n(x), n(598), n(5), n(23), colour))
        text(x + 17, 591, 240, 36, label, 20)
    parts.append('</screen>')
    return "".join(parts)
