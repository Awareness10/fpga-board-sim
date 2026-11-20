"""boardsim: the Zybo and Basys3 boards without the hardware.

    uv run boardsim doctor              which tools are installed, and how to get the rest
    uv run boardsim new zybo lab1       start an assignment in assignments/lab1 (see HOW-TO-USE.md)
    uv run boardsim test                every testbench and every program
    uv run boardsim zybo --help         Zybo: ARM programs in QEMU, PL in GHDL
    uv run boardsim basys3 --help       Basys3: VHDL in GHDL, Vivado bitstreams
"""
import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__, assignments, ghdl, qemu, term, tools


def cmd_setup(args):
    tools.conan_setup()
    print(term.ok("Conan is set up") + " (default profile + arm-gnu-toolchain recipe).")
    return 0


def cmd_install(args):
    {"ghdl": ghdl.install, "surfer": tools.install_surfer}[args.tool](force=args.force)
    return 0


def tool_version(exe):
    """First line of `exe --version`, or why there is none (e.g. blocked from starting)."""
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else f"exit {r.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"won't start: {e}"


def cmd_doctor(args):
    print(term.head(f"boardsim {__version__}") + f", Python {sys.version.split()[0]} on {sys.platform}\n")
    for name, finder, purpose, hints in tools.TOOLS:
        path = finder()
        mark = term.ok("ok ") if path else term.bad("-- ")
        where = term.path(path) if path else term.warn("not found")
        if path and name.startswith("qemu"):
            where += term.dim(f"  ({tool_version(path)})")
        print(f"  {mark} {name:16s} {where}   {term.dim(f'({purpose})')}")
        if not path:
            print(f"       install: {term.head(hints.get(sys.platform, hints['linux']))}")
    print(term.dim("\n  The ARM compiler, CMake and Ninja are downloaded by Conan on the first build."))
    return 0


def cmd_new(args):
    if args.gpio and args.board != "zybo":
        raise SystemExit("--gpio is only for zybo")
    template = "zybo-gpio" if args.gpio else args.board
    dest = assignments.new(template, args.name)
    assignments.print_next_steps(template, args.name, dest)
    return 0


