# -*- coding: utf-8 -*-
"""Live side preview for the native Date/time screen, without input hooks."""
from __future__ import unicode_literals

import json
from enigma import ePoint, eTimer
from xml.etree import ElementTree as ET
from Components.Label import Label
from Screens.Screen import Screen
from . import runtime
from .core import layout
from .design import preview_geometry, fit_preview
from .glyphs import NativeClockOverlay


class PreviewPanel(NativeClockOverlay):
    def __init__(self, session, geometry):
        self.geometry = geometry
        desktop = runtime.desktop_size()
        cfg = runtime.cfg
        dims = layout(desktop, cfg.style.value, cfg.size.value, cfg.seconds.value, cfg.twelve.value, cfg.date.value)
        NativeClockOverlay.__init__(self, session, preview=True,
                                    render_desktop=fit_preview(desktop, dims, geometry["stage"]))
        for name in ("title", "font", "style", "opacity", "hint"):
            self[name] = Label("")
        self["title"].setText("APERÇU EN DIRECT")
        # This preview and its backdrop share one window: transparent glyphs
        # must blend into the stage, rather than cut through to the TV plane.
        self.onLayoutFinish.remove(self.reposition)

    def compose_skin(self, tree):
        geometry = self.geometry
        x, y, width, height = geometry["rect"]
        scale = geometry["scale"]
        sx, sy, sw, sh = geometry["stage"]
        def n(value):
            return max(1, int(round(value * scale)))
        parts = ['<screen name="ModernClockSidePreview" position="%d,%d" size="%d,%d" flags="wfNoBorder" zPosition="20" backgroundColor="#0010202C">' % (x, y, width, height)]
        parts.append('<eLabel position="0,0" size="%d,%d" backgroundColor="#0068E0BE" />' % (n(3), height))
        parts.append('<eLabel position="%d,%d" size="%d,%d" backgroundColor="#00283D55" />' % (sx, sy, sw // 2, sh))
        parts.append('<eLabel position="%d,%d" size="%d,%d" backgroundColor="#00818E9D" />' % (sx + sw // 2, sy, sw - sw // 2, sh))
        fields = [("title", n(14), n(34), 22, "68E0BE"),
                  ("font", sy + sh + n(17), n(27), 18, "F2F5FA"),
                  ("style", sy + sh + n(45), n(27), 18, "F2F5FA"),
                  ("opacity", sy + sh + n(76), n(25), 16, "B8C8D8"),
                  ("hint", sy + sh + n(109), n(20), 14, "A4B6C9")]
        for name, yy, hh, font, colour in fields:
            parts.append('<widget name="%s" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#00%s" backgroundColor="#0010202C" transparent="1" valign="center" noWrap="1" />' % (name, sx, yy, sw, hh, n(font), colour))
        parts.append('</screen>')
        panel = ET.fromstring("".join(parts))
        dims = self.dimensions()
        dx, dy = sx + (sw - dims["width"]) // 2, sy + (sh - dims["height"]) // 2
        glyphs = list(tree)
        tree.attrib.clear()
        tree.attrib.update(panel.attrib)
        tree[:] = list(panel)
        for glyph in glyphs:
            gx, gy = [int(value) for value in glyph.attrib["position"].split(",")]
            glyph.set("position", "%d,%d" % (gx + dx, gy + dy))
            glyph.set("zPosition", "2")
            tree.append(glyph)

    def update_labels(self):
        cfg = runtime.cfg
        self["font"].setText("Police : " + cfg.font.getText())
        self["style"].setText("Style : " + cfg.style.getText())
        self["opacity"].setText("Opacité %s %% / transparence %d %%" % (cfg.text_opacity.value, 100 - int(cfg.text_opacity.value)))
        self["hint"].setText("Bleu : voir la taille réelle sur la TV" if cfg.enabled.value else "Horloge désactivée - aperçu uniquement")


class RightPreview(object):
    def __init__(self, screen):
        self.screen = screen
        self.session = screen.session
        self.geometry = None
        self.panel = None
        self.signature = None
        self.active = False
        self.visible = False
        self.closed = False
        self.timer = eTimer()
        self.connection = runtime.connect_timer(self.timer, self.tick)
        screen.onLayoutFinish.append(self.prepare)
        screen.onExecBegin.append(self.resume)
        screen.onExecEnd.append(self.pause)
        screen.onClose.append(self.stop)

    def prepare(self):
        desktop = runtime.desktop_size()
        config = self.screen["config"].instance
        right = self.screen.instance.position().x() + config.position().x() + config.size().width()
        self.geometry = preview_geometry(desktop, right)

    def resume(self):
        if self.closed:
            return
        self.active = True
        if self.geometry is not None:
            self.tick()
            self.timer.start(400, False)

    def pause(self):
        self.active = False
        self.timer.stop()
        for dialog in (self.panel,):
            if dialog is not None:
                dialog.hide()
        self.visible = False
        self.write_status()

    def tick(self):
        if self.closed or not self.active or self.geometry is None:
            return
        cfg = runtime.cfg
        signature = tuple(getattr(cfg, key).value for key in ("font", "style", "size", "text_color", "text_opacity", "seconds", "date", "twelve", "enabled"))
        if signature != self.signature:
            if self.panel is not None:
                self.panel.hide()
                self.session.deleteDialog(self.panel)
            self.panel = self.session.instantiateDialog(PreviewPanel, self.geometry)
            self.panel.update_labels()
            self.signature = signature
            self.visible = False
        if not self.visible:
            self.panel.show()
            self.visible = True
            self.write_status()
        self.panel.refresh()

    def write_status(self):
        cfg = runtime.cfg
        try:
            with open("/tmp/modern-clock-side-preview.json", "w") as output:
                json.dump({"visible": self.visible, "font": cfg.font.value, "style": cfg.style.value,
                           "opacity": cfg.text_opacity.value, "rect": self.geometry["rect"] if self.geometry else None}, output)
        except (IOError, OSError):
            pass

    def stop(self):
        if self.closed:
            return
        self.pause()
        self.closed = True
        for dialog in (self.panel,):
            if dialog is not None:
                self.session.deleteDialog(dialog)
        self.panel = None
        if hasattr(self.timer, "callback") and self.tick in self.timer.callback:
            self.timer.callback.remove(self.tick)
        self.connection = None
