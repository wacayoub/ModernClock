# -*- coding: utf-8 -*-
"""Clock presentation helpers independent of the Enigma2 GUI."""
from __future__ import unicode_literals
from .core import clock_text

FONTS = [("modern", "Moderne"), ("bold", "Gras"), ("sport", "Sport italique"),
         ("mono", "Monospace"), ("digital", "Digitale (7 segments)")]


def display_values(now, style, seconds=False, twelve=False, date=True):
    values = clock_text(now, seconds, twelve, date)
    if style == "stacked":
        hours, minutes = values["time"].split(":")
        extra = (values["detail"] + " " + values["period"]).strip()
        values.update(time=hours, detail=minutes, period=extra)
    return values


def glyph_name(font, colour, opacity, character):
    name = "%s_%s_%02x.png" % (colour, opacity, ord(character))
    return name if font == "modern" else "%s/%s" % (font, name)


def preview_geometry(desktop, config_right):
    """Place the preview in the free column; never cover the settings list."""
    width, height = desktop
    scale = min(width / 1280.0, height / 720.0)
    margin = max(8, int(round(16 * scale)))
    left = max(int(round(width * .68)), int(config_right) + margin)
    panel_width = width - left - margin
    if panel_width < int(round(210 * scale)):
        return None
    top = int(round(height * .34))
    panel_height = min(int(round(390 * scale)), height - top - int(round(100 * scale)))
    inset = int(round(20 * scale))
    stage_y = int(round(60 * scale))
    stage_height = min(int(round(185 * scale)), panel_height - int(round(155 * scale)))
    return {"rect": (left, top, panel_width, panel_height), "scale": scale,
            "stage": (inset, stage_y, panel_width - 2 * inset, stage_height)}


def fit_preview(desktop, dimensions, stage):
    """Enlarge small clocks, fitting large or vertical clocks inside the panel."""
    factor = min(2.0, stage[2] * .88 / dimensions["width"], stage[3] * .88 / dimensions["height"])
    return tuple(max(1, int(round(value * factor))) for value in desktop)
