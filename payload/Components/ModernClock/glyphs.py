# -*- coding: utf-8 -*-
"""Pixmap glyphs preserve per-pixel opacity on images ignoring text alpha."""
from __future__ import unicode_literals
from os.path import dirname, join
from time import localtime
from xml.etree import ElementTree as ET

from Components.Pixmap import Pixmap
from Screens.Screen import Screen
from . import runtime
from .core import overlay_skin, text_colour, layout, ACCENTS
from .design import display_values, glyph_name

OriginalOverlay = runtime.ModernClockOverlay


class NativeClockOverlay(OriginalOverlay):
    def __init__(self, session, preview=False, render_desktop=None):
        self.render_desktop = render_desktop or runtime.desktop_size()
        tree = ET.fromstring(overlay_skin(self.render_desktop, preview=preview, **runtime.appearance()))
        self.slots = {}
        for widget in list(tree):
            if widget.tag != "widget":
                if widget.tag == "eLabel":
                    widget.set("backgroundColor", text_colour(ACCENTS.get(runtime.cfg.accent.value, ACCENTS["mint"]), runtime.cfg.text_opacity.value))
                continue
            tree.remove(widget)
            name = widget.attrib["name"]
            x, y = [int(value) for value in widget.attrib["position"].split(",")]
            width, height = [int(value) for value in widget.attrib["size"].split(",")]
            font = int(widget.attrib["font"].split(";")[1])
            count = {"time": 2 if runtime.cfg.style.value == "stacked" else 5, "detail": 2, "period": 5, "date": 12}[name]
            char_width = max(1, int(round(font * 0.64)))
            char_height = max(1, int(round(font * 1.32)))
            self.slots[name] = []
            for index in range(count):
                slot = "%s_%d" % (name, index)
                self.slots[name].append(slot)
                # Hidden fields are represented by blank pixmaps, inside bounds.
                sx = x + index * char_width if width > 1 else 0
                sy = y + max(0, (height - char_height) // 2) if height > 1 else 0
                ET.SubElement(tree, "widget", {"name": slot, "position": "%d,%d" % (sx, sy),
                    "size": "%d,%d" % ((char_width, char_height) if width > 1 else (1, 1)),
                    "alphatest": "blend", "scale": "1", "transparent": "1"})
        self.compose_skin(tree)
        self.skin = ET.tostring(tree, encoding="unicode")
        Screen.__init__(self, session)
        self.last_text = {}
        for slots in self.slots.values():
            for name in slots:
                self[name] = Pixmap()
        self.onLayoutFinish.append(self.reposition)

    def compose_skin(self, tree):
        """Allow a preview to paint its backdrop in the same GUI window."""
        pass

    def dimensions(self):
        cfg = runtime.cfg
        return layout(self.render_desktop, cfg.style.value, cfg.size.value, cfg.seconds.value, cfg.twelve.value, cfg.date.value)

    def refresh(self):
        cfg = runtime.cfg
        values = display_values(localtime(), cfg.style.value, cfg.seconds.value, cfg.twelve.value, cfg.date.value)
        for field, value in values.items():
            if value == self.last_text.get(field):
                continue
            for index, slot in enumerate(self.slots[field]):
                character = value[index] if index < len(value) else " "
                path = join(dirname(__file__), "glyphs", glyph_name(cfg.font.value, cfg.text_color.value, cfg.text_opacity.value, character))
                self[slot].instance.setPixmapFromFile(path)
        self.last_text = values
