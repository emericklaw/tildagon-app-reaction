import random
import utime

import settings

from .leds import LED_COUNT

TARGET_COLOR = (200, 220, 255)
SEQUENCE_COLOR = (255, 200, 60)
HIT_COLOR = (0, 255, 60)
WRONG_COLOR = (255, 30, 0)

HIT_FLASH_MS = 150
MISS_FLASH_MS = 250
WRONG_TOUCH_FLASH_MS = 120


def _random_pad(exclude=None):
    choices = [p for p in range(1, LED_COUNT + 1) if p != exclude]
    return random.choice(choices)


class ModeBase:
    """Shared timing/feedback plumbing for the three game modes below.

    Two independent kinds of visual feedback are needed:

    - A *blocking* flash (see _start_flash/_tick_flash) pauses on_touch
      handling for a moment before running a callback -- used whenever the
      round genuinely needs to pause before advancing (a correct hit, or a
      life-losing miss).
    - A *cosmetic* flash (see _mark_wrong) is purely visual and never blocks
      input -- used for wrong touches in modes where mashing the wrong pad
      shouldn't stall the round (e.g. Time Trial's clock keeps running).
    """

    def __init__(self):
        self.game_over = False
        self.result_lines = []

        self._flash_pad = None
        self._flash_color = None
        self._flash_until = 0
        self._flash_next = None

        self._wrong_pad = None
        self._wrong_until = 0

        self._hit_pad = None
        self._hit_until = 0

    def start(self):
        raise NotImplementedError

    def update(self):
        raise NotImplementedError

    def on_touch(self, pad_idx, now_ms):
        raise NotImplementedError

    def led_colors(self):
        raise NotImplementedError

    def hud_lines(self):
        raise NotImplementedError

    # ---- blocking flash ---------------------------------------------------

    def _start_flash(self, pad, color, duration_ms, then):
        self._flash_pad = pad
        self._flash_color = color
        self._flash_until = utime.ticks_add(utime.ticks_ms(), duration_ms)
        self._flash_next = then

    def _flash_active(self):
        return self._flash_next is not None

    def _tick_flash(self):
        if self._flash_next is not None and utime.ticks_diff(
            utime.ticks_ms(), self._flash_until
        ) >= 0:
            then = self._flash_next
            self._flash_pad = None
            self._flash_next = None
            then()

    # ---- cosmetic wrong-touch flash ---------------------------------------

    def _mark_wrong(self, pad):
        self._wrong_pad = pad
        self._wrong_until = utime.ticks_add(utime.ticks_ms(), WRONG_TOUCH_FLASH_MS)

    def _wrong_overlay(self):
        if self._wrong_pad is not None and utime.ticks_diff(
            utime.ticks_ms(), self._wrong_until
        ) < 0:
            return self._wrong_pad, WRONG_COLOR
        return None, None

    # ---- cosmetic mid-sequence-hit flash -----------------------------------

    def _mark_hit(self, pad, now_ms=None):
        if now_ms is None:
            now_ms = utime.ticks_ms()
        self._hit_pad = pad
        self._hit_until = utime.ticks_add(now_ms, WRONG_TOUCH_FLASH_MS)

    def _hit_overlay(self):
        if self._hit_pad is not None and utime.ticks_diff(
            utime.ticks_ms(), self._hit_until
        ) < 0:
            return self._hit_pad, HIT_COLOR
        return None, None

    def _base_colors(self):
        colors = {}
        wrong_pad, wrong_color = self._wrong_overlay()
        if wrong_pad is not None:
            colors[wrong_pad] = wrong_color
        hit_pad, hit_color = self._hit_overlay()
        if hit_pad is not None:
            colors[hit_pad] = hit_color
        if self._flash_pad is not None:
            colors[self._flash_pad] = self._flash_color
        return colors


