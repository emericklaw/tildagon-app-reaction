# Reaction

A reaction-game, LED lights up and you touch the corresponding pad to
trigger it.

![Play](https://github.com/emericklaw/tildagon-app-reaction/blob/main/images/play.jpg?raw=true)

![Failed](https://github.com/emericklaw/tildagon-app-reaction/blob/main/images/failed.jpg?raw=true)

## Hardware requirement

Uses the 12 capacitive touch pads (`TOUCH01`-`TOUCH12`) from
`frontboards.twentysix`, which are only present on the **2026 frontboard**.
There's no fallback for older hardware — touch is the whole point of the
game.

Pad `N` sits at the same clockwise position as LED `N` on the badge's
12-LED ring (see `leds.PAD_TO_LED`), so the lit LED points at the pad to
touch — confirmed on real hardware. If a future frontboard revision
changes that, fix the mapping in `leds.py`.

## Modes

- **Survival** — endless rounds; touch the lit pad before a timeout that
  shrinks as your streak grows. 3 lives: a wrong touch or a timeout costs
  one. Best streak is saved.
- **Time Trial** — 10 timed rounds. A wrong touch adds a 200ms penalty to
  that round but doesn't pause the clock. Shows average/fastest/slowest at
  the end; best average is saved.
- **Simon Says** — each round adds one pad to a growing sequence, played
  back for you, which you then repeat by touching pads in order. Ends on
  the first wrong touch or a 2.5s pause mid-sequence. Best length reached
  is saved.

High scores for all three modes are visible from the main menu and persist
via the `settings` module (keys `reaction.best_streak`,
`reaction.best_avg_ms`, `reaction.best_sequence`).

## Controls

- Touch a pad to register it during a round.
- **CANCEL** exits the current round back to the main menu (progress for
  that round is lost); from the main menu it minimises the app.
- **CONFIRM** on the results screen returns to the main menu.
