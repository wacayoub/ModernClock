# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import localtime

from enigma import ePoint, eTimer, getDesktop
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import config, configfile, ConfigSubsection, ConfigYesNo, ConfigSelection, ConfigInteger, getConfigListEntry
from Screens.Screen import Screen
from Screens import Standby

from .core import clock_text, layout, position, normalized_position, overlay_skin

config.misc.modernclock = ConfigSubsection()
cfg = config.misc.modernclock
cfg.enabled = ConfigYesNo(default=True)
cfg.style = ConfigSelection(default="watermark", choices=[("watermark", "Filigrane TV (sans fond)"), ("signature", "Signature"), ("minimal", "Minimal"), ("compact", "Compact")])
cfg.size = ConfigSelection(default="small", choices=[("small", "Petite"), ("medium", "Moyenne"), ("large", "Grande")])
cfg.text_color = ConfigSelection(default="white", choices=[("white", "Blanc"), ("grey", "Gris clair"), ("yellow", "Jaune"), ("mint", "Menthe")])
cfg.text_opacity = ConfigSelection(default="35", choices=[("15", "15 % - Tres discret"), ("25", "25 % - Discret"), ("35", "35 % - Filigrane TV"), ("50", "50 %"), ("65", "65 %"), ("80", "80 %"), ("100", "100 % - Opaque")])
cfg.accent = ConfigSelection(default="mint", choices=[("mint", "Menthe"), ("blue", "Bleu glacier"), ("amber", "Ambre"), ("white", "Blanc")])
cfg.opacity = ConfigSelection(default="clear", choices=[("glass", "Verre"), ("solid", "Opaque"), ("light", "Discret"), ("clear", "Transparent")])
cfg.seconds = ConfigYesNo(default=False)
cfg.date = ConfigYesNo(default=False)
cfg.twelve = ConfigYesNo(default=False)
cfg.anchor = ConfigSelection(default="top_left", choices=[("top_right", "Haut droite"), ("top_left", "Haut gauche"), ("bottom_right", "Bas droite"), ("bottom_left", "Bas gauche"), ("custom", "Personnalisee")])
cfg.hide_menus = ConfigYesNo(default=True)
cfg.x = ConfigInteger(default=800, limits=(0, 1000))
cfg.y = ConfigInteger(default=50, limits=(0, 1000))
OPTIONS = ("enabled", "style", "size", "text_color", "text_opacity", "accent", "opacity", "seconds", "date", "twelve", "anchor", "hide_menus", "x", "y")
_controller = None


def desktop_size():
    size = getDesktop(0).size()
    return size.width(), size.height()


def appearance():
    return dict(style=cfg.style.value, size=cfg.size.value, seconds=cfg.seconds.value,
                twelve=cfg.twelve.value, date=cfg.date.value, accent=cfg.accent.value, opacity=cfg.opacity.value,
                text_color=cfg.text_color.value, text_opacity=cfg.text_opacity.value)


def connect_timer(timer, callback):
    # Older OE images expose timeout.connect instead of callback.append.
    if hasattr(timer, "callback"):
        timer.callback.append(callback)
        return None
    return timer.timeout.connect(callback)


class ModernClockOverlay(Screen):
    def __init__(self, session, preview=False):
        self.skin = overlay_skin(desktop_size(), preview=preview, **appearance())
        Screen.__init__(self, session)
        self.last_text = {}
        for name in ("time", "detail", "period", "date"):
            self[name] = Label("")
        self.onLayoutFinish.append(self.reposition)

    def dimensions(self):
        return layout(desktop_size(), cfg.style.value, cfg.size.value, cfg.seconds.value, cfg.twelve.value, cfg.date.value)

    def reposition(self):
        xy = position(desktop_size(), self.dimensions(), cfg.anchor.value, cfg.x.value, cfg.y.value)
        self.instance.move(ePoint(*xy))
        self.refresh()

    def refresh(self):
        values = clock_text(localtime(), cfg.seconds.value, cfg.twelve.value, cfg.date.value)
        for name, value in values.items():
            if value != self.last_text.get(name):
                self[name].setText(value)
        self.last_text = values


