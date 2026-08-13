from tildagonos import tildagonos

LED_COUNT = 12

# Physical LEDs are numbered 1-12 clockwise
PAD_TO_LED = {pad: pad for pad in range(1, LED_COUNT + 1)}

OFF = (0, 0, 0)


def clear():
    for pad in range(1, LED_COUNT + 1):
        tildagonos.leds[PAD_TO_LED[pad]] = OFF
    tildagonos.leds.write()


def set_pads(colors, default=OFF):
    """colors: {pad_idx: (r, g, b)}. Every pad not present is set to default."""
    for pad in range(1, LED_COUNT + 1):
        tildagonos.leds[PAD_TO_LED[pad]] = colors.get(pad, default)
    tildagonos.leds.write()
