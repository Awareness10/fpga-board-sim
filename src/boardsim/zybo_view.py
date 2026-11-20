"""Live Zybo board view: runs a program in QEMU and shows the board in a browser
(LEDs, buttons, switches, the AXI GPIO registers, bus activity, the UART console).

    browser page (web/zybo.html)  <--HTTP / server-sent events-->  this module
    this module                   <--TCP socket = UART1-->  QEMU: your program + the board
                                                           model (zybo/ps/model/zybo_board.c)

The model prints "@zybo key=value ..." lines once the page asks for them ('@'), and takes
explicit input commands (a-d/A-D = press/release BTN0-3, e-h/E-H = SW0-3 on/off).

QEMU runs with -icount shift=N,align=on: 2^N ns per instruction, kept in step with the
wall clock. N=1 is about the speed of the Zybo's 650 MHz Cortex-A9 (667 MHz on the Zybo Z7).
"""
import re
import threading
import time

from . import qemu, server

HEX_FIELDS = {"led", "btn", "sw", "dout1", "tri1", "tri2", "in2", "off", "val"}
DEC_FIELDS = {"rd", "wr"}
ALLOWED_INPUT = set("abcdABCDefghEFGH12345678")
LATE = re.compile(r"late by [\d.]+ to ([\d.]+) seconds")
LATE_OK_S = 2.0          # startup lag that is normal and caught up again


class Board:
    """Owns the QEMU process: start, restart (the PS-SRST button), stop, send input."""

    def __init__(self, elf, hub, shift=1):
        self.elf, self.hub, self.shift = elf, hub, shift
        self.q = None
        self.gen = 0
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            self.gen += 1
            gen = self.gen
            self.q = qemu.Qemu(self.elf, icount_shift=self.shift, on_message=self._qemu_message)
            q = self.q
        self.hub.publish({"t": "status", "running": True, "code": None})
        threading.Thread(target=self._reader, args=(q, gen), daemon=True).start()

    def _qemu_message(self, line):
        # QEMU's own output. "The guest is now late by X to Y seconds" means this computer
        # can't emulate the CPU at the -icount speed. Up to a couple of seconds happens at
        # every startup and is caught up again: noise. More than that means it keeps falling
        # behind, so timing (e.g. the blink) gets slower than on the board.
        if not line:
            return
        late = LATE.search(line)
        if late:
            if float(late.group(1)) <= LATE_OK_S:
                return
            line = (f"QEMU is {late.group(1)} s behind the real chip: this computer can't keep up, so the "
                    f"program runs slower than on the board. Try --shift {self.shift + 1}.")
        self.hub.publish({"t": "uart", "line": "[qemu] " + line})

    def stop(self):
        with self.lock:
            q, self.q = self.q, None
            self.gen += 1
        if q:
            q.kill()

    def restart(self):
        self.stop()
        self.hub.publish({"t": "reset"})
        self.start()

    def send(self, chars):
        with self.lock:
            q = self.q
        if q:
            q.send(chars)

    def _line(self, line, state):
        if line.startswith("@zybo "):
            ev = {"t": "state", "time": time.time()}
            for item in line[6:].split():
                k, _, v = item.partition("=")
                try:
                    ev[k] = int(v, 16) if k in HEX_FIELDS else int(v) if k in DEC_FIELDS else v
                except ValueError:
                    ev[k] = v
            self.hub.publish(ev)
        elif line.startswith("[zybo]"):
            # The model's first line comes from the first GPIO access: by then bsp_init has
            # enabled the UART receiver, so the '@' will not be dropped.
            if not state["gui"]:
                state["gui"] = True
                self.send("@")
        else:
            self.hub.publish({"t": "uart", "line": line})

    def _reader(self, q, gen):
        buf, state = b"", {"gui": False}
        while True:
            data = q.read()
            if not data or gen != self.gen:
                break
            buf += data
            *lines, buf = buf.split(b"\n")
            for raw in lines:
                self._line(raw.decode("utf-8", "replace").rstrip("\r"), state)
        code = q.wait(5) if q.proc.poll() is None and gen == self.gen else q.proc.poll()
        if gen == self.gen:
            self.hub.publish({"t": "status", "running": False, "code": code})


def run(elf, shift=1, port=8737, open_browser=True):
    hub = server.Hub()
    board = Board(str(elf), hub, shift)
    program = elf.stem
    board.start()
    routes = {
        "/input": lambda body: board.send("".join(c for c in body if c in ALLOWED_INPUT)),
        "/reset": lambda body: board.restart(),
    }
    server.serve("zybo.html", hub, {"t": "hello", "program": program, "shift": shift}, routes,
                 port=port, open_browser=open_browser, on_stop=board.stop)
    return 0
