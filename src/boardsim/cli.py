"""boardsim: the Zybo Z7 and Basys3 boards without the hardware.

    uv run boardsim doctor              which tools are installed, and how to get the rest
    uv run boardsim test                every testbench and every program
    uv run boardsim zybo --help         Zybo Z7: ARM programs in QEMU, PL in GHDL
"""
import argparse
import subprocess
import sys

from . import __version__, ghdl, qemu, tools


def cmd_setup(args):
    tools.conan_setup()
    print("Conan is set up (default profile + arm-gnu-toolchain recipe).")
    return 0


def cmd_doctor(args):
    print(f"boardsim {__version__}, Python {sys.version.split()[0]} on {sys.platform}\n")
    missing = 0
    for name, finder, purpose, hints in tools.TOOLS:
        path = finder()
        print(f"  {'ok ' if path else '-- '} {name:16s} {path or 'not found'}   ({purpose})")
        if not path:
            missing += 1
            print(f"       install: {hints.get(sys.platform, hints['linux'])}")
    print("\n  The ARM compiler, CMake and Ninja are downloaded by Conan on the first build.")
    return 0


# --- Zybo -----------------------------------------------------------------------
ZYBO_PS = ("zybo", "ps")
ZYBO_PL = ("zybo", "pl")


def zybo_elf(prog):
    return tools.repo_dir(*ZYBO_PS) / "build" / "Debug" / f"{prog}.elf"


def zybo_profile(args):
    return "cortexa9-baremetal-gcc-system" if getattr(args, "system_toolchain", False) else "cortexa9-baremetal-gcc"


def ensure_built(args, prog):
    if not zybo_elf(prog).exists() and tools.conan_build(tools.repo_dir(*ZYBO_PS), zybo_profile(args), test=False):
        raise SystemExit("build failed")
    if not zybo_elf(prog).exists():
        raise SystemExit(f"no program called {prog} (see zybo/ps/examples/)")
    return zybo_elf(prog)


def cmd_zybo_build(args):
    return tools.conan_build(tools.repo_dir(*ZYBO_PS), zybo_profile(args), test=not args.no_test)


def cmd_zybo_test(args):
    ok = True
    if ghdl.find_ghdl():
        print("== Zybo PL: GHDL testbenches")
        ok = ghdl.Design(tools.repo_dir(*ZYBO_PL)).test()
    else:
        print("== Zybo PL: skipped (ghdl not installed; see boardsim doctor)")
    print("== Zybo PS: build + every program in QEMU")
    ok = tools.conan_build(tools.repo_dir(*ZYBO_PS), zybo_profile(args)) == 0 and ok
    return 0 if ok else 1


def cmd_zybo_run(args):
    elf = ensure_built(args, args.program)
    if args.terminal:
        print("Keys + Enter go to the board: 1-4 toggle BTN0-3, 5-8 toggle SW0-3, q quits.")
        return qemu.interactive(str(elf))
    from . import zybo_view
    return zybo_view.run(elf, shift=args.shift, port=args.port, open_browser=not args.no_browser)


def open_wave(design, tb):
    d = ghdl.Design(design)
    d.analyse()
    if not d.elaborate(tb):
        return 1
    d.run(tb, wave=True)
    wave = d.build / f"{tb}.ghw"
    viewer = tools.find_gtkwave()
    if not viewer:
        print(f"Waveform: {wave}\n(gtkwave not found: open it in any viewer, e.g. Surfer)")
        return 0
    save = d.root / "waves" / f"{tb}.gtkw"
    cmd = [viewer, str(wave)] + ([str(save)] if save.exists() else [])
    subprocess.Popen(cmd, cwd=d.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def cmd_zybo_wave(args):
    return open_wave(tools.repo_dir(*ZYBO_PL), args.testbench)


def cmd_test(args):
    return cmd_zybo_test(args)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="boardsim", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="set up Conan (default profile, Arm toolchain recipe)").set_defaults(fn=cmd_setup)
    sub.add_parser("doctor", help="check which tools are installed").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("test", help="run every testbench and program")
    p.add_argument("--system-toolchain", action="store_true", help="use your own arm-none-eabi-gcc")
    p.set_defaults(fn=cmd_test)

    zybo = sub.add_parser("zybo", help="Zybo Z7 (Zynq-7000): ARM in QEMU, PL in GHDL").add_subparsers(dest="zcmd", required=True)
    p = zybo.add_parser("build", help="build the ARM programs (and run them as tests)")
    p.add_argument("--no-test", action="store_true")
    p.add_argument("--system-toolchain", action="store_true", help="use your own arm-none-eabi-gcc (PATH or ARM_GNU_PREFIX)")
    p.set_defaults(fn=cmd_zybo_build)
    p = zybo.add_parser("test", help="PL testbenches + every ARM program in QEMU")
    p.add_argument("--system-toolchain", action="store_true")
    p.set_defaults(fn=cmd_zybo_test)
    p = zybo.add_parser("run", help="run a program on the emulated board (browser board view)")
    p.add_argument("program", nargs="?", default="xgpio_btns", help="e.g. xgpio_blink, xgpio_btns, hello")
    p.add_argument("--terminal", action="store_true", help="text board in this terminal instead of the browser")
    p.add_argument("--shift", type=int, default=1, choices=range(0, 11), metavar="N",
                   help="2^N ns per emulated instruction (default 1 = Zybo speed; 2 = half, for slow machines)")
    p.add_argument("--port", type=int, default=8737)
    p.add_argument("--no-browser", action="store_true", help="don't open a browser")
    p.add_argument("--system-toolchain", action="store_true")
    p.set_defaults(fn=cmd_zybo_run)
    p = zybo.add_parser("wave", help="simulate a PL testbench and open the waveform")
    p.add_argument("testbench", nargs="?", default="zybo_gpio_tb")
    p.set_defaults(fn=cmd_zybo_wave)

    args = ap.parse_args(argv)
    try:
        return args.fn(args) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
