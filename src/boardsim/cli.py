"""boardsim: the Zybo Z7 and Basys3 boards without the hardware.

    uv run boardsim doctor              which tools are installed, and how to get the rest
    uv run boardsim test                every testbench and every program
    uv run boardsim zybo --help         Zybo Z7: ARM programs in QEMU, PL in GHDL
    uv run boardsim basys3 --help       Basys3: VHDL in GHDL, Vivado bitstreams
"""
import argparse
import subprocess
import sys
from pathlib import Path

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


def open_wave(design, tb, extra_sim=()):
    d = ghdl.Design(design, extra_sim=extra_sim)
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


# --- Zybo on the real board: Vivado, Vitis, JTAG --------------------------------------
def zybo_hw_dir():
    return tools.repo_dir("zybo") / "build" / "hw"


def cmd_zybo_xsa(args):
    vivado = tools.require(tools.find_vivado(), "Vivado")
    out = zybo_hw_dir()
    out.mkdir(parents=True, exist_ok=True)
    cmd = [vivado, "-mode", "batch", "-nojournal", "-log", out / f"vivado_{args.board}.log",
           "-source", tools.repo_dir("zybo", "vivado", "zybo_gpio.tcl"), "-tclargs", out, args.board]
    return tools.run(cmd + (["bd"] if args.bd_only else []), cwd=out)


def cmd_zybo_vitis(args):
    vitis = tools.require(tools.find_vitis(), "Vitis")
    xsa = zybo_hw_dir() / f"zybo_{args.board}.xsa"
    if not xsa.exists():
        raise SystemExit(f"{xsa} not found: run `boardsim zybo xsa --board {args.board}` first")
    ws = zybo_hw_dir() / "vitis_ws"
    cmd = [vitis, "-s", tools.repo_dir("zybo", "vitis", "build_apps.py"), xsa, ws, *args.apps]
    return tools.run(cmd, env=tools.xilinx_env(vitis))


def cmd_zybo_jtag(args):
    xsdb = tools.require(tools.find_xsdb(), "XSDB (part of Vitis)")
    cmd = [xsdb, tools.repo_dir("zybo", "vitis", "run_jtag.tcl"), zybo_hw_dir() / "vitis_ws", args.app]
    return tools.run(cmd, env=tools.xilinx_env(xsdb))


# --- Basys3 ---------------------------------------------------------------------
def basys3_dir(args):
    """--dir (your own project with src/, tb/, constraints/) or the repo's basys3/."""
    return Path(args.dir).resolve() if getattr(args, "dir", None) else tools.repo_dir("basys3")


def basys3_design(args):
    shared_sim = [tools.repo_dir("basys3", "sim")] if getattr(args, "dir", None) else []
    return ghdl.Design(basys3_dir(args), extra_sim=shared_sim)


def cmd_basys3_test(args):
    return 0 if basys3_design(args).test(args.only) else 1


def cmd_basys3_wave(args):
    shared_sim = [tools.repo_dir("basys3", "sim")] if args.dir else []
    return open_wave(basys3_dir(args), args.testbench, shared_sim)


def cmd_basys3_run(args):
    from . import basys3_view
    generics = {}
    for g in args.generic or []:
        k, sep, v = g.partition("=")
        if not sep:
            raise SystemExit(f"--generic {g}: expected NAME=VALUE")
        generics[k] = v
    shared_sim = [tools.repo_dir("basys3", "sim")] if args.dir else []
    return basys3_view.run(basys3_dir(args), args.top, shared_sim, generics, clk_hz=args.clk_hz,
                           frame_ms=args.frame_ms, realtime=not args.max_speed, port=args.port,
                           open_browser=not args.no_browser)


def vivado_basys3(args, program):
    vivado = tools.require(tools.find_vivado(), "Vivado")
    cmd = [vivado, "-mode", "batch", "-nojournal", "-nolog", "-source", tools.repo_dir("basys3", "vivado", "build.tcl"),
           "-tclargs", basys3_dir(args), args.top] + (["program"] if program else [])
    return tools.run(cmd, cwd=basys3_dir(args))


def cmd_basys3_bit(args):
    return vivado_basys3(args, program=False)


def cmd_basys3_program(args):
    return vivado_basys3(args, program=True)


def cmd_test(args):
    ok = cmd_zybo_test(args) == 0
    if ghdl.find_ghdl():
        print("== Basys3: GHDL testbenches")
        ok = ghdl.Design(tools.repo_dir("basys3")).test() and ok
    return 0 if ok else 1


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

    boards = ("z7-20", "z7-10")
    p = zybo.add_parser("xsa", help="Vivado: block design, bitstream and .xsa for the real board")
    p.add_argument("--board", choices=boards, default="z7-20")
    p.add_argument("--bd-only", action="store_true", help="stop after the block design (quick check)")
    p.set_defaults(fn=cmd_zybo_xsa)
    p = zybo.add_parser("vitis", help="Vitis: platform + apps from the .xsa (same source as the emulation)")
    p.add_argument("apps", nargs="*", help="default: xgpio_blink xgpio_btns")
    p.add_argument("--board", choices=boards, default="z7-20")
    p.set_defaults(fn=cmd_zybo_vitis)
    p = zybo.add_parser("jtag", help="load the bitstream and an app onto a connected Zybo over JTAG")
    p.add_argument("app", nargs="?", default="xgpio_blink")
    p.set_defaults(fn=cmd_zybo_jtag)

    basys3 = sub.add_parser("basys3", help="Basys3 (Artix-7): VHDL in GHDL, Vivado build").add_subparsers(dest="bcmd", required=True)
    dir_help = "your own design folder with src/, tb/, constraints/ (default: the repo's basys3/)"
    p = basys3.add_parser("test", help="run every testbench in tb/")
    p.add_argument("--dir", help=dir_help)
    p.add_argument("--only", help="only testbenches whose name starts with this")
    p.set_defaults(fn=cmd_basys3_test)
    p = basys3.add_parser("wave", help="simulate a testbench and open the waveform")
    p.add_argument("testbench", nargs="?", default="basys3_top_tb")
    p.add_argument("--dir", help=dir_help)
    p.set_defaults(fn=cmd_basys3_wave)
    p = basys3.add_parser("run", help="run your design on the emulated board (browser board view)")
    p.add_argument("--top", default="basys3_top", help="top entity (ports named as in the Basys3 master XDC)")
    p.add_argument("--dir", help=dir_help)
    p.add_argument("--generic", "-g", action="append", metavar="NAME=VALUE", help="override a generic of the top entity")
    p.add_argument("--clk-hz", type=float, help="simulated clock (default: 250 kHz if the top has a CLK_HZ generic, else 100 MHz)")
    p.add_argument("--frame-ms", type=float, default=10.0, help="simulated time per screen update (default 10)")
    p.add_argument("--max-speed", action="store_true", help="don't slow down to real time when the simulation is faster")
    p.add_argument("--port", type=int, default=8738)
    p.add_argument("--no-browser", action="store_true", help="don't open a browser")
    p.set_defaults(fn=cmd_basys3_run)
    for name, fn, text in (("bit", cmd_basys3_bit, "Vivado: build the bitstream"),
                           ("program", cmd_basys3_program, "Vivado: build and load it onto a connected Basys3")):
        p = basys3.add_parser(name, help=text)
        p.add_argument("--top", default="basys3_top", help="top entity; constraints/<top>.xdc must exist")
        p.add_argument("--dir", help=dir_help)
        p.set_defaults(fn=fn)

    args = ap.parse_args(argv)
    try:
        return args.fn(args) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
