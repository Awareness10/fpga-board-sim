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
    ("vivado", lambda: find_vivado(), "bitstreams, programming real boards (optional)", {
        "win32": "AMD Vivado 2023.2 (https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado.html)",
        "darwin": "not available for macOS: use a Windows/Linux machine for bitstreams",
        "linux": "AMD Vivado 2023.2 (https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado.html)",
    }),
]


# --- AMD/Xilinx tools (Windows and Linux only; there is no Vivado for macOS) -------
XILINX_ROOTS = {
    "win32": [Path("C:/Xilinx"), Path("C:/AMD"), Path("D:/Xilinx")],
    "linux": [Path.home() / "Xilinx", Path("/tools/Xilinx"), Path("/opt/Xilinx")],
}.get(sys.platform, [])


def find_xilinx(product, exe, env=None):
    """<root>/<product>/<version>/bin/<exe>, newest version first; $env or PATH win."""
    exe_name = exe + (".bat" if sys.platform == "win32" else "")
    if env and os.environ.get(env):
        p = Path(os.environ[env])
        p = p / "bin" / exe_name if p.is_dir() else p
        return str(p) if p.exists() else None
    found = shutil.which(exe_name) or shutil.which(exe)
    if found:
        return found
    hits = sorted((v for root in XILINX_ROOTS for v in root.glob(f"{product}/*/bin/{exe_name}")), reverse=True)
    return str(hits[0]) if hits else None


def find_vivado():
    return find_xilinx("Vivado", "vivado", "XILINX_VIVADO")


def require(path, what):
    if not path:
        where = {"darwin": "Vivado/Vitis don't run on macOS: use a Windows or Linux machine (or VM) for this step.",
                 "win32": "Install Vivado/Vitis 2023.2 (default C:\\Xilinx), or set XILINX_VIVADO / XILINX_VITIS.",
                 }.get(sys.platform, "Install Vivado/Vitis 2023.2 (default ~/Xilinx), or set XILINX_VIVADO / XILINX_VITIS.")
        raise SystemExit(f"{what} not found. {where}")
    return path


def find_vitis():
    return find_xilinx("Vitis", "vitis", "XILINX_VITIS")


def find_xsdb():
    return find_xilinx("Vitis", "xsdb", "XILINX_VITIS")


def xilinx_env(tool):
    """Environment for a Vitis tool, roughly what Vitis' settings64.sh / settings64.bat set
    up: XILINX_VITIS, and Vitis' own ARM compilers on PATH."""
    env = dict(os.environ)
    root = Path(tool).resolve().parent.parent
    host = "nt" if sys.platform == "win32" else "lin"
    env["XILINX_VITIS"] = str(root)
    paths = [root / "bin", root / "gnu" / "aarch32" / host / "gcc-arm-none-eabi" / "bin",
             root / "gnu" / "aarch64" / host / "aarch64-none" / "bin"]
    env["PATH"] = os.pathsep.join([str(p) for p in paths if p.is_dir()] + [env.get("PATH", "")])
    # On Linux distributions other than Ubuntu/RHEL (Arch, Fedora, ...) Vitis' bundled cmake
    # can't find OpenSSL 1.0: point it at the copy Vitis ships for Ubuntu. Harmless elsewhere.
    libs = root / "tps" / "lnx64" / "cmake-3.24.2" / "libs" / "Ubuntu"
    if sys.platform.startswith("linux") and libs.is_dir():
        env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [str(libs), env.get("LD_LIBRARY_PATH")]))
    return env