class SurvivalMode(ModeBase):
    """Endless rounds. Touch the lit pad before the timeout, which shrinks
    as your streak grows. 3 lives; a wrong touch or a timeout costs one.
    """

    NAME = "Survival"
    LIVES = 3
    BASE_TIMEOUT_MS = 1500
    MIN_TIMEOUT_MS = 500
    TIMEOUT_STEP_MS = 40

    def start(self):
        self.lives = self.LIVES
        self.streak = 0
        self.timeout_ms = self.BASE_TIMEOUT_MS
        self.best_streak = settings.get("reaction.best_streak", 0)
        self.target_pad = None
        self.round_start = 0
        self._next_round()

    def _next_round(self):
        self.target_pad = _random_pad(exclude=self.target_pad)
        self.round_start = utime.ticks_ms()

    def update(self):
        self._tick_flash()
        if self.game_over or self._flash_active():
            return
        if utime.ticks_diff(utime.ticks_ms(), self.round_start) >= self.timeout_ms:
            self._miss(self.target_pad)

    def on_touch(self, pad_idx, now_ms):
        if self.game_over or self._flash_active():
            return
        if pad_idx == self.target_pad:
            self.streak += 1
            self.timeout_ms = max(
                self.MIN_TIMEOUT_MS, self.timeout_ms - self.TIMEOUT_STEP_MS
            )
            self._start_flash(pad_idx, HIT_COLOR, HIT_FLASH_MS, self._next_round)
        else:
            self._miss(pad_idx)

    def _miss(self, flash_pad):
        self.lives -= 1
        if self.lives <= 0:
            self._start_flash(flash_pad, WRONG_COLOR, MISS_FLASH_MS, self._end_game)
        else:
            self._start_flash(flash_pad, WRONG_COLOR, MISS_FLASH_MS, self._next_round)

    def _end_game(self):
        self.game_over = True
        if self.streak > self.best_streak:
            self.best_streak = self.streak
            settings.set("reaction.best_streak", self.best_streak)
            settings.save()
        self.result_lines = [
            "Streak: {}".format(self.streak),
            "Best: {}".format(self.best_streak),
        ]

    def led_colors(self):
        colors = {}
        if not self.game_over:
            colors[self.target_pad] = TARGET_COLOR
        colors.update(self._base_colors())
        return colors

    def hud_lines(self):
        return [
            "Lives: {}".format(self.lives),
            "Streak: {}  Best: {}".format(self.streak, self.best_streak),
            "Timeout: {}ms".format(self.timeout_ms),
        ]


class TimeTrialMode(ModeBase):
    """Fixed number of rounds, each timed. A wrong touch adds a time
    penalty for that round but doesn't stop the clock, so mashing pads
    can't game the benchmark.
    """

    NAME = "Time Trial"
    ROUNDS = 10
    WRONG_PENALTY_MS = 200

    def start(self):
        self.round_num = 0
        self.times = []
        self.penalty_ms = 0
        self.best_avg_ms = settings.get("reaction.best_avg_ms", None)
        self.target_pad = None
        self.round_start = 0
        self._next_round()

    def _next_round(self):
        self.round_num += 1
        self.penalty_ms = 0
        self.target_pad = _random_pad(exclude=self.target_pad)
        self.round_start = utime.ticks_ms()

    def update(self):
        # No per-round timeout in this mode -- rounds only advance on a
        # correct touch -- but _tick_flash() still needs to run every
        # frame to process the hit-flash-then-advance-round callback.
        self._tick_flash()

    def on_touch(self, pad_idx, now_ms):
        if self.game_over or self._flash_active():
            return
        if pad_idx == self.target_pad:
            elapsed = utime.ticks_diff(now_ms, self.round_start) + self.penalty_ms
            self.times.append(elapsed)
            if self.round_num >= self.ROUNDS:
                self._start_flash(pad_idx, HIT_COLOR, HIT_FLASH_MS, self._end_game)
            else:
                self._start_flash(pad_idx, HIT_COLOR, HIT_FLASH_MS, self._next_round)
        else:
            self.penalty_ms += self.WRONG_PENALTY_MS
            self._mark_wrong(pad_idx)

    def _end_game(self):
        self.game_over = True
        avg = sum(self.times) / len(self.times)
        if self.best_avg_ms is None or avg < self.best_avg_ms:
            settings.set("reaction.best_avg_ms", avg)
            settings.save()
            self.best_avg_ms = avg
        self.result_lines = [
            "Avg: {:.0f}ms  Best: {:.0f}ms".format(avg, self.best_avg_ms),
            "Fastest: {:.0f}ms".format(min(self.times)),
            "Slowest: {:.0f}ms".format(max(self.times)),
        ]

    def led_colors(self):
        colors = {}
        if not self.game_over:
            colors[self.target_pad] = TARGET_COLOR
        colors.update(self._base_colors())
        return colors

    def hud_lines(self):
        last = "Last: {:.0f}ms".format(self.times[-1]) if self.times else ""
        return [
            "Round {}/{}".format(min(self.round_num, self.ROUNDS), self.ROUNDS),
            last,
        ]


