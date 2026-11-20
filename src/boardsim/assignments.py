"""Your own work: one folder per assignment in assignments/, made by `boardsim new`.

    assignments/<name>/            a Zybo assignment          a Basys3 assignment
        pl/src, pl/tb,             VHDL for the PL            -
        pl/constraints
        ps/                        C for the ARM              -
        src/, tb/, constraints/    -                          VHDL, testbenches, pins
        build/                     everything generated (GHDL, Vivado, Vitis); not in git

Every board command finds an assignment by its name, so `boardsim zybo test lab1` or
`boardsim basys3 run lab2` work from anywhere in the repository.
"""
import re
from pathlib import Path

from . import term, tools

TEMPLATES = Path(__file__).resolve().parent / "templates"
KINDS = {"zybo": "zybo", "zybo-gpio": "zybo", "basys3": "basys3"}   # template -> board

# Names already used by the repo's own programs and libraries (CMake targets share one namespace).
TAKEN = {"hello", "asm_sum", "axi_leds", "xgpio_blink", "xgpio_btns", "bsp", "zybo_model", "test", "all",
         "basys3", "zybo", "basys3_top", "counter", "seven_seg", "axi_gpio", "axi_lite_leds", "zybo_gpio_top"}
# VHDL reserved words that look like plausible assignment names.
VHDL_RESERVED = {"abs", "access", "after", "alias", "all", "and", "architecture", "array", "assert", "begin",
                 "block", "body", "buffer", "bus", "case", "component", "configuration", "constant", "else",
                 "end", "entity", "exit", "file", "for", "function", "generate", "generic", "group", "if",
                 "in", "inout", "is", "label", "library", "linkage", "loop", "map", "mod", "nand", "new",
                 "next", "nor", "not", "null", "of", "on", "open", "or", "others", "out", "package", "port",
                 "procedure", "process", "range", "record", "register", "rem", "report", "return", "select",
                 "signal", "subtype", "then", "to", "type", "units", "until", "use", "variable", "wait",
                 "when", "while", "with", "xor", "xnor", "context", "force", "release", "parameter"}


def root():
    d = tools.ROOT / "assignments"
    d.mkdir(exist_ok=True)
    return d


def board_of(d):
    """'zybo', 'basys3' or None, from what the folder contains."""
    d = Path(d)
    if (d / "ps").is_dir() or (d / "pl").is_dir():
        return "zybo"
    if (d / "src").is_dir():
        return "basys3"
    return None


def all_of(board):
    return [d for d in sorted(root().iterdir()) if d.is_dir() and board_of(d) == board]


def find(name, board=None):
    """The folder of assignment <name> (for <board>, if given), or None."""
    d = root() / name
    if d.is_dir() and board_of(d) and (board is None or board_of(d) == board):
        return d
    return None


def check_name(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or "__" in name or name.endswith("_"):
        raise SystemExit(f"'{name}': use lowercase letters, digits and single underscores, starting with a "
                         "letter (it becomes a VHDL entity, a C identifier and a program name), e.g. lab1")
    if name in TAKEN or name in VHDL_RESERVED:
        raise SystemExit(f"'{name}' is already used in the repository or reserved in VHDL; pick another name")


def new(template, name):
    check_name(name)
    dest = root() / name
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    src = TEMPLATES / template
    subst = {"{{name}}": name, "{{NAME}}": name.upper()}

    def fill(text):
        for k, v in subst.items():
            text = text.replace(k, v)
        return text

    for f in sorted(src.rglob("*")):
        if f.is_dir() or f.name == "__pycache__":
            continue
        out = dest / fill(str(f.relative_to(src)))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(fill(f.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    return dest


def print_next_steps(template, name, dest):
    rel = dest.relative_to(tools.ROOT).as_posix()
    print(term.ok("Created ") + term.path(rel))
    for f in sorted(p for p in dest.rglob("*") if p.is_file()):
        print(f"  {f.relative_to(dest).as_posix()}")
    steps = {
        "zybo": [
            (f"uv run boardsim zybo test {name}", "VHDL testbench in GHDL + the C program in QEMU"),
            (f"uv run boardsim zybo wave {name}_tb", "the testbench's waveform"),
            (f"uv run boardsim zybo run {name} --terminal", "the C program in QEMU"),
            (f"uv run boardsim zybo xsa {name}", "Vivado: block design with your peripheral -> .xsa"),
            (f"uv run boardsim zybo vitis {name}", "Vitis: platform + your program"),
            (f"uv run boardsim zybo jtag {name}", "run it on a connected Zybo"),
        ],
        "zybo-gpio": [
            (f"uv run boardsim zybo run {name}", "your program on the emulated board, in the browser"),
            (f"uv run boardsim zybo test {name}", "its test (KEYS / EXPECT in ps/CMakeLists.txt)"),
            (f"uv run boardsim zybo xsa {name}", "Vivado: the tutorial's block design -> .xsa"),
            (f"uv run boardsim zybo vitis {name}", "Vitis: platform + your program"),
            (f"uv run boardsim zybo jtag {name}", "run it on a connected Zybo"),
        ],
        "basys3": [
            (f"uv run boardsim basys3 test {name}", "the testbenches in tb/"),
            (f"uv run boardsim basys3 run {name}", "your design on the emulated board, in the browser"),
            (f"uv run boardsim basys3 wave {name}_tb", "a testbench's waveform"),
            (f"uv run boardsim basys3 program {name}", "Vivado: bitstream, loaded onto a connected Basys3"),
        ],
    }[template]
    print("\nNext:")
    width = max(len(c) for c, _ in steps)
    for cmd, what in steps:
        print(f"  {term.head(cmd.ljust(width))}   {term.dim(what)}")
    print(term.dim("\nThe whole workflow: HOW-TO-USE.md"))
