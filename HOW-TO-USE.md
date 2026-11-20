# How to use this for your assignments

This repository is a development environment for the Zybo and Basys3 assignments. You
write VHDL and C in **one folder per assignment**, test them on your own computer without
the board, and build them for the real board from the same files, all through one tool,
`boardsim`.

```
assignments/lab1/      ← your work: VHDL, testbenches, C, pin constraints
        │
        ├── emulated:    GHDL runs your testbenches, QEMU runs your C program
        └── real board:  Vivado builds the bitstream, Vitis builds the program, JTAG runs it
```

Run every command from the repository folder, as `uv run boardsim ...`.

## 1. One-time setup

Install uv, QEMU and GHDL as described in the [README](README.md#install) (Vivado/Vitis
2023.2 only if you'll use the real board), then:

```sh
uv run boardsim doctor     # shows what's installed and how to get the rest
uv run boardsim setup      # Conan: downloads the ARM compiler on the first build
uv run boardsim test       # everything should say PASS
```

## 2. Start an assignment

Choose the kind that matches the assignment:

| The assignment is about... | Command | You get |
|---|---|---|
| **Zybo: your own hardware + C** (a VHDL peripheral the ARM uses over AXI) | `uv run boardsim new zybo lab1` | an AXI-Lite peripheral (LEDs, switches, buttons), its testbench, a C driver and program |
| **Zybo: C only**, on the tutorial's block design (AXI GPIO for LEDs and buttons) | `uv run boardsim new zybo lab1 --gpio` | a C program using `XGpio`, which runs in the live board view in your browser |
| **Basys3: VHDL only** | `uv run boardsim new basys3 lab1` | a top entity (switches → LEDs, a blinking LED), its testbench and pin constraints |

The name (`lab1` here) becomes the folder, the VHDL entity and the program name: use
lowercase letters, digits and `_`. The command prints the files it made and the next
commands to run. The new assignment already works: its tests pass before you change
anything, so you start from something working and change it a step at a time.

Each assignment is self-contained:

```
assignments/lab1/                     (zybo)          assignments/lab1/          (basys3)
  pl/src/lab1.vhdl          the peripheral               src/lab1.vhdl             top entity
  pl/tb/lab1_tb.vhdl        its testbench                tb/lab1_tb.vhdl           testbench
  pl/constraints/lab1.xdc  pins of its board I/O        constraints/lab1.xdc     pins
  ps/main.c                the program                  build/                   generated
  ps/lab1.h                the driver (register map)
  ps/CMakeLists.txt        which .c files make the program
  build/                   generated: GHDL, Vivado, Vitis (not in git)
```

A `--gpio` assignment has only `ps/` (the hardware is the tutorial's AXI GPIO).

**Adding files:** any `.vhdl` in `src/` or `pl/src/` is picked up automatically, and any
`*_tb.vhdl` in `tb/` is a testbench (`.vhd` works too). A new `.c` or `.S` file goes in
the list in `ps/CMakeLists.txt`.

## 3. Zybo: your own peripheral + C

The Zynq has two halves: the **PL** (FPGA fabric: your VHDL) and the **PS** (the ARM:
your C). The ARM sees your peripheral's registers as memory at `0x43C0_0000`. QEMU can't
run VHDL, so in the emulator each half is tested on its own, against the **same register
map**. They only run together on the real board:

```
pl/src/lab1.vhdl ── tested by ── pl/tb/lab1_tb.vhdl      (GHDL; the testbench acts as the ARM)
        │
   register map  (the comment at the top of lab1.vhdl = the struct in ps/lab1.h)
        │
ps/lab1.h + main.c ── tested in QEMU against a fake register block in RAM
```

A good order to work in:

1. **Decide the register map.** Write it in the comment at the top of `pl/src/lab1.vhdl`:
   offset, name, read/write, what the bits mean. Keep the `ID` register: it lets the C
   code check that the right bitstream is loaded.
2. **VHDL.** Change the registers in the two `case` statements (`write_ch`, `read_ch`)
   and the ports under "board I/O". Keep the `s_axi_*` port names: Vivado recognises the
   AXI interface from them.
3. **Testbench.** In `pl/tb/lab1_tb.vhdl`, `wr(addr, value)` and `rd(addr, expected)` do
   AXI writes and reads like the ARM would, and stop the test on a wrong value. Add a
   few lines per register, then:
   ```sh
   uv run boardsim zybo test lab1         # PASS/FAIL for the testbench (and the C test)
   uv run boardsim zybo wave lab1_tb      # the waveform, when you need to see why
   ```
4. **Driver.** Make the struct in `ps/lab1.h` match the register map, one
   `volatile uint32_t` per register, in order, and write small functions for what the
   program needs.
5. **Program.** `ps/main.c` has two halves, chosen automatically:
   - `#ifdef ZYBO_BOARD_MODEL` (the emulator): the driver runs against a fake register
     block in RAM. Use it to check that the driver writes and reads the right bits
     (`EXPECT(...)`).
   - `#else` (the board, built by Vitis): the real program, using the real peripheral.
   ```sh
   uv run boardsim zybo test lab1              # both: the VHDL testbench and the C test
   uv run boardsim zybo run lab1 --terminal    # see the program's output
   ```
6. **The real board** (section 6): `zybo xsa lab1`, `zybo vitis lab1`, `zybo jtag lab1`.

Your peripheral isn't shown in the browser board view: the board view models only the
tutorial's AXI GPIO. Use `--terminal`.

## 4. Zybo: C only (`--gpio`)

The hardware is the tutorial's: `axi_gpio_0` at `0x4120_0000`, channel 1 = LD3..LD0,
channel 2 = BTN3..BTN0. You write C with the Xilinx `XGpio` driver, exactly as in Vitis.

```sh
uv run boardsim zybo run lab1          # the board view in your browser: click buttons, watch LEDs
uv run boardsim zybo test lab1         # the scripted test
```

In the board view, hold keys `1`–`4` (or click) for BTN0–BTN3; **PS-SRST** restarts the
program. Every `zybo run` rebuilds first, so what runs is what you just saved.

The test is in `ps/CMakeLists.txt`: `KEYS` are typed into the board (`1`–`4` toggle
BTN0–3, `5`–`8` SW0–3, `.` waits, `q` quits) and `EXPECT` is a regular expression the
board's output must match. Change them when the program's behaviour changes. Programs
that loop forever need a `q` in `KEYS` to end the test, or `NO_TEST` to have no test.

## 5. Basys3: VHDL only

```sh
uv run boardsim basys3 test lab1       # every testbench in tb/
uv run boardsim basys3 run lab1        # your design on the emulated board, in the browser
uv run boardsim basys3 wave lab1_tb    # a testbench's waveform
```

- **Port names** must be the ones in Digilent's master XDC (`clk`, `sw`, `led`,
  `btnC`/`btnU`/`btnL`/`btnR`/`btnD`, `seg`, `dp`, `an`). The board view connects ports
  by these names; narrower vectors such as `led(7 downto 0)` are fine.
- **Compute every clock divider from the `CLK_HZ` generic**, never from a fixed
  `100_000_000`. The board view then runs your design on a slower clock at real speed
  (GHDL can't simulate 100 MHz in real time), and testbenches can use a small value.
- The top entity is the one named like the folder (`lab1`); pass `--top` for another.

More on the board view: [basys3/README.md](basys3/README.md).

## 6. On the real board

Needs Vivado/Vitis 2023.2 (Windows or Linux). Everything ends up in `assignments/lab1/build/`.

**Zybo** (jumper JP5 on JTAG, USB in the PROG/UART port, power on):

```sh
uv run boardsim zybo xsa lab1      # Vivado: block design -> bitstream -> .xsa       (~5 min)
uv run boardsim zybo vitis lab1    # Vitis: platform from the .xsa + your ps/ files   (~5 min)
uv run boardsim zybo jtag lab1     # load the bitstream and the program, and run it
```

- `zybo xsa` builds what you would click in Vivado: Zynq PS with the board preset; your
  peripheral (`Add Module`) on `M_AXI_GP0` by connection automation, with its other ports
  made external and pinned by `pl/constraints/lab1.xdc`. For a `--gpio` assignment it
  builds the tutorial's design instead. It prints `CHECK:` lines: compare the base address
  with the one in your header.
- `zybo vitis` imports every `.c`/`.h`/`.S` in `ps/` unchanged; there,
  `ZYBO_BOARD_MODEL` isn't defined, so the board half of `main.c` is built.
- The program's output appears on the board's serial port at 115200 baud
  (Linux: usually `/dev/ttyUSB1`, e.g. `screen /dev/ttyUSB1 115200`; Windows: a COM port
  in PuTTY).
- To look at or change the design in the IDEs, open
  `assignments/lab1/build/hw/zybo/zybo.xpr` in Vivado and `assignments/lab1/build/hw/vitis_ws`
  as the Vitis workspace. Note that `zybo xsa` recreates the project, so changes you
  clicked in the GUI are gone the next time you run it. Make changes you want to keep in
  your files.

**Basys3** (USB connected, power on):

```sh
uv run boardsim basys3 program lab1    # bitstream, loaded onto the board
uv run boardsim basys3 bit lab1        # only the bitstream (build/vivado/lab1/lab1.bit)
```

Every port of the top entity needs its pins in `constraints/lab1.xdc`; copy lines from
`basys3/constraints/Basys-3-Master.xdc`.

Cable drivers, the serial console, and the same steps by hand in the GUI:
[zybo/README.md](zybo/README.md#on-the-real-board).

## 7. Commands

| | Zybo | Basys3 |
|---|---|---|
| start an assignment | `new zybo <name> [--gpio]` | `new basys3 <name>` |
| testbenches (+ C tests) | `zybo test <name>` | `basys3 test <name>` |
| waveform | `zybo wave <name>_tb` | `basys3 wave <name>_tb` |
| run on the emulated board | `zybo run <name>` (`--terminal` for text) | `basys3 run <name>` |
| bitstream | `zybo xsa <name>` | `basys3 bit <name>` |
| program the board | `zybo vitis <name>`, then `zybo jtag <name>` | `basys3 program <name>` |
| everything, all assignments | `test` | `test` |

Without a name, the commands work on the repository's own examples (the tutorial's
`xgpio_blink`/`xgpio_btns`, `basys3_top`). Add `--help` to any command for its options.

## 8. When something goes wrong

- **A testbench says FAIL:** the lines under it show the failed check. Run
  `wave <tb>` to see the signals.
- **"did not finish within 10ms of simulated time":** a test run stops after 10 ms of
  simulated time. End the testbench with `std.env.finish` and keep it short: test a
  divider with a small `CLK_HZ`, not by simulating a whole second at 100 MHz.
- **C test FAIL with `CHECK failed`:** an `EXPECT` in `main.c` (or `CHECK`) didn't hold;
  the line number is printed. `TIMEOUT` means the program didn't end: add `q` to `KEYS`
  or return from `main`.
- **`zybo run` is slow, or says "QEMU is N s behind":** your computer can't emulate at
  the Zybo's speed; use `--shift 2`.
- **On the board, "not found at 0x43c00000":** the bitstream isn't loaded, or Vivado
  chose another address: check the `CHECK: ... base` line from `zybo xsa` against
  `<NAME>_BASE` in your header.
- **Changed the register map, but the board misbehaves:** the VHDL, the testbench's
  `REG_*` constants and the header's struct must all agree. The testbench and the C
  test only catch mistakes in their own half.

## Saving your work

Commit `assignments/<name>/` (for example in your own fork of this repository); `build/`
folders are ignored by git. To start over, delete the folder and run `boardsim new` again.
