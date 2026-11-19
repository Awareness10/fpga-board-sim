"""Colours for boardsim's own output, with the same rules as Python 3.14's: only on a
terminal, never with NO_COLOR set, always with FORCE_COLOR set. Works on Windows too."""
import os
import sys


def _enable_windows_ansi(stream):
    """Windows Terminal understands ANSI codes; the old console needs them switched on."""
    try:
        import ctypes
        import msvcrt

        kernel32 = ctypes.windll.kernel32
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        return bool(kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
    except (AttributeError, OSError, ValueError):
        return False


def can_colour(stream=None):
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        if not stream.isatty():
            return False
    except (AttributeError, ValueError):
        return False
    return _enable_windows_ansi(stream) if sys.platform == "win32" else True


_ON = {1: can_colour(sys.stdout), 2: can_colour(sys.stderr)}
_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "blue": "34",
          "magenta": "35", "cyan": "36", "bold_red": "1;31", "bold_green": "1;32"}


def paint(text, style, fd=1):
    return f"\x1b[{_CODES[style]}m{text}\x1b[0m" if _ON.get(fd) else str(text)


def ok(t, fd=1):
    return paint(t, "bold_green", fd)


def bad(t, fd=1):
    return paint(t, "bold_red", fd)


def warn(t, fd=1):
    return paint(t, "yellow", fd)


def dim(t, fd=1):
    return paint(t, "dim", fd)


def head(t, fd=1):
    return paint(t, "bold", fd)


def path(t, fd=1):
    return paint(t, "cyan", fd)
