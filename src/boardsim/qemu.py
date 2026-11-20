#!/usr/bin/env python3
"""Run a bare-metal Zynq program in QEMU (machine xilinx-zynq-a9), on any OS.

    python qemu.py prog.elf                          run, print the UART, exit with its code
    python qemu.py prog.elf --keys "1.2.q" --expect "LD3..LD0 ...\\*"   scripted test
    python qemu.py prog.elf --interactive            type lines, they go to the UART

UART1 (the Zybo's USB-UART) is a TCP socket on 127.0.0.1 instead of QEMU's stdio:
pipes into QEMU behave differently on Windows, a socket is the same everywhere. We listen
and QEMU connects as a client: on Windows, ports that look free can be reserved (Hyper-V,
WSL2, Docker) and QEMU can't bind them, while a port the OS gives us is always usable.
QEMU connects before it starts the CPU, so no output is lost. Semihosting
turns the program's exit(code) into QEMU's exit status.

Standard library only: CMake's ctest runs this file directly with any Python 3.
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

MACHINE = ["-M", "xilinx-zynq-a9", "-m", "512M", "-display", "none", "-monitor", "none",
           "-semihosting", "-serial", "null"]          # UART0 unused, UART1 = the socket

INSTALL_HINT = {
    "win32": "winget install SoftwareFreedomConservancy.QEMU   (or https://qemu.weilnetz.de)",
    "darwin": "brew install qemu",
    "linux": "sudo apt install qemu-system-arm   /   sudo pacman -S qemu-system-arm   /   sudo dnf install qemu-system-arm",
}


def find_qemu():
    """qemu-system-arm from $QEMU, PATH, or the usual install folders."""
    if os.environ.get("QEMU"):
        return os.environ["QEMU"]
    found = shutil.which("qemu-system-arm")
    if found:
        return found
    candidates = {
        "win32": [r"C:\Program Files\qemu\qemu-system-arm.exe"],
        "darwin": ["/opt/homebrew/bin/qemu-system-arm", "/usr/local/bin/qemu-system-arm"],
    }.get(sys.platform, [])
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def shell_line(cmd):
    """The command as you'd type it in this OS's shell (paths with spaces quoted)."""
    if sys.platform == "win32":
        line = subprocess.list2cmdline([str(c) for c in cmd])
        return "& " + line if line.startswith('"') else line      # PowerShell needs & before a quoted path
    import shlex
    return shlex.join(str(c) for c in cmd)


class Qemu:
    """One QEMU process with UART1 on a socket. read() / send() / wait()."""

    def __init__(self, elf, icount_shift=None, extra=(), on_message=None):
        qemu = find_qemu()
        if not qemu:
            hint = INSTALL_HINT.get(sys.platform, INSTALL_HINT["linux"])
            raise SystemExit(f"qemu-system-arm not found. Install it: {hint}\n(or set QEMU=/path/to/qemu-system-arm)")
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))      # the OS picks a port that is really free
        self.listener.listen(1)
        port = self.listener.getsockname()[1]
        cmd = [qemu, *MACHINE, "-serial", f"tcp:127.0.0.1:{port}", "-kernel", elf]
        if icount_shift is not None:
            # 2^shift ns per instruction, kept in step with the wall clock
            cmd += ["-icount", f"shift={icount_shift},align=on"]
        cmd += list(extra)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, creationflags=flags)
        except OSError as e:
            self.listener.close()
            hint = ""
            if sys.platform == "win32":
                hint = ("\nWindows refused to start it. If it says the file is blocked (Smart App Control, "
                        "an application control policy or your antivirus), allow qemu-system-arm.exe there, "
                        "or check that it starts at all: & \"" + qemu + "\" --version")
            raise SystemExit(f"Could not start QEMU ({qemu}): {e}{hint}")
        self.messages = []                       # QEMU's own stdout/stderr (warnings)
        self.on_message = on_message
        threading.Thread(target=self._drain, daemon=True).start()
        self.sock = None
        deadline = time.time() + 10
        self.listener.settimeout(0.1)
        while self.sock is None:
            try:
                self.sock, _ = self.listener.accept()
            except OSError:
                code = self.proc.poll()
                if code is not None or time.time() > deadline:
                    self.listener.close()
                    if code is None:
                        self.proc.kill()
                    time.sleep(0.2)              # let _drain pick up QEMU's last words
                    out = b"".join(self.messages).decode(errors="replace").strip()
                    why = f"exited with code {code}" if code is not None else "never connected its UART (10 s)"
                    raise SystemExit(f"QEMU did not start: it {why}.\n  command: {shell_line(cmd)}\n"
                                     f"  QEMU said: {out or '(nothing)'}")
                time.sleep(0.05)
        self.listener.close()
        self.sock.settimeout(None)

    def _drain(self):
        for line in self.proc.stdout:
            self.messages.append(line)
            if self.on_message:
                self.on_message(line.decode(errors="replace").rstrip())

    def read(self, n=4096):
        """Bytes from the UART, b'' once the program has ended."""
        try:
            return self.sock.recv(n)
        except OSError:
            return b""

    def send(self, data):
        try:
            self.sock.sendall(data.encode() if isinstance(data, str) else data)
        except OSError:
            pass

    def wait(self, timeout=None):
        try:
            return self.proc.wait(timeout)
        finally:
            self.close()

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self.close()

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass


def run(elf, keys="", timeout=20.0, echo=True):
    """Run to completion. keys go to the UART once the program has printed something
    (the UART drops bytes until bsp_init enables its receiver). Returns (code, output)."""
    q = Qemu(elf)
    out = bytearray()
    timed_out = threading.Event()

    def expire():
        timed_out.set()
        q.kill()

    timer = threading.Timer(timeout, expire)
    timer.start()
    sent = not keys
    try:
        while True:
            data = q.read()
            if not data:
                break
            out += data
            if echo:
                sys.stdout.write(data.decode(errors="replace").replace("\r", ""))
                sys.stdout.flush()
            if not sent:
                q.send(keys)
                sent = True
        code = q.wait(5)
    finally:
        timer.cancel()
        q.kill()
    return (None if timed_out.is_set() else code), out.decode(errors="replace").replace("\r", "")


def interactive(elf):
    q = Qemu(elf)

    def typing():
        for line in sys.stdin:
            q.send(line.rstrip("\r\n"))

    threading.Thread(target=typing, daemon=True).start()
    try:
        while True:
            data = q.read()
            if not data:
                break
            sys.stdout.write(data.decode(errors="replace").replace("\r", ""))
            sys.stdout.flush()
        return q.wait(5)
    except KeyboardInterrupt:
        q.kill()
        return 130


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("elf")
    ap.add_argument("--keys", default="", help="characters to type into the UART")
    ap.add_argument("--expect", help="regex the output must match (test mode)")
    ap.add_argument("--fail", default=r"EXCEPTION|CHECK failed", help="regex that fails the test")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--interactive", action="store_true", help="forward typed lines to the UART")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.elf):
        raise SystemExit(f"{args.elf}: not found")
    if args.interactive:
        return interactive(args.elf)

    code, out = run(args.elf, args.keys, args.timeout)
    if code is None:
        print(f"\nTIMEOUT after {args.timeout:g} s", file=sys.stderr)
        return 124
    if args.fail and re.search(args.fail, out):
        print(f"\nFAIL: output matches /{args.fail}/", file=sys.stderr)
        return 1
    if args.expect and not re.search(args.expect, out, re.DOTALL):
        print(f"\nFAIL: output does not match /{args.expect}/", file=sys.stderr)
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