class ClockController(object):
    def __init__(self, session):
        self.session = session
        self.dialog = None
        self.suspended = False
        self.preview = False
        self.visible = None
        self.timer = eTimer()
        self.timer_connection = connect_timer(self.timer, self.tick)
        self.apply()

    def destroy_dialog(self):
        if self.dialog is not None:
            self.dialog.hide()
            self.session.deleteDialog(self.dialog)
            self.dialog = None
        self.visible = None

    def apply(self):
        self.timer.stop()
        self.destroy_dialog()
        if cfg.enabled.value or self.preview:
            self.dialog = self.session.instantiateDialog(ModernClockOverlay, preview=self.preview)
            self.tick()
            self.timer.start(1000, False)

    def should_show(self):
        if Standby.inStandby is not None:
            return False
        if self.preview:
            return True
        if self.suspended or not cfg.enabled.value:
            return False
        if cfg.hide_menus.value:
            from Components.ServiceEventTracker import InfoBarBase
            if not isinstance(self.session.current_dialog, InfoBarBase):
                return False
        return True

    def tick(self):
        if self.dialog is None:
            return
        visible = self.should_show()
        if visible != self.visible:
            if visible:
                self.dialog.show()
            else:
                self.dialog.hide()
            self.visible = visible
        if visible:
            self.dialog.refresh()

    def set_preview(self, enabled):
        self.preview = enabled
        self.apply()

    def stop(self):
        self.timer.stop()
        self.destroy_dialog()


class ClockPreview(Screen):
    def __init__(self, session, controller, move=False):
        width, height = desktop_size()
        scale = min(width / 1280.0, height / 720.0)
        bar = int(98 * scale)
        self.skin = '<screen position="0,0" size="%d,%d" flags="wfNoBorder" backgroundColor="#ff000000"><widget name="help" position="0,%d" size="%d,%d" font="Regular;%d" halign="center" valign="center" foregroundColor="#00F2F5FA" backgroundColor="#200D1421" /></screen>' % (width, height, height - bar, width, bar, max(12, int(21 * scale)))
        Screen.__init__(self, session)
        self.controller = controller
        self.move_mode = move
        self.step = 10
        self.original = (cfg.anchor.value, cfg.x.value, cfg.y.value)
        self.xy = None
        self.new_anchor = cfg.anchor.value
        self["help"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions"], {
            "ok": self.accept, "green": self.accept, "cancel": self.cancel, "red": self.cancel,
            "left": lambda: self.move(-1, 0), "right": lambda: self.move(1, 0),
            "up": lambda: self.move(0, -1), "down": lambda: self.move(0, 1),
            "blue": self.toggle_step, "yellow": self.reset_position,
        }, -2)
        self.onLayoutFinish.append(self.start_preview)
        self.onClose.append(self.end_preview)
        self.update_help()

    def update_help(self):
        self["help"].setText(("Fleches : deplacer  |  Bleu : pas %d px  |  Jaune : position initiale\nOK : garder la position  |  EXIT : annuler" % self.step) if self.move_mode else "Apercu sur la television\nOK / EXIT : revenir aux reglages")

    def start_preview(self):
        self.controller.set_preview(True)
        dialog = self.controller.dialog
        self.xy = position(desktop_size(), dialog.dimensions(), cfg.anchor.value, cfg.x.value, cfg.y.value)

    def end_preview(self):
        self.controller.set_preview(False)

    def move(self, dx, dy):
        if not self.move_mode or self.controller.dialog is None:
            return
        dialog = self.controller.dialog
        dims = dialog.dimensions()
        desktop = desktop_size()
        self.xy = tuple(max(0, min(desktop[i] - dims[("width", "height")[i]], self.xy[i] + delta * self.step)) for i, delta in enumerate((dx, dy)))
        self.new_anchor = "custom"
        dialog.instance.move(ePoint(*self.xy))

    def toggle_step(self):
        self.step = 1 if self.step == 10 else 10
        self.update_help()

    def reset_position(self):
        if self.move_mode:
            self.new_anchor = cfg.anchor.default
            self.xy = position(desktop_size(), self.controller.dialog.dimensions(), self.new_anchor)
            self.controller.dialog.instance.move(ePoint(*self.xy))

    def accept(self):
        if self.move_mode and self.xy is not None:
            cfg.anchor.value = self.new_anchor
            cfg.x.value, cfg.y.value = normalized_position(desktop_size(), self.controller.dialog.dimensions(), self.xy)
        self.close()

    def cancel(self):
        cfg.anchor.value, cfg.x.value, cfg.y.value = self.original
        self.close()


