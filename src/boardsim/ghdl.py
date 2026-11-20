"""VHDL simulation with GHDL for a design folder laid out as

    src/*.vhdl     the design (what goes to Vivado)
    tb/*_tb.vhdl   self-checking testbenches, one per file
    sim/*.vhdl     simulation-only helpers (bus functional models, board views)
(.vhd works too.)

Build products go to <design>/build/: the GHDL work library in build/ghdl/, waveforms
in build/<testbench>.ghw. Works the same on Windows, macOS and Linux.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import installer, term

STD = "08"
INSTALL_HINT = {
    "win32": "uv run boardsim install ghdl",
    "darwin": "uv run boardsim install ghdl   (Apple Silicon; needs the Xcode command line tools: xcode-select --install)",
    "linux": "sudo apt install ghdl   /   paru -S ghdl (Arch, AUR)   /   uv run boardsim install ghdl",
}

# --- Installing GHDL: the official release builds, checked against their SHA-256 ----------
RELEASE = "6.0.0"
RELEASE_URL = "https://github.com/ghdl/ghdl/releases/download/v{v}/{name}"
BUILDS = {   # (sys.platform, machine) -> (file, sha256)
    ("win32", "amd64"): ("ghdl-mcode-{v}-ucrt64.zip",
                         "76e160ceec35834c73ada6e4e484416d13aed4b64cbc7c74c5cca53a7ef60e41"),
    ("darwin", "arm64"): ("ghdl-llvm-{v}-macos14-aarch64.tar.gz",
                          "9cb3ccc09ca95f37c88bb757b3da7415ce5efede51e136e0262c74f3f99c2245"),
    ("linux", "x86_64"): ("ghdl-mcode-{v}-ubuntu24.04-x86_64.tar.gz",
                          "30d6a977b8456d140bbafecbbe64b1947a3d92eeae8f5e6d9f528a174f9566e7"),
}


def installed_dir():
    return installer.data_dir() / f"ghdl-{RELEASE}"


def install(force=False):
    """Download and unpack the GHDL release build for this computer. Returns ghdl's path."""
    import platform

    exe = installed_dir() / "bin" / ("ghdl.exe" if sys.platform == "win32" else "ghdl")
    if exe.exists() and not force:
        print(term.ok(f"GHDL {RELEASE} is already installed: ") + term.path(exe))
        return exe
    build = BUILDS.get((sys.platform, platform.machine().lower()))
    if not build:
        hint = INSTALL_HINT.get(sys.platform, INSTALL_HINT["linux"]).replace("uv run boardsim install ghdl", "")
        raise SystemExit(f"No GHDL release build for {sys.platform}/{platform.machine()}. "
                         f"Install it another way: {hint.strip(' /') or 'https://github.com/ghdl/ghdl'}")
    name, sha256 = build[0].format(v=RELEASE), build[1]
    installer.fetch(RELEASE_URL.format(v=RELEASE, name=name), sha256, installed_dir())
    if not exe.exists():
        raise SystemExit(f"Unpacked {name}, but {exe} is missing.")
    print(term.ok(f"Installed GHDL {RELEASE}: ") + term.path(exe))
    return exe


def find_ghdl():
    if os.environ.get("GHDL"):
        return os.environ["GHDL"]
    found = shutil.which("ghdl")
    if found:
        return found
    candidates = [installed_dir() / "bin" / ("ghdl.exe" if sys.platform == "win32" else "ghdl")]
    candidates += [Path(c) for c in {
        "win32": [r"C:\msys64\ucrt64\bin\ghdl.exe", r"C:\msys64\mingw64\bin\ghdl.exe", r"C:\ghdl\bin\ghdl.exe"],
        "darwin": ["/opt/homebrew/bin/ghdl", "/usr/local/bin/ghdl"],
    }.get(sys.platform, [])]
    return next((str(c) for c in candidates if c.is_file()), None)