def open_wave(d, tb):
    """Simulate testbench <tb> of ghdl.Design <d> and open the waveform."""
    d.analyse()
    if not d.elaborate(tb):
        return 1
    d.run(tb, wave=True)
    wave = d.build / f"{tb}.ghw"
    kind, viewer = tools.find_viewer()
    print(f"Waveform: {term.path(wave)}")
    if not viewer:
        print(term.warn("No waveform viewer found: ") + "uv run boardsim install surfer  (or install GTKWave)")
        return 0
    save = d.root / "waves" / f"{tb}.gtkw"          # GTKWave's saved signal layout, if there is one
    cmd = [viewer, str(wave)] + ([str(save)] if kind == "gtkwave" and save.exists() else [])
    if kind == "surfer" and save.exists():
        print(term.dim("(Surfer: add signals from the scope list on the left; the saved layout is GTKWave's)"))
    subprocess.Popen(cmd, cwd=d.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def wave_in(designs, name, where):
    """Open testbench <name> from the first design that has it. <name> may also be an
    assignment, for its first testbench."""
    designs = list(designs)
    for d in designs:
        if ghdl.vhdl_file(d.root / "tb", name):
            return open_wave(d, name)
    for d in designs:
        if name in (d.root.name, d.root.parent.name) and d.testbenches():
            return open_wave(d, d.testbenches()[0])
    raise SystemExit(f"no testbench called {name}.vhdl in {where}")


# --- Zybo -----------------------------------------------------------------------
ZYBO_PS = ("zybo", "ps")
ZYBO_PL = ("zybo", "pl")


def zybo_assignment(name):
    d = assignments.find(name, "zybo")
    if not d:
        raise SystemExit(f"no Zybo assignment called '{name}' in assignments/ "
                         f"(start one with: uv run boardsim new zybo {name})")
    return d


def zybo_pl_designs(only=None):
    """GHDL designs: the repo's zybo/pl, and each Zybo assignment's pl/ (or just <only>'s)."""
    out = [] if only else [ghdl.Design(tools.repo_dir(*ZYBO_PL))]
    for d in [zybo_assignment(only)] if only else assignments.all_of("zybo"):
        if (d / "pl" / "src").is_dir():
            # The assignment's testbenches can use axil_master_pkg from zybo/pl/sim.
            out.append(ghdl.Design(d / "pl", extra_sim=[tools.repo_dir(*ZYBO_PL, "sim")], build=d / "build" / "pl"))
    return out


def zybo_elf(prog):
    return tools.repo_dir(*ZYBO_PS) / "build" / "Debug" / f"{prog}.elf"


def zybo_profile(args):
    return "cortexa9-baremetal-gcc-system" if getattr(args, "system_toolchain", False) else "cortexa9-baremetal-gcc"


def ensure_built(args, prog):
    # Always (re)build: incremental, about a second, and your latest edits are what runs.
    if tools.conan_build(tools.repo_dir(*ZYBO_PS), zybo_profile(args), test=False):
        raise SystemExit("build failed")
    if not zybo_elf(prog).exists():
        raise SystemExit(f"no program called {prog} (see zybo/ps/examples/ and assignments/)")
    return zybo_elf(prog)


def cmd_zybo_build(args):
    return tools.conan_build(tools.repo_dir(*ZYBO_PS), zybo_profile(args), test=not args.no_test)


def cmd_zybo_test(args):
    name = getattr(args, "assignment", None)
    if name:
        zybo_assignment(name)
    ok = True
    if ghdl.find_ghdl():
        for d in zybo_pl_designs(name):
            print(term.head(f"== Zybo PL: GHDL testbenches in {d.root.relative_to(tools.ROOT).as_posix()}"))
            ok = d.test() and ok
    else:
        print(term.warn("== Zybo PL: skipped (ghdl not installed; see boardsim doctor)"))
    if name and not (zybo_assignment(name) / "ps" / "CMakeLists.txt").exists():
        return 0 if ok else 1
    print(term.head(f"== Zybo PS: build + {name if name else 'every program'} in QEMU"))
    ok = tools.conan_build(tools.repo_dir(*ZYBO_PS), zybo_profile(args), only=name) == 0 and ok
    return 0 if ok else 1


def cmd_zybo_run(args):
    elf = ensure_built(args, args.program)
    if args.terminal:
        print("Keys + Enter go to the board: 1-4 toggle BTN0-3, 5-8 toggle SW0-3, q quits.")
        return qemu.interactive(str(elf))
    from . import zybo_view
    return zybo_view.run(elf, shift=args.shift, port=args.port, open_browser=not args.no_browser)


def cmd_zybo_wave(args):
    return wave_in(zybo_pl_designs(), args.testbench, "zybo/pl/tb or assignments/*/pl/tb")


# --- Zybo on the real board: Vivado, Vitis, JTAG --------------------------------------
def zybo_hw_dir(assignment_dir=None):
    """Where Vivado and Vitis put their output: the assignment's build/hw, or zybo/build/hw."""
    return assignment_dir / "build" / "hw" if assignment_dir else tools.repo_dir("zybo") / "build" / "hw"


def zybo_hw_name(board):
    """Vivado project / .xsa name, as zybo/vivado/zybo_design.tcl names it."""
    return "zybo" if board == "zybo" else f"zybo_{board}"


def cmd_zybo_xsa(args):
    vivado = tools.require(tools.find_vivado(), "Vivado")
    d = zybo_assignment(args.assignment) if args.assignment else None
    out = zybo_hw_dir(d)
    out.mkdir(parents=True, exist_ok=True)
    cmd = [vivado, "-mode", "batch", "-nojournal", "-log", out / f"vivado_{args.board}.log",
           "-source", tools.repo_dir("zybo", "vivado", "zybo_design.tcl"),
           "-tclargs", out, args.board, "bd" if args.bd_only else "all"]
    if d and (d / "pl" / "src").is_dir():          # your peripheral instead of the tutorial's AXI GPIO
        top = args.top or d.name
        cmd += [d / "pl" / "src", top, d / "pl" / "constraints" / f"{top}.xdc"]
    return tools.run(cmd, cwd=out)


def cmd_zybo_vitis(args):
    vitis = tools.require(tools.find_vitis(), "Vitis")
    found = [assignments.find(a, "zybo") for a in args.apps]
    d = next((f for f in found if f), None)
    if d and len(args.apps) > 1:
        raise SystemExit("one assignment at a time: uv run boardsim zybo vitis <assignment>")
    specs = [f"{a}={f / 'ps'}" if f else a for a, f in zip(args.apps, found)]
    xsa = zybo_hw_dir(d) / f"{zybo_hw_name(args.board)}.xsa"
    if not xsa.exists():
        name = f"{d.name} " if d else ""
        raise SystemExit(f"{xsa} not found: run `uv run boardsim zybo xsa {name}--board {args.board}` first")
    ws = zybo_hw_dir(d) / "vitis_ws"
    cmd = [vitis, "-s", tools.repo_dir("zybo", "vitis", "build_apps.py"), xsa, ws, *specs]
    return tools.run(cmd, env=tools.xilinx_env(vitis))


def cmd_zybo_jtag(args):
    xsdb = tools.require(tools.find_xsdb(), "XSDB (part of Vitis)")
    ws = zybo_hw_dir(assignments.find(args.app, "zybo")) / "vitis_ws"
    cmd = [xsdb, tools.repo_dir("zybo", "vitis", "run_jtag.tcl"), ws, args.app]
    # stdin not a terminal: Xilinx's xsdb launcher then skips its bundled rlwrap (line editing
    # we don't need for a script), which warns about $TERM on distros whose terminfo it can't read.
    return tools.run(cmd, env=tools.xilinx_env(xsdb), stdin=subprocess.DEVNULL)


# --- Basys3 ---------------------------------------------------------------------
def basys3_dir(args):
    """The design folder: an assignment by name, a folder (--dir or a path), or the repo's basys3/."""
    target = getattr(args, "design", None) or getattr(args, "dir", None)
    if not target:
        return tools.repo_dir("basys3")
    d = assignments.find(target, "basys3")
    if d:
        return d
    p = Path(target).resolve()
    if not (p / "src").is_dir():
        raise SystemExit(f"'{target}' is neither a Basys3 assignment in assignments/ nor a folder with src/ "
                         f"(start one with: uv run boardsim new basys3 {target})")
    return p


def basys3_design(d):
    """GHDL design for folder <d>; designs outside basys3/ can use basys3_sim_pkg from basys3/sim."""
    repo = tools.repo_dir("basys3")
    extra = [] if d == repo else [repo / "sim"]
    return ghdl.Design(d, extra_sim=extra)


def basys3_top(args, d):
    """--top, else the entity named like the folder (as `boardsim new basys3` makes it), else basys3_top."""
    if args.top:
        return args.top
    return d.name if ghdl.vhdl_file(d / "src", d.name) else "basys3_top"


def cmd_basys3_test(args):
    return 0 if basys3_design(basys3_dir(args)).test(args.only) else 1


def cmd_basys3_wave(args):
    if args.dir:
        designs = [basys3_design(basys3_dir(args))]
    else:
        designs = [basys3_design(d) for d in [tools.repo_dir("basys3"), *assignments.all_of("basys3")]]
    return wave_in(designs, args.testbench, args.dir or "basys3/tb or assignments/*/tb")


def cmd_basys3_run(args):
    from . import basys3_view
    generics = {}
    for g in args.generic or []:
        k, sep, v = g.partition("=")
        if not sep:
            raise SystemExit(f"--generic {g}: expected NAME=VALUE")
        generics[k] = v
    d = basys3_dir(args)
    return basys3_view.run(d, basys3_top(args, d), basys3_design(d).extra_sim, generics, clk_hz=args.clk_hz,
                           frame_ms=args.frame_ms, realtime=not args.max_speed, port=args.port,
                           open_browser=not args.no_browser)


def vivado_basys3(args, program):
    vivado = tools.require(tools.find_vivado(), "Vivado")
    d = basys3_dir(args)
    cmd = [vivado, "-mode", "batch", "-nojournal", "-nolog", "-source", tools.repo_dir("basys3", "vivado", "build.tcl"),
           "-tclargs", d, basys3_top(args, d)] + (["program"] if program else [])
    return tools.run(cmd, cwd=d)


def cmd_basys3_bit(args):
    return vivado_basys3(args, program=False)


def cmd_basys3_program(args):
    return vivado_basys3(args, program=True)


def cmd_test(args):
    ok = cmd_zybo_test(args) == 0
    if ghdl.find_ghdl():
        for d in [tools.repo_dir("basys3"), *assignments.all_of("basys3")]:
            print(term.head(f"== Basys3: GHDL testbenches in {d.relative_to(tools.ROOT).as_posix()}"))
            ok = basys3_design(d).test() and ok
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="boardsim", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="set up Conan (default profile, Arm toolchain recipe)").set_defaults(fn=cmd_setup)
    sub.add_parser("doctor", help="check which tools are installed").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("new", help="start an assignment in assignments/<name> from a working template")
    p.add_argument("board", choices=["zybo", "basys3"])
    p.add_argument("name", help="e.g. lab1: lowercase letters, digits, underscores")
    p.add_argument("--gpio", action="store_true",
                   help="zybo: C only, on the tutorial's AXI GPIO (board view), instead of your own AXI peripheral")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("test", help="run every testbench and program (the repo's and your assignments')")
    p.add_argument("--system-toolchain", action="store_true", help="use your own arm-none-eabi-gcc")
    p.set_defaults(fn=cmd_test)

    p = sub.add_parser("install", help="download a tool's official build into your user folder")
    p.add_argument("tool", choices=["ghdl", "surfer"], help="ghdl (VHDL simulator) or surfer (waveform viewer)")
    p.add_argument("--force", action="store_true", help="download again even if it is installed")
    p.set_defaults(fn=cmd_install)

    assignment_help = "an assignment in assignments/ (default: the repo's own examples)"
    zybo = sub.add_parser("zybo", help="Zybo (Zynq-7000): ARM in QEMU, PL in GHDL").add_subparsers(dest="zcmd", required=True)
    p = zybo.add_parser("build", help="build the ARM programs (and run them as tests)")
    p.add_argument("--no-test", action="store_true")
    p.add_argument("--system-toolchain", action="store_true", help="use your own arm-none-eabi-gcc (PATH or ARM_GNU_PREFIX)")
    p.set_defaults(fn=cmd_zybo_build)
    p = zybo.add_parser("test", help="PL testbenches + ARM programs in QEMU (all, or one assignment's)")
    p.add_argument("assignment", nargs="?", help="only this assignment (default: everything)")
    p.add_argument("--system-toolchain", action="store_true")
    p.set_defaults(fn=cmd_zybo_test)
    p = zybo.add_parser("run", help="run a program on the emulated board (browser board view)")
    p.add_argument("program", nargs="?", default="xgpio_btns", help="an assignment, or e.g. xgpio_blink, xgpio_btns, hello")
    p.add_argument("--terminal", action="store_true", help="text board in this terminal instead of the browser")
    p.add_argument("--shift", type=int, default=1, choices=range(0, 11), metavar="N",
                   help="2^N ns per emulated instruction (default 1 = Zybo speed; 2 = half, for slow machines)")
    p.add_argument("--port", type=int, default=8737)
    p.add_argument("--no-browser", action="store_true", help="don't open a browser")
    p.add_argument("--system-toolchain", action="store_true")
    p.set_defaults(fn=cmd_zybo_run)
    p = zybo.add_parser("wave", help="simulate a PL testbench and open the waveform")
    p.add_argument("testbench", nargs="?", default="zybo_gpio_tb", help="e.g. lab1_tb (or an assignment's name)")
    p.set_defaults(fn=cmd_zybo_wave)

    boards = ("zybo", "z7-10", "z7-20")   # the course's original Zybo; Zybo Z7-10/-20 (outside the course)
    board_help = "zybo: the original Zybo (default, the course's board); z7-10, z7-20: Zybo Z7, outside the course"
    p = zybo.add_parser("xsa", help="Vivado: block design, bitstream and .xsa for the real board")
    p.add_argument("assignment", nargs="?", help=assignment_help)
    p.add_argument("--top", help="your peripheral's entity (default: the assignment's name)")
    p.add_argument("--board", choices=boards, default="zybo", help=board_help)
    p.add_argument("--bd-only", action="store_true", help="stop after the block design (quick check)")
    p.set_defaults(fn=cmd_zybo_xsa)
    p = zybo.add_parser("vitis", help="Vitis: platform + apps from the .xsa (same source as the emulation)")
    p.add_argument("apps", nargs="*", default=["xgpio_blink", "xgpio_btns"],
                   help="an assignment, or examples (default: xgpio_blink xgpio_btns)")
    p.add_argument("--board", choices=boards, default="zybo", help=board_help)
    p.set_defaults(fn=cmd_zybo_vitis)
    p = zybo.add_parser("jtag", help="load the bitstream and an app onto a connected Zybo over JTAG")
    p.add_argument("app", nargs="?", default="xgpio_blink", help="an assignment, or an example")
    p.set_defaults(fn=cmd_zybo_jtag)

    basys3 = sub.add_parser("basys3", help="Basys3 (Artix-7): VHDL in GHDL, Vivado build").add_subparsers(dest="bcmd", required=True)
    design_help = "an assignment in assignments/, or a folder with src/ (default: the repo's basys3/)"
    dir_help = "same as the design argument (a folder with src/, tb/, constraints/)"
    top_help = "top entity (default: the one named like the folder, else basys3_top)"
    p = basys3.add_parser("test", help="run every testbench in tb/")
    p.add_argument("design", nargs="?", help=design_help)
    p.add_argument("--dir", help=dir_help)
    p.add_argument("--only", help="only testbenches whose name starts with this")
    p.set_defaults(fn=cmd_basys3_test)
    p = basys3.add_parser("wave", help="simulate a testbench and open the waveform")
    p.add_argument("testbench", nargs="?", default="basys3_top_tb", help="e.g. lab2_tb (or an assignment's name)")
    p.add_argument("--dir", help=dir_help)
    p.set_defaults(fn=cmd_basys3_wave)
    p = basys3.add_parser("run", help="run your design on the emulated board (browser board view)")
    p.add_argument("design", nargs="?", help=design_help)
    p.add_argument("--top", help=top_help + "; ports named as in the Basys3 master XDC")
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
        p.add_argument("design", nargs="?", help=design_help)
        p.add_argument("--top", help=top_help + "; constraints/<top>.xdc must exist")
        p.add_argument("--dir", help=dir_help)
        p.set_defaults(fn=fn)

    args = ap.parse_args(argv)
    try:
        return args.fn(args) or 0
    except KeyboardInterrupt:
        return 130
    except SystemExit as e:
        if isinstance(e.code, str):            # our own error messages
            print(term.bad("error: ", 2) + e.code, file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
