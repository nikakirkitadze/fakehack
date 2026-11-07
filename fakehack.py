#!/usr/bin/env python3
"""
fakehack — a terminal "you've been hacked" prank screen.

A zero-dependency (stdlib only) full-screen terminal takeover: a glitching
red banner, a fake Hollywood hacker log, a climbing ACCESS bar, and a blinking
warning. Runs for a set duration (or until a keypress), then flips to a big
GOTCHA reveal and restores your terminal exactly as it was.

Designed to be safe to hand to an agent: `fakehack --duration 20` takes over,
auto-exits, and always restores the terminal (alt screen, cursor, colors) even
on Ctrl-C or error. It is pure theater — it does nothing to any device.

Examples:
  fakehack                      # default 15s HACKED takeover, then GOTCHA
  fakehack -d 30                # run for 30 seconds
  fakehack --word PWNED         # change the big banner word
  fakehack --target LAPTOP-07   # name shown in the fake log
  fakehack --message "got you!" # custom reveal line
  fakehack --no-reveal          # skip the GOTCHA screen, just restore
  fakehack --selftest           # print one static frame (no takeover) and exit
"""

import argparse
import os
import random
import signal
import sys
import time

# ---------------------------------------------------------------- colors ----
def rgb(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

RED      = rgb(255, 45, 45)
RED_HOT  = rgb(255, 106, 106)
BLOOD    = rgb(139, 0, 0)
DIM      = rgb(120, 14, 14)
YELLOW   = rgb(255, 210, 61)
CYAN     = rgb(25, 255, 230)   # a whisper of chromatic glitch
WHITE    = rgb(235, 235, 235)
RESET    = "\033[0m"
BOLD     = "\033[1m"

# ------------------------------------------------------------- block font ----
# 5 rows tall. '#' marks a lit cell; rendered with full blocks.
FONT = {
    " ": ["   "] * 5,
    "!": ["#", "#", "#", " ", "#"],
    ".": [" ", " ", " ", " ", "#"],
    "-": ["     ", "     ", "#####", "     ", "     "],
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#### ", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "F": ["#####", "#    ", "#### ", "#    ", "#    "],
    "G": [" ####", "#    ", "#  ##", "#   #", " ####"],
    "H": ["#   #", "#   #", "#####", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["#####", "   # ", "   # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "###  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#  ##", " ####"],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "S": [" ####", "#    ", " ### ", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "X": ["#   #", " # # ", "  #  ", " # # ", "#   #"],
    "Y": ["#   #", " # # ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "   # ", "  #  ", " #   ", "#####"],
    "0": [" ### ", "#  ##", "# # #", "##  #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "#####"],
    "2": [" ### ", "#   #", "  ## ", " #   ", "#####"],
    "3": ["#### ", "    #", " ### ", "    #", "#### "],
    "4": ["#   #", "#   #", "#####", "    #", "    #"],
    "5": ["#####", "#    ", "#### ", "    #", "#### "],
    "6": [" ####", "#    ", "#### ", "#   #", " ### "],
    "7": ["#####", "   # ", "  #  ", " #   ", "#    "],
    "8": [" ### ", "#   #", " ### ", "#   #", " ### "],
    "9": [" ### ", "#   #", " ####", "    #", "#### "],
}


def render_banner(word):
    """Return a list of 5 strings forming big block letters for `word`."""
    rows = ["", "", "", "", ""]
    for ch in word.upper():
        glyph = FONT.get(ch, FONT[" "])
        # pad all glyph rows to equal width
        w = max(len(r) for r in glyph)
        for i in range(5):
            cell = glyph[i].ljust(w) if i < len(glyph) else " " * w
            rows[i] += cell + "  "  # gap between letters
    return [r.rstrip() for r in rows]


# -------------------------------------------------------------- fake log ----
def build_log(target):
    t = target
    return [
        ("$ establishing uplink to %s ..." % t, DIM),
        ("> handshake accepted  [0xA91F]", RED_HOT),
        ("> bypassing firewall ........ DONE", RED_HOT),
        ("> escalating privileges -> ROOT", YELLOW),
        ("> injecting payload 'ghost.bin'", RED),
        ("> scanning filesystem ........ 4,192 files", RED),
        ("> locating credential vault ...", RED),
        ("> vault unlocked  OK", RED_HOT),
        ("> mirroring display buffer ...", RED),
        ("> disabling remote input ...", YELLOW),
        ("> uploading to node 0xC4 ..... 100%", RED_HOT),
        ("> wiping trace logs ...", DIM),
        ("> %s is now UNDER CONTROL" % t, YELLOW),
        ("$ awaiting operator command_", RED),
    ]


# ------------------------------------------------------- terminal helpers ----
def term_size():
    try:
        sz = os.get_terminal_size()
        return sz.columns, sz.lines
    except OSError:
        return 80, 24


class RawInput:
    """Non-blocking single-key reads on Unix; no-op elsewhere."""

    def __init__(self):
        self.ok = False
        self.fd = None
        self.old = None

    def __enter__(self):
        try:
            import termios
            import tty

            self.termios = termios
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            self.ok = True
        except Exception:
            self.ok = False
        return self

    def pressed(self):
        if not self.ok:
            return False
        import select

        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            try:
                sys.stdin.read(1)
            except Exception:
                pass
            return True
        return False

    def __exit__(self, *a):
        if self.ok and self.old is not None:
            try:
                self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old)
            except Exception:
                pass


def enter_screen():
    sys.stdout.write("\033[?1049h\033[?25l")  # alt buffer + hide cursor
    sys.stdout.flush()


def leave_screen():
    sys.stdout.write("\033[0m\033[?25h\033[?1049l")  # reset + show cursor + main buffer
    sys.stdout.flush()


# --------------------------------------------------------------- frames ------
def center(line_len, width):
    return max((width - line_len) // 2, 0)


class Buf:
    """An ANSI-safe character grid: one char + one color per cell.

    Overlapping writes compose correctly because positions are cell indices,
    never offsets into a string that already contains escape codes. Colors are
    emitted once, at serialize time, only where they change.
    """

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.ch = [[" "] * cols for _ in range(rows)]
        self.co = [[""] * cols for _ in range(rows)]

    def put(self, row, col, text, color=""):
        if row < 0 or row >= self.rows:
            return
        c = col
        for glyph in text:
            if 0 <= c < self.cols:
                self.ch[row][c] = glyph
                self.co[row][c] = color
            c += 1

    def render(self):
        out = []
        for r in range(self.rows):
            parts = []
            cur = None
            for c in range(self.cols):
                color = self.co[r][c]
                if color != cur:
                    parts.append(RESET)
                    if color:
                        parts.append(color)
                    cur = color
                parts.append(self.ch[r][c])
            parts.append(RESET)
            out.append("".join(parts))
        return "\n".join(out)


def compose_frame(cols, rows, state):
    """Return a single string (no trailing newline) for the current frame."""
    screen = Buf(cols, rows)
    put = screen.put

    word = state["word"]
    banner = render_banner(word)
    bw = max(len(r) for r in banner)
    btop = max(1, rows // 2 - 7)
    jitter = state["jitter"]
    bcol = center(bw, cols) + jitter
    bcolor = state["bcolor"]
    for i, brow in enumerate(banner):
        # faint chromatic ghost one column over
        if state["glitch"]:
            put(btop + i, bcol + 1, brow.replace("#", "█"), CYAN)
        put(btop + i, bcol, brow.replace("#", "█"), bcolor)

    sub = "U N A U T H O R I Z E D   A C C E S S   D E T E C T E D"
    put(btop + 6, center(len(sub), cols), sub, RED_HOT if state["blink"] else DIM)

    # meta line, top-left
    meta = "%s NODE 0xC4-FF-19   ROOT SHELL   %s" % (
        "[REC]" if state["blink"] else "     ",
        state["clock"],
    )
    put(1, 2, meta, DIM)

    # fake log, lower block
    log_top = btop + 8
    maxlog = max(0, rows - log_top - 4)
    shown = state["log_lines"][-maxlog:]
    for i, (text, color) in enumerate(shown):
        cur = "_" if (i == len(shown) - 1 and state["blink"]) else ""
        put(log_top + i, 2, text + cur, color)

    # access bar, near bottom
    bar_row = rows - 3
    pct = state["pct"]
    barw = min(cols - 20, 60)
    filled = int(barw * pct / 100)
    bar = "#" * filled + "-" * (barw - filled)
    bar = bar.replace("#", "█").replace("-", "░")
    label = "ACCESS "
    tail = ("%3d%%" % pct) if pct < 100 else "GRANTED"
    put(bar_row, 2, "%s[%s] %s" % (label, bar, tail), RED if pct < 100 else RED_HOT)

    # warning + hint, bottom
    warn = "!!!  DO NOT POWER OFF THIS DEVICE  !!!"
    if state["blink"]:
        put(rows - 2, center(len(warn), cols), warn, YELLOW + BOLD)
    hint = "[ press any key ]"
    put(rows - 1, cols - len(hint) - 2, hint, DIM)

    return screen.render()


def big_message(cols, rows, word, message):
    buf = [" " * cols for _ in range(rows)]
    banner = render_banner(word)
    top = max(1, rows // 2 - 5)
    for i, brow in enumerate(banner):
        line = brow.replace("#", "█")
        c = center(len(line), cols)
        buf[top + i] = " " * c + RED + BOLD + line + RESET
    c = center(len(message), cols)
    buf[top + 7] = " " * c + RED_HOT + message + RESET
    foot = "( it was only a prank — nothing was touched )"
    c = center(len(foot), cols)
    buf[top + 9] = " " * c + DIM + foot + RESET
    return "\n".join(buf)


# ----------------------------------------------------------------- main ------
def run(args):
    if args.selftest:
        cols, rows = term_size()
        rows = max(rows, 24)
        state = {
            "word": args.word, "jitter": 0, "bcolor": RED, "glitch": False,
            "blink": True, "clock": time.strftime("%H:%M:%S"), "pct": 73,
            "log_lines": build_log(args.target)[:9],
        }
        sys.stdout.write(compose_frame(cols, rows, state) + "\n")
        sys.stdout.write(RESET)
        return 0

    if not sys.stdout.isatty():
        sys.stderr.write(
            "fakehack: needs an interactive terminal (a TTY) to take over the screen.\n"
            "          Run it directly in a terminal, or use --selftest to preview one frame.\n"
        )
        return 2

    log_source = build_log(args.target)
    log_lines = []
    li = 0
    pct = 0.0
    start = time.monotonic()
    frame = 0
    fps = max(4, min(args.fps, 60))
    interval = 1.0 / fps

    enter_screen()
    try:
        with RawInput() as keys:
            quit_early = False
            while True:
                now = time.monotonic()
                elapsed = now - start
                if elapsed >= args.duration:
                    break
                if keys.pressed():
                    quit_early = True
                    break

                cols, rows = term_size()
                rows = max(rows, 20)

                # advance the fake log a few times a second
                if frame % max(1, int(fps / 3)) == 0:
                    log_lines.append(log_source[li % len(log_source)])
                    li += 1
                    if len(log_lines) > 60:
                        log_lines = log_lines[-60:]

                # climb the access bar
                if pct < 100:
                    pct = min(100.0, pct + random.uniform(0.4, 2.4))

                blink = (frame // max(1, int(fps / 2))) % 2 == 0
                glitch = random.random() < 0.18
                jitter = random.choice([-1, 0, 0, 0, 1]) if glitch else 0
                bcolor = random.choice([RED, RED, RED_HOT, BLOOD]) if glitch else RED

                state = {
                    "word": args.word,
                    "jitter": jitter,
                    "bcolor": bcolor,
                    "glitch": glitch,
                    "blink": blink,
                    "clock": time.strftime("%H:%M:%S"),
                    "pct": int(pct),
                    "log_lines": log_lines if log_lines else log_source[:1],
                }
                sys.stdout.write("\033[H" + compose_frame(cols, rows, state))
                sys.stdout.flush()
                frame += 1
                time.sleep(interval)

            # reveal
            if not args.no_reveal:
                cols, rows = term_size()
                rows = max(rows, 20)
                sys.stdout.write("\033[2J\033[H" + big_message(cols, rows, "GOTCHA", args.message))
                sys.stdout.flush()
                reveal_deadline = time.monotonic() + (0.0 if quit_early else 2.6)
                # hold the reveal briefly; a key press skips the wait
                while time.monotonic() < reveal_deadline:
                    if keys.pressed():
                        break
                    time.sleep(0.05)
    finally:
        leave_screen()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="fakehack",
        description="Terminal 'you've been hacked' prank screen. Pure theater — touches nothing.",
    )
    p.add_argument("-d", "--duration", type=float, default=15.0,
                   help="seconds to show the hacked screen before the reveal (default: 15)")
    p.add_argument("-w", "--word", default="HACKED",
                   help="the big banner word (default: HACKED)")
    p.add_argument("-t", "--target", default="DEVICE-07",
                   help="fake victim name shown in the log (default: DEVICE-07)")
    p.add_argument("-m", "--message", default="you just got pranked :)",
                   help="line shown under the GOTCHA reveal")
    p.add_argument("--fps", type=int, default=16, help="animation frames per second (4-60)")
    p.add_argument("--no-reveal", action="store_true",
                   help="skip the GOTCHA reveal; just restore the terminal when done")
    p.add_argument("--selftest", action="store_true",
                   help="print one static frame to stdout (no takeover) and exit")
    p.add_argument("--version", action="version", version="fakehack 1.0.0")
    args = p.parse_args(argv)

    # make sure Ctrl-C / kill still restore the terminal
    def _bail(signum, frame):
        leave_screen()
        sys.exit(130)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _bail)
        except Exception:
            pass

    try:
        return run(args)
    except KeyboardInterrupt:
        leave_screen()
        return 130


if __name__ == "__main__":
    sys.exit(main())