def require_ghdl():
    ghdl = find_ghdl()
    if not ghdl:
        hint = INSTALL_HINT.get(sys.platform, INSTALL_HINT["linux"])
        raise SystemExit(f"ghdl not found. Install it:\n  {hint}\n(or set GHDL=/path/to/ghdl)")
    return ghdl


VHDL_EXTS = (".vhdl", ".vhd")


def vhdl_files(folder, suffix=""):
    """VHDL files in <folder> whose name (without extension) ends in <suffix>, .vhdl or .vhd."""
    return sorted(f for f in Path(folder).glob("*") if f.suffix in VHDL_EXTS and f.stem.endswith(suffix))


def vhdl_file(folder, stem):
    """<folder>/<stem>.vhdl or .vhd, whichever exists (None if neither)."""
    return next((Path(folder) / (stem + e) for e in VHDL_EXTS if (Path(folder) / (stem + e)).exists()), None)


class Design:
    def __init__(self, root, extra_sim=(), stop_time="10ms"):
        self.root = Path(root).resolve()
        self.build = self.root / "build"
        self.work = self.build / "ghdl"
        self.extra_sim = [Path(p).resolve() for p in extra_sim]
        self.stop_time = stop_time
        self.ghdl = require_ghdl()

    @property
    def flags(self):
        return [f"--std={STD}", f"--workdir={self.work}", "-frelaxed"]

    def files(self, extra=()):
        sim = [f for d in [*self.extra_sim, self.root / "sim"] for f in vhdl_files(d)]
        return [*sim, *vhdl_files(self.root / "src"), *vhdl_files(self.root / "tb"),
                *[Path(e) for e in extra]]

    def testbenches(self):
        return [f.stem for f in vhdl_files(self.root / "tb", "_tb")]

    def _ghdl(self, *args, log=None, **kw):
        cmd = [self.ghdl, *args]
        if log is None:
            return subprocess.run(cmd, cwd=self.root, **kw)
        with open(log, "a") as f:
            return subprocess.run(cmd, cwd=self.root, stdout=f, stderr=subprocess.STDOUT, **kw)

    def analyse(self, extra=()):
        """Register every file in the work library (GHDL sorts out the order itself)."""
        self.work.mkdir(parents=True, exist_ok=True)
        r = self._ghdl("-i", *self.flags, *map(str, self.files(extra)), capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(r.stdout + r.stderr)

    def elaborate(self, unit, log=None):
        return self._ghdl("-m", *self.flags, unit, log=log).returncode == 0

    def run(self, unit, wave=False, log=None, stop_time=None, extra_args=(), **kw):
        args = ["-r", *self.flags, unit, f"--stop-time={stop_time or self.stop_time}", "--assert-level=error"]
        if wave:
            args.append(f"--wave={self.build / (unit + '.ghw')}")
        return self._ghdl(*args, *extra_args, log=log, **kw)

    def test(self, only=None):
        """Run every testbench; print PASS/FAIL like a test runner. True if all pass."""
        self.analyse()
        ok = True
        for tb in self.testbenches():
            if only and not tb.startswith(only):
                continue
            log = self.build / f"{tb}.log"
            log.unlink(missing_ok=True)
            passed = self.elaborate(tb, log) and self.run(tb, log=log).returncode == 0
            # Reaching --stop-time exits with 0, but then the testbench never got to its end
            # (and maybe not to its checks either): count that as a failure.
            timed_out = passed and "stopped by --stop-time" in log.read_text(errors="replace")
            passed = passed and not timed_out
            print(f"{term.ok('PASS') if passed else term.bad('FAIL')}  {tb}", flush=True)
            if timed_out:
                print(term.dim(f"        did not finish within {self.stop_time} of simulated time: end the "
                               "testbench with std.env.finish (or stop its clock) sooner"))
            if not passed:
                ok = False
                lines = [l for l in log.read_text(errors="replace").splitlines()
                         if any(k in l.lower() for k in ("error", "fail", "assert"))]
                for l in lines[:4]:
                    print(term.dim(f"        {l}"))
        return ok
