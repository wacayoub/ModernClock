# -*- coding: utf-8 -*-
"""Date/time screen integration. No plugin registration."""
from __future__ import unicode_literals

import json

from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.config import ConfigSelection
from . import runtime
from .glyphs import NativeClockOverlay
from .design import FONTS
from .right_preview import RightPreview

runtime.ModernClockOverlay = NativeClockOverlay

cfg = runtime.cfg
cfg.font = ConfigSelection(default="modern", choices=FONTS)
cfg.style.setChoices([("watermark", "Filigrane TV"), ("minimal", "Minimal"),
                      ("compact", "Compact"), ("signature", "Signature"),
                      ("stacked", "Verticale HH / MM")], default="watermark")


class TransparencyView(ConfigSelection):
    """Two views of one preference; no mutually-triggering change callbacks."""
    def __init__(self, opacity):
        self.opacity = opacity
        self._view_ready = False
        ConfigSelection.__init__(self, default="65", choices=[(str(100 - int(value)), "%d %%" % (100 - int(value))) for value in ("100", "80", "65", "50", "35", "25", "15")])
        self._view_ready = True

    def getValue(self):
        return str(100 - int(self.opacity.value))

    def setValue(self, value):
        if self._view_ready:
            self.opacity.value = str(100 - int(value))
        else:
            self._value = value

    value = property(getValue, setValue)

    def getText(self):
        return "%s %%" % self.getValue()

    def getMulti(self, selected):
        # ConfigSelection caches _descr; this derived view must stay dynamic.
        return ("text", self.getText())

    def isChanged(self):
        return self.opacity.isChanged()

    def save(self):
        self.saved_value = None

    def load(self):
        pass

    def cancel(self):
        # Setup also includes the canonical opacity entry and cancels it.
        pass


cfg.text_transparency = TransparencyView(cfg.text_opacity)


def start(session):
    if runtime._controller is None:
        runtime._controller = runtime.ClockController(session)
        if hasattr(session, "onShutdown"):
            session.onShutdown.append(runtime._controller.stop)
        status("started")
    return runtime._controller


def status(event):
    try:
        with open("/tmp/modern-clock-native.json", "w") as output:
            json.dump({"event": event, "enabled": cfg.enabled.value, "opacity": cfg.text_opacity.value,
                       "transparency": cfg.text_transparency.value, "anchor": cfg.anchor.value,
                       "font": cfg.font.value, "style": cfg.style.value,
                       "desktop": runtime.desktop_size()}, output)
    except (IOError, OSError):
        pass


def attach(screen):
    """Keep normal time-zone/NTP options and add positioning on the blue key."""
    controller = start(screen.session)
    controller.suspended = True
    controller.tick()

    def saved():
        # Coordinates are changed in the placement dialog, outside Setup's list.
        cfg.x.save()
        cfg.y.save()
        cfg.text_transparency.save()
        status("saved-in-time-settings")

    def closed():
        # Saving updated saved_value above; cancelling reverts the coordinates.
        cfg.x.cancel()
        cfg.y.cancel()
        controller.suspended = False
        controller.apply()

    def positioned(*args):
        screen["config"].invalidateCurrent()

    def position_clock():
        screen.session.openWithCallback(positioned, runtime.ClockPreview, controller, move=True)

    screen["key_blue"] = StaticText("Position horloge")
    screen["modernClockPositionActions"] = ActionMap(["ColorActions"], {"blue": position_clock}, -2)
    screen.addSaveNotifier(saved)
    screen.onClose.append(closed)
    screen.modernClockRightPreview = RightPreview(screen)
    status("time-settings-attached")
