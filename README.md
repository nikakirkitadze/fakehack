# fakehack

> A zero-dependency terminal **"you've been hacked"** prank screen — for your own screens and willing victims.

[![CI](https://github.com/nikakirkitadze/fakehack/actions/workflows/ci.yml/badge.svg)](https://github.com/nikakirkitadze/fakehack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-red.svg)](https://www.python.org/)

`fakehack` takes over your terminal with a glitching red banner, a fake Hollywood
hacker log, a climbing **ACCESS** bar, and a blinking warning. After a set
duration (or the first keypress) it flips to a big **GOTCHA** and restores your
terminal exactly as it was. It is **pure theater** — it reads nothing, changes
nothing, and talks to no network or device.

```
  [REC] NODE 0xC4-FF-19   ROOT SHELL   02:14:07



                    █   █   ███    ████  █   █  █████  ████
                    █   █  █   █  █      █  █   █      █   █
                    █████  █████  █      ███    ████   █   █
                    █   █  █   █  █      █  █   █      █   █
                    █   █  █   █   ████  █   █  █████  ████

            U N A U T H O R I Z E D   A C C E S S   D E T E C T E D

  > bypassing firewall ........ DONE
  > escalating privileges -> ROOT
  > injecting payload 'ghost.bin'
  > scanning filesystem ........ 4,192 files
  > locating credential vault ...
  > vault unlocked  OK
  > mirroring display buffer ..._

  ACCESS [███████████████████████████████████████████░░░░░░░░░░░░░░░░░]  73%
                     !!!  DO NOT POWER OFF THIS DEVICE  !!!
                                                             [ press any key ]
```

*(In a real terminal it's bright red, glitches, blinks, and scrolls. Fullscreen
your terminal first for the full effect.)*

## Please prank responsibly

This is a joke screen, nothing more. Even so:

- Run it on **your own** machines, or on a friend's **with their blessing** — and
  reveal the GOTCHA quickly. A good prank ends in a laugh, not a panic.
- Don't use it to intimidate, extort, or convince anyone that real damage was
  done. It isn't, and that's not funny.
- It does **not** hack anything. There is no exploit here and none is implied.

## Install

**With [pipx](https://pipx.pypa.io) (recommended — isolated, gives you a `fakehack` command):**

```bash
pipx install git+https://github.com/nikakirkitadze/fakehack
fakehack
```

**With pip:**

```bash
pip install git+https://github.com/nikakirkitadze/fakehack
fakehack
```

**No install — it's a single file with no dependencies:**

```bash
curl -fsSLO https://raw.githubusercontent.com/nikakirkitadze/fakehack/main/fakehack.py
python3 fakehack.py
```

Requires **Python 3.8+**. Works on macOS and Linux; on Windows the animation runs
but the "press any key" early-exit needs a Unix terminal.

## Usage

```bash
fakehack                       # 15s HACKED takeover, then GOTCHA
fakehack -d 30                 # run for 30 seconds
fakehack --word PWNED          # change the big banner word
fakehack --target LAPTOP-07    # name shown in the fake log
fakehack --message "got you!"  # custom line under the reveal
fakehack --no-reveal           # skip GOTCHA, just restore when done
fakehack --selftest            # print one static frame and exit (no takeover)
```

| Flag | Default | What it does |
| --- | --- | --- |
| `-d`, `--duration` | `15` | Seconds to show the hacked screen before the reveal. |
| `-w`, `--word` | `HACKED` | The big block-letter banner word (A–Z, 0–9). |
| `-t`, `--target` | `DEVICE-07` | Fake victim name woven into the log. |
| `-m`, `--message` | `you just got pranked :)` | Line shown under the GOTCHA reveal. |
| `--fps` | `16` | Animation frames per second (4–60). |
| `--no-reveal` | off | Skip the GOTCHA reveal; just restore the terminal. |
| `--selftest` | off | Render one static frame to stdout and exit — handy for CI or a screenshot. |
| `--version` | | Print version and exit. |

Press **any key** at any time to cut to the reveal early.

## Driving it from a script or an AI agent

`fakehack` is safe to automate: it auto-exits after `--duration` and **always
restores the terminal** — alternate screen buffer, cursor, and colors — on normal
exit, `Ctrl-C`, or an error. So an assistant can "temporarily show the hacked
screen" with a bounded, self-cleaning command:

```bash
fakehack --duration 20 --target "$(hostname)"
```

If stdout isn't a TTY (piped or captured), it refuses to animate and tells you so,
instead of dumping escape codes — use `--selftest` to preview a frame in that case.

## How it works

- **Alternate screen buffer** (`\033[?1049h`) so the takeover never scrolls away
  your real shell history, restored on exit.
- An **ANSI-safe cell compositor**: every frame is built as a grid of
  *(character, color)* cells and serialized once, so overlapping layers (the
  glitch "ghost", the banner, the log) never corrupt each other's escape codes.
- A tiny hand-made **5-row block font** renders the banner for any A–Z / 0–9 word.
- Truecolor (24-bit) ANSI for the red palette; graceful fallback to an 80×24
  layout when the terminal size can't be read.

No dependencies, one file, ~400 lines of standard-library Python.

## Contributing

Issues and PRs welcome — new banner glyphs, extra log flavor, Windows key-input
support, color themes. Keep it dependency-free and keep `--selftest` passing
(that's what CI checks).

## License

[MIT](LICENSE) © 2026 Nika Kirkitadze
