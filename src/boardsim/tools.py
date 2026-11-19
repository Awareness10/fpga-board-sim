"""Finding the external tools on Windows, macOS and Linux, and running Conan."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import ghdl, qemu

ROOT = Path(__file__).resolve().parents[2]          # the repository checkout
CONAN_PROFILES = ROOT / "conan" / "profiles"
TOOLCHAIN_RECIPE = ROOT / "conan" / "recipes" / "arm-gnu-toolchain"


def repo_dir(*parts):
    p = ROOT.joinpath(*parts)
    if not p.exists():
        raise SystemExit(f"{p} not found: run boardsim from a checkout of the repository (uv run boardsim ...)")
    return p


def find(name, env=None, candidates=()):
    if env and os.environ.get(env):
        return os.environ[env]
    return shutil.which(name) or next((c for c in candidates if os.path.isfile(c)), None)


def find_gtkwave():
    return find("gtkwave", "GTKWAVE", {
        "win32": [r"C:\gtkwave\bin\gtkwave.exe", r"C:\msys64\ucrt64\bin\gtkwave.exe"],
        "darwin": ["/Applications/gtkwave.app/Contents/Resources/bin/gtkwave", "/opt/homebrew/bin/gtkwave"],
    }.get(sys.platform, []))


def find_conan():
    """Conan from the same environment as boardsim (uv installs it as a dependency)."""
    exe = Path(sys.executable).parent / ("conan.exe" if sys.platform == "win32" else "conan")
    return str(exe) if exe.exists() else (shutil.which("conan") or "conan")


def run(cmd, **kw):
    print("+ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], **kw).returncode


def conan_setup(quiet=False):
    """A default build profile, and the Arm toolchain recipe in the local Conan cache."""
    conan = find_conan()
    out = None if not quiet else subprocess.DEVNULL
    subprocess.run([conan, "profile", "detect", "--exist-ok"], stdout=out, stderr=out, check=True)
    subprocess.run([conan, "export", str(TOOLCHAIN_RECIPE)], stdout=out, stderr=out, check=True)


def conan_build(project, profile, test=True):
    conan_setup(quiet=True)
    cmd = [find_conan(), "build", str(project), "-pr:h", str(CONAN_PROFILES / profile), "-pr:b", "default",
           "--build=missing"]
    if not test:
        cmd += ["-c", "tools.build:skip_test=True"]
    return run(cmd)


TOOLS = [
    # name, finder, needed for, install hint per platform
    ("qemu-system-arm", qemu.find_qemu, "Zybo: run ARM programs, board view", qemu.INSTALL_HINT),
    ("ghdl", ghdl.find_ghdl, "VHDL testbenches, Basys3 board view", ghdl.INSTALL_HINT),
    ("gtkwave", find_gtkwave, "waveforms (optional)", {
        "win32": "https://gtkwave.sourceforge.net (or the Surfer viewer: https://surfer-project.org)",
        "darwin": "brew install --cask gtkwave   (or Surfer: https://surfer-project.org)",
        "linux": "sudo apt install gtkwave   /   sudo pacman -S gtkwave",
    }),
]
