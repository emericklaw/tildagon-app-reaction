from math import cos, pi, radians, sin

import app
import settings
from app_components import Menu, clear_background
from events.input import Buttons, BUTTON_TYPES

from . import leds
from .modes import MODES
from .touch import TouchInput

APP_VERSION = "0.1.0"

MAIN_MENU_ITEMS = [mode.NAME for mode in MODES] + ["High Scores", "About"]
MODE_BY_NAME = {mode.NAME: mode for mode in MODES}

RING_RADIUS = 80
PAD_DOT_RADIUS = 10
IDLE_DOT_COLOR = (0.08, 0.08, 0.1)


def _pad_bearing(pad_idx):
    # Matches the physical LED ring convention
    # Pad 1 sits 15 degrees clockwise of true top,
    # each pad a further 30 degrees clockwise.
    return radians((pad_idx - 1) * 30 + 15)


class ReactionGame(app.App):
    def __init__(self):
        super().__init__()
        self.state = "menu"  # "menu" | "playing" | "results"
        self.menu = None
        self.current_menu = None
        self.mode = None

        self.button_states = Buttons(self)
        self._confirm_armed = True

        self.touch = TouchInput(self)
        self.touch.on_pad_touch = self._on_pad_touch
        self.touch.on_cancel = self._on_cancel

        self.set_menu("main")

    # ---- menu ---------------------------------------------------------

    def set_menu(self, name):
        self.current_menu = name
        if self.menu:
            self.menu._cleanup()
        if name == "main":
            self.menu = Menu(
                self,
                MAIN_MENU_ITEMS,
                select_handler=self.select_handler,
                back_handler=self.back_handler,
            )
        elif name == "high_scores":
            self.menu = Menu(
                self,
                self._high_score_lines(),
                back_handler=self.back_handler,
            )
        elif name == "about":
            self.menu = Menu(
                self,
                [
                    "Reaction",
                    "Version: {}".format(APP_VERSION),
                    "",
                    "Touch the lit pad!",
                    "CANCEL exits a round",
                    "",
                    "Needs 2026 frontboard",
                ],
                back_handler=self.back_handler,
            )

    def _high_score_lines(self):
        best_streak = settings.get("reaction.best_streak", 0)
        best_avg_ms = settings.get("reaction.best_avg_ms", None)
        best_len = settings.get("reaction.best_sequence", 0)
        avg_text = "{:.0f}ms".format(best_avg_ms) if best_avg_ms is not None else "-"
        return [
            "Survival: {}".format(best_streak),
            "Trial: {}".format(avg_text),
            "Simon Says: {}".format(best_len),
        ]

    def back_handler(self):
        if self.current_menu == "main":
            self.minimise()
        else:
            self.set_menu("main")

    def select_handler(self, item, idx):
        if self.current_menu == "main":
            if item == "High Scores":
                self.set_menu("high_scores")
            elif item == "About":
                self.set_menu("about")
            elif item in MODE_BY_NAME:
                self._start_mode(item)

    def _start_mode(self, name):
        if self.menu:
            self.menu._cleanup()
            self.menu = None
        self.mode = MODE_BY_NAME[name]()
        self.mode.start()
        self.state = "playing"

    # ---- touch/button routing ------------------------------------------

    def _on_pad_touch(self, pad_idx, now_ms):
        if self.state == "playing" and self.mode:
            self.mode.on_touch(pad_idx, now_ms)

    def _on_cancel(self):
        if self.state in ("playing", "results"):
            self._return_to_menu()

    def _return_to_menu(self):
        leds.clear()
        self.mode = None
        self.state = "menu"
        self.set_menu("main")

    # ---- update/draw ----------------------------------------------------

    def update(self, delta):
        if self.state == "playing":
            self.mode.update()
            leds.set_pads(self.mode.led_colors())
            if self.mode.game_over:
                self.state = "results"
                leds.clear()
        elif self.state == "results":
            pressed = self.button_states.get(BUTTON_TYPES["CONFIRM"])
            if pressed and self._confirm_armed:
                self._confirm_armed = False
                self.button_states.clear()
                self._return_to_menu()
            elif not pressed:
                self._confirm_armed = True
        elif self.menu:
            self.menu.update(delta)

    def draw(self, ctx):
        clear_background(ctx)
        if self.state == "menu":
            if self.menu:
                self.menu.draw(ctx)
        elif self.state == "playing":
            self._draw_ring(ctx, self.mode.led_colors())
            self._draw_lines(ctx, self.mode.hud_lines(), start_y=-20)
        elif self.state == "results":
            self._draw_ring(ctx, {})
            ctx.save()
            ctx.text_align = ctx.CENTER
            ctx.text_baseline = ctx.MIDDLE
            ctx.font_size = 16
            ctx.rgb(1, 1, 1).move_to(0, -40).text("Game Over")
            ctx.restore()
            self._draw_lines(ctx, self.mode.result_lines, start_y=-15)
            ctx.save()
            ctx.text_align = ctx.CENTER
            ctx.text_baseline = ctx.MIDDLE
            ctx.font_size = 11
            ctx.rgb(0.6, 0.6, 0.65).move_to(0, 60).text("CONFIRM: menu")
            ctx.restore()

    def _draw_ring(self, ctx, colors):
        ctx.save()
        for pad_idx in range(1, leds.LED_COUNT + 1):
            bearing = _pad_bearing(pad_idx)
            x = RING_RADIUS * sin(bearing)
            y = -RING_RADIUS * cos(bearing)
            color = colors.get(pad_idx)
            if color is not None:
                ctx.rgb(color[0] / 255, color[1] / 255, color[2] / 255)
            else:
                ctx.rgb(*IDLE_DOT_COLOR)
            ctx.arc(x, y, PAD_DOT_RADIUS, 0, 2 * pi, False).fill()
        ctx.restore()

    def _draw_lines(self, ctx, lines, start_y):
        ctx.save()
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.font_size = 14
        ctx.rgb(1, 1, 1)
        y = start_y
        for line in lines:
            if line:
                ctx.move_to(0, y).text(line)
            y += 18
        ctx.restore()


__app_export__ = ReactionGame