class SimonMode(ModeBase):
    """Simon-says: each round appends one pad to a growing sequence, played
    back for you, which you must then repeat by touching pads in order.
    """

    NAME = "Simon Says"
    FLASH_ON_MS = 380
    FLASH_GAP_MS = 140
    INPUT_TIMEOUT_MS = 2500

    def start(self):
        self.sequence = [_random_pad()]
        self.best_len = settings.get("reaction.best_sequence", 0)
        self.phase = "playback"
        self.playback_idx = 0
        self.playback_led_on = True
        self.playback_next_time = utime.ticks_add(utime.ticks_ms(), self.FLASH_ON_MS)
        self.input_idx = 0
        self.last_input_time = utime.ticks_ms()

    def _begin_playback(self):
        self.phase = "playback"
        self.playback_idx = 0
        self.playback_led_on = True
        self.playback_next_time = utime.ticks_add(utime.ticks_ms(), self.FLASH_ON_MS)

    def _begin_input(self):
        self.phase = "input"
        self.input_idx = 0
        self.last_input_time = utime.ticks_ms()

    def _grow_and_replay(self):
        self.sequence.append(_random_pad(exclude=self.sequence[-1]))
        self._begin_playback()

    def update(self):
        self._tick_flash()
        if self.game_over or self._flash_active():
            return
        now = utime.ticks_ms()
        if self.phase == "playback":
            if utime.ticks_diff(now, self.playback_next_time) >= 0:
                if self.playback_led_on:
                    self.playback_led_on = False
                    self.playback_next_time = utime.ticks_add(now, self.FLASH_GAP_MS)
                else:
                    self.playback_idx += 1
                    if self.playback_idx >= len(self.sequence):
                        self._begin_input()
                    else:
                        self.playback_led_on = True
                        self.playback_next_time = utime.ticks_add(
                            now, self.FLASH_ON_MS
                        )
        elif self.phase == "input":
            if utime.ticks_diff(now, self.last_input_time) > self.INPUT_TIMEOUT_MS:
                self._end_game()

    def on_touch(self, pad_idx, now_ms):
        if self.game_over or self._flash_active() or self.phase != "input":
            return
        self.last_input_time = now_ms
        if pad_idx == self.sequence[self.input_idx]:
            self.input_idx += 1
            if self.input_idx >= len(self.sequence):
                self._start_flash(
                    pad_idx, HIT_COLOR, HIT_FLASH_MS, self._grow_and_replay
                )
            else:
                self._mark_hit(pad_idx, now_ms)
        else:
            self._start_flash(pad_idx, WRONG_COLOR, MISS_FLASH_MS, self._end_game)

    def _end_game(self):
        self.game_over = True
        reached = len(self.sequence) - 1
        if reached > self.best_len:
            self.best_len = reached
            settings.set("reaction.best_sequence", self.best_len)
            settings.save()
        self.result_lines = [
            "Length: {}".format(reached),
            "Best: {}".format(self.best_len),
        ]

    def led_colors(self):
        colors = {}
        if not self.game_over and self.phase == "playback" and self.playback_led_on:
            colors[self.sequence[self.playback_idx]] = SEQUENCE_COLOR
        colors.update(self._base_colors())
        return colors

    def hud_lines(self):
        if self.phase == "playback":
            return ["Watch...", "Length: {}".format(len(self.sequence))]
        return [
            "Repeat it!",
            "{}/{}".format(self.input_idx, len(self.sequence)),
        ]


MODES = [SurvivalMode, TimeTrialMode, SimonMode]
