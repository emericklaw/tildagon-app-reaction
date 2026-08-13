import utime

from events.input import ButtonDownEvent, BUTTON_TYPES
from frontboards.twentysix import TOUCH
from system.eventbus import eventbus

PAD_COUNT = 12
_PAD_KEYS = [(pad, "TOUCH{:02d}".format(pad)) for pad in range(1, PAD_COUNT + 1)]


class TouchInput:

    def __init__(self, owner):
        self.on_pad_touch = None  # callback(pad_idx, ticks_ms)
        self.on_cancel = None  # callback()
        eventbus.on(ButtonDownEvent, self._handle_down, owner)

    def _handle_down(self, event):
        now = utime.ticks_ms()
        if BUTTON_TYPES["CANCEL"] in event.button:
            if self.on_cancel:
                self.on_cancel()
            return
        if self.on_pad_touch is None:
            return
        for pad_idx, key in _PAD_KEYS:
            if TOUCH[key] in event.button:
                self.on_pad_touch(pad_idx, now)
                return
