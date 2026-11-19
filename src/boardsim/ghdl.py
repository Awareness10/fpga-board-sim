"""VHDL simulation with GHDL for a design folder laid out as

    src/*.vhd      the design (what goes to Vivado)
    tb/*_tb.vhd    self-checking testbenches, one per file
    sim/*.vhd      simulation-only helpers (bus functional models, board views)

Build products go to <design>/build/: the GHDL work library in build/ghdl/, waveforms
in build/<testbench>.ghw. Works the same on Windows, macOS and Linux.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

STD = "08"
INSTALL_HINT = {
    "win32": "download the mingw64/ucrt64 zip from https://github.com/ghdl/ghdl/releases and put its bin/ on PATH,\n"
             "  or in MSYS2: pacman -S mingw-w64-ucrt-x86_64-ghdl-llvm",
    "darwin": "download the macOS tarball from https://github.com/ghdl/ghdl/releases and put its bin/ on PATH",
    "linux": "sudo apt install ghdl   /   paru -S ghdl (Arch, AUR)   /   https://github.com/ghdl/ghdl/releases",
}


def find_ghdl():
    if os.environ.get("GHDL"):
        return os.environ["GHDL"]
    found = shutil.which("ghdl")
    if found:
        return found
    candidates = {
        "win32": [r"C:\msys64\ucrt64\bin\ghdl.exe", r"C:\msys64\mingw64\bin\ghdl.exe", r"C:\ghdl\bin\ghdl.exe"],
        "darwin": ["/opt/homebrew/bin/ghdl", "/usr/local/bin/ghdl"],
    }.get(sys.platform, [])
    return next((c for c in candidates if os.path.isfile(c)), None)


def require_ghdl():
    ghdl = find_ghdl()
    if not ghdl:
        hint = INSTALL_HINT.get(sys.platform, INSTALL_HINT["linux"])
        raise SystemExit(f"ghdl not found. Install it:\n  {hint}\n(or set GHDL=/path/to/ghdl)")
    return ghdl


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
        sim = sorted(f for d in [*self.extra_sim, self.root / "sim"] for f in d.glob("*.vhd"))
        return [*sim, *sorted((self.root / "src").glob("*.vhd")), *sorted((self.root / "tb").glob("*.vhd")),
                *[Path(e) for e in extra]]

    def testbenches(self):
        return [f.stem for f in sorted((self.root / "tb").glob("*_tb.vhd"))]

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
            print(f"{'PASS' if passed else 'FAIL'}  {tb}", flush=True)
            if not passed:
                ok = False
                lines = [l for l in log.read_text(errors="replace").splitlines()
                         if any(k in l.lower() for k in ("error", "fail", "assert"))]
                for l in lines[:4]:
                    print(f"        {l}")
        return ok
