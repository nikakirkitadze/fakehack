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

  fakehack tv                   # cast the hacked screen to an LG webOS TV (no mirroring)
  fakehack tv --ip 192.168.1.5 --word PWNED
"""

import argparse
import base64
import json
import os
import random
import signal
import socket
import struct
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


def main_prank(argv):
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
    p.add_argument("--version", action="version", version="fakehack 1.1.0")
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


# ------------------------------------------------------- cast to LG webOS ----
# A tiny, dependency-free LG webOS (SSAP) client over a secure WebSocket.
# Modern `ssl` only (works on current Python); the registration manifest omits
# the old shared "test" signature that 2023+ firmware blacklists.
DEFAULT_TV_URL = "https://nikakirkitadze.github.io/fakehack/"

LG_REGISTER_PAYLOAD = {
    "forcePairing": False,
    "pairingType": "PROMPT",
    "manifest": {
        "appVersion": "1.1",
        "manifestVersion": 1,
        "permissions": [
            "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP", "CLOSE", "TEST_OPEN", "TEST_PROTECTED",
            "CONTROL_AUDIO", "CONTROL_DISPLAY", "CONTROL_INPUT_JOYSTICK",
            "CONTROL_INPUT_MEDIA_RECORDING", "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_INPUT_TV",
            "CONTROL_POWER", "READ_APP_STATUS", "READ_CURRENT_CHANNEL", "READ_INPUT_DEVICE_LIST",
            "READ_NETWORK_STATE", "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST",
            "WRITE_NOTIFICATION_TOAST", "READ_POWER_STATE", "READ_COUNTRY_INFO", "READ_SETTINGS",
            "CONTROL_TV_SCREEN", "CONTROL_TV_STANBY", "CONTROL_FAVORITE_GROUP", "CONTROL_USER_INFO",
            "CHECK_BLUETOOTH_DEVICE", "CONTROL_BLUETOOTH", "CONTROL_TIMER_INFO",
            "STB_INTERNAL_CONNECTION", "CONTROL_RECORDING", "READ_RECORDING_STATE",
            "WRITE_RECORDING_LIST", "READ_RECORDING_LIST", "READ_RECORDING_SCHEDULE",
            "WRITE_RECORDING_SCHEDULE", "READ_STORAGE_DEVICE_LIST", "READ_TV_PROGRAM_INFO",
            "CONTROL_BOX_CHANNEL", "READ_TV_ACR_AUTH_TOKEN", "READ_TV_CONTENT_STATE",
            "READ_TV_CURRENT_TIME", "ADD_LAUNCHER_CHANNEL", "SET_CHANNEL_SKIP",
            "RELEASE_CHANNEL_SKIP", "CONTROL_CHANNEL_BLOCK", "DELETE_SELECT_CHANNEL",
            "CONTROL_CHANNEL_GROUP", "SCAN_TV_CHANNELS", "CONTROL_TV_POWER", "CONTROL_WOL",
        ],
    },
}


def _lg_ws_connect(ip, port=3001, timeout=10):
    import ssl

    raw = socket.create_connection((ip, port), timeout=timeout)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # TV uses a self-signed cert
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    sock = ctx.wrap_socket(raw, server_hostname=ip)
    key = base64.b64encode(os.urandom(16)).decode()
    req = ("GET / HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
           "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
           "Sec-WebSocket-Version: 13\r\n\r\n") % (ip, port, key)
    sock.sendall(req.encode())
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("connection closed during handshake")
        data += chunk
    if b" 101 " not in data.split(b"\r\n", 1)[0]:
        raise ConnectionError("unexpected handshake: %r" % data.split(b"\r\n", 1)[0])
    return sock, bytearray(data[data.index(b"\r\n\r\n") + 4:])


def _lg_frame(opcode, data=b""):
    header = bytearray([0x80 | opcode])
    n = len(data)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126); header += struct.pack("!H", n)
    else:
        header.append(0x80 | 127); header += struct.pack("!Q", n)
    mask = os.urandom(4)
    header += mask
    return bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data))


class _LGSocket:
    def __init__(self, sock, buf):
        self.sock = sock
        self.buf = buf

    def _exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("connection closed")
            self.buf += chunk
        out = bytes(self.buf[:n]); del self.buf[:n]; return out

    def send(self, obj):
        self.sock.sendall(_lg_frame(0x1, json.dumps(obj).encode("utf-8")))

    def recv(self):
        message = bytearray()
        while True:
            hdr = self._exact(2)
            fin, opcode, masked, length = hdr[0] & 0x80, hdr[0] & 0x0F, hdr[1] & 0x80, hdr[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._exact(8))[0]
            mask = self._exact(4) if masked else b""
            payload = self._exact(length) if length else b""
            if masked:
                payload = bytes(p ^ mask[i % 4] for i, p in enumerate(payload))
            if opcode == 0x8:
                raise ConnectionError("TV closed the connection")
            if opcode == 0x9:  # ping -> pong
                self.sock.sendall(_lg_frame(0xA, payload)); continue
            if opcode == 0xA:  # pong
                continue
            message += payload
            if fin:
                return json.loads(message.decode("utf-8", "replace"))

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def _lg_discover(timeout=4):
    """Return the IP of the first LG webOS TV found via SSDP, or None."""
    import re

    msg = ("M-SEARCH * HTTP/1.1\r\nHOST:239.255.255.250:1900\r\n"
           'MAN:"ssdp:discover"\r\nMX:2\r\nST:ssdp:all\r\n\r\n').encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    s.settimeout(1.0)
    for _ in range(3):
        try:
            s.sendto(msg, ("239.255.255.250", 1900))
        except Exception:
            pass
    deadline = time.time() + timeout
    seen = {}
    while time.time() < deadline:
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            continue
        except Exception:
            break
        seen.setdefault(addr[0], b"")
        seen[addr[0]] += data
    s.close()
    from urllib.request import urlopen
    for ip, raw in seen.items():
        text = raw.decode("utf-8", "replace")
        if re.search(r"(?i)lg|webos", text):
            return ip
        loc = re.search(r"(?im)^LOCATION:\s*(.+)$", text)
        if loc:
            try:
                with urlopen(loc.group(1).strip(), timeout=2.0) as r:
                    xml = r.read().decode("utf-8", "replace")
                if re.search(r"(?i)lg electronics|webos", xml):
                    return ip
            except Exception:
                pass
    return None


def _cast_to_lg(ip, url, client_key=None, pair_timeout=120, on_prompt=None):
    """Pair (if needed) and open `url` in the TV browser. Returns the client-key."""
    sock, buf = _lg_ws_connect(ip)
    ws = _LGSocket(sock, buf)
    payload = json.loads(json.dumps(LG_REGISTER_PAYLOAD))
    if client_key:
        payload["client-key"] = client_key
    ws.send({"type": "register", "id": "register_0", "payload": payload})
    sock.settimeout(pair_timeout)
    key = client_key
    while True:
        d = ws.recv()
        kind = d.get("type")
        if kind == "response" and d.get("id") == "register_0":
            if d.get("payload", {}).get("pairingType") == "PROMPT" and on_prompt:
                on_prompt()
        elif kind == "registered" and d.get("id") == "register_0":
            key = d.get("payload", {}).get("client-key") or key
            break
        elif kind == "error":
            ws.close()
            raise RuntimeError(d.get("error") or "registration failed")
    sock.settimeout(15)
    ws.send({"type": "request", "id": "req_open",
             "uri": "ssap://system.launcher/open", "payload": {"target": url}})
    resp = None
    while True:
        d = ws.recv()
        if d.get("id") == "req_open":
            resp = d
            break
    ws.close()
    if not (isinstance(resp, dict) and resp.get("payload", {}).get("returnValue", False)):
        raise RuntimeError("TV did not confirm opening the page: %r" % (resp,))
    return key


def _tv_store_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "fakehack", "lgtv.json")


def _load_store():
    import json
    try:
        with open(_tv_store_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_store(store):
    import json
    path = _tv_store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(store, f)
    except Exception:
        pass


def _build_tv_url(args):
    from urllib.parse import urlencode

    params = {}
    if args.word:
        params["word"] = args.word
    if args.target:
        params["target"] = args.target
    if args.message:
        params["msg"] = args.message
    if args.headline:
        params["headline"] = args.headline
    if args.duration and args.duration > 0:
        params["duration"] = int(args.duration)
    if not params:
        return args.url
    sep = "&" if "?" in args.url else "?"
    return args.url + sep + urlencode(params)


def main_tv(argv):
    ap = argparse.ArgumentParser(
        prog="fakehack tv",
        description="Cast the hacked screen to an LG webOS TV over Wi-Fi — no screen mirroring. "
                    "First run shows a one-time pairing prompt on the TV; accept it with the remote.",
    )
    ap.add_argument("--ip", help="TV IP address (default: auto-discover on the LAN)")
    ap.add_argument("-w", "--word", default="HACKED", help="big banner word (default: HACKED)")
    ap.add_argument("-t", "--target", default="DEVICE-07", help="fake victim name in the log")
    ap.add_argument("-m", "--message", default=None, help="line under the GOTCHA reveal")
    ap.add_argument("--headline", default=None, help="big top line (default: SYSTEM COMPROMISED)")
    ap.add_argument("-d", "--duration", type=float, default=0,
                    help="auto-reveal GOTCHA after N seconds (0 = stay until someone clicks the TV remote)")
    ap.add_argument("--url", default=DEFAULT_TV_URL, help="base URL of the hosted screen")
    ap.add_argument("--pair-timeout", type=int, default=120, help="seconds to wait for the one-time TV pairing prompt")
    args = ap.parse_args(argv)

    # Resolve the TV IP (auto-discover if not given).
    ip = args.ip
    if not ip:
        sys.stderr.write("Discovering an LG webOS TV on the LAN ...\n")
        sys.stderr.flush()
        ip = _lg_discover()
        if not ip:
            sys.stderr.write("No LG TV found automatically. Re-run with --ip <address>.\n")
            return 4
        sys.stderr.write("Found TV at %s\n" % ip)

    store = _load_store()
    client_key = store.get(ip, {}).get("client_key")

    url = _build_tv_url(args)
    prompted = {"shown": False}

    def on_prompt():
        prompted["shown"] = True
        sys.stderr.write(
            "\n>> FIRST-TIME SETUP: the TV is showing a 'connect this device?' prompt.\n"
            "   Accept it with the remote (ONE time only — every cast after this is silent).\n\n"
        )
        sys.stderr.flush()

    try:
        new_key = _cast_to_lg(ip, url, client_key=client_key,
                              pair_timeout=args.pair_timeout, on_prompt=on_prompt)
    except ConnectionError as exc:
        sys.stderr.write("Could not reach the TV at %s: %s\n" % (ip, exc))
        sys.stderr.write("Make sure it's ON and on the same Wi-Fi.\n")
        return 5
    except Exception as exc:
        text = str(exc).lower()
        if "cancel" in text or "denied" in text or "rejected" in text or "403" in text:
            sys.stderr.write("The TV did not accept pairing: %s\n" % exc)
            sys.stderr.write("Re-run and choose Accept on the TV within the time window.\n")
            return 6
        sys.stderr.write("Casting failed: %s\n" % exc)
        return 7

    if new_key and new_key != client_key:
        store[ip] = {"client_key": new_key}
        _save_store(store)

    print("Hacked screen is now on the TV (%s)." % ip)
    print("URL: %s" % url)
    print("(silent cast — no TV confirmation needed)" if not prompted["shown"]
          else "Paired! That was the one-time confirmation; future casts are silent.")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "tv":
        return main_tv(argv[1:])
    return main_prank(argv)


if __name__ == "__main__":
    sys.exit(main())
