# Zybo (Zynq-7000)

The Zybo's Zynq-7000 chip has two halves, and each one is handled differently here:

| Half | What it is | Here, without a board | Folder |
|---|---|---|---|
| **PS** (Processing System) | 2× ARM Cortex-A9, DDR, UART, timers: fixed silicon | **emulated**: real ARM code runs in QEMU's `xilinx-zynq-a9` machine | `ps/` |
| **PL** (Programmable Logic) | Artix-7-class FPGA fabric: your VHDL | **simulated**: GHDL testbenches | `pl/` |

The PS talks to the PL over **AXI**: the ARM sees PL registers as memory, so a store to
`0x4120_0000` becomes an AXI write into the FPGA. QEMU has no FPGA fabric, so each side is
tested on its own, against the same register map:

```
 C program + driver (ps/)                     VHDL (pl/src/)
   runs in QEMU against a C model of            tested in GHDL by testbenches that
   the PL design (ps/model/zybo_board.c)        act as the ARM's AXI master
                     \                          /
                      ---- same register map ---
```

## The Peronnin tutorial, step by step

The tutorial: in Vivado, add an AXI GPIO with `leds_4bits` and `btns_4bits` and build a
bitstream; in Vitis, run `xgpio_example.c`, which blinks LED 0; then change it to copy
the buttons to the LEDs. Every step has a stand-in that runs without a board:

| Tutorial step | In Vivado / Vitis | Emulated here | Scripted for the real board |
|---|---|---|---|
| Zynq + AXI GPIO + connection automation | block design | `pl/src/axi_gpio.vhdl` (same registers as Xilinx's AXI GPIO) and `pl/src/zybo_gpio_top.vhdl` (the wiring) | `boardsim zybo xsa` |
| Generate bitstream | Vivado | `boardsim zybo test`: `zybo_gpio_tb` does the tutorial's register accesses over AXI and checks the LEDs follow the buttons | (same command) |
| Platform / BSP | Vitis generates `xparameters.h`, `xgpio.h`, ... | `ps/xil/`: hand-written stand-ins with the same names and API | `boardsim zybo vitis` |
| Import `xgpio_example.c`, run: LED blinks | Vitis + board | `boardsim zybo run xgpio_blink` | `boardsim zybo jtag xgpio_blink` |
| Change the code: buttons → LEDs | Vitis + board | `boardsim zybo run xgpio_btns` (changes marked `// CHANGED`) | `boardsim zybo jtag xgpio_btns` |

**How the unchanged program runs without a board.** Every Xilinx driver reaches the
hardware through `Xil_In32` / `Xil_Out32` (`ps/xil/xil_io.h`). In the emulator build,
accesses to `0x4120_0000`–`0x4120_FFFF` go to `ps/model/zybo_board.c` instead: a C model of
the same AXI GPIO and wiring as the VHDL, which gets the buttons from the board view (or
the keyboard) over the UART. `xgpio_example.c` itself is the same file Vitis builds
against the real BSP: the file names, functions and the `SDT` switch match.

AXI GPIO registers (Xilinx PG144): `0x0` GPIO_DATA, `0x4` GPIO_TRI, `0x8` GPIO2_DATA,
`0xC` GPIO2_TRI. A TRI bit of 1 makes the pin an input.

## The board view

`boardsim zybo run <program>` starts QEMU and opens the board in your browser:

- The board with the Zynq in "x-ray view": the PS running your program, the PL with
  `axi_gpio_0`, and the AXI link between them, which moves while the program uses the
  bus. Traces from the GPIO pins light up while that pin is high.
- The four AXI GPIO registers bit by bit, reads/writes per second, the last bus access,
  and the UART console with the program's `xil_printf` output.
- **PS-SRST** restarts the program, like the button on the board.

QEMU runs with `-icount shift=1,align=on`: 2 ns per instruction, kept in step with the
wall clock, which is close to the Zybo's 650 MHz Cortex-A9. That's why `xgpio_blink`
blinks at a visible rate (about 3 Hz) instead of flickering. The tests don't use this
and run as fast as your computer allows.

**Keeping up.** At `shift=1` your computer has to emulate 500 million instructions per
second. If it can't, QEMU warns that the guest is "late", and the console shows
`[qemu] QEMU is N s behind the real chip`. (QEMU always starts up to a couple of seconds
behind and catches up; that warning is hidden.) Falling behind is harmless (QEMU then
runs flat out), but the blink gets slower than on the board. On a
laptop, try a performance power profile first, then `--shift 2` (4 ns per instruction,
half speed).

The board model is written to keep up: a GPIO access is inlined into the driver like a
single load or store on the chip, and touches one small precomputed struct; button input
arrives by UART interrupt into a ring buffer, so the hot path never polls a device.
What's still not like the chip: there is no bus latency. On the Zybo every PL access is a
real AXI transaction, which takes far longer than one instruction, so a polling loop runs
faster here than on the board.

**What QEMU leaves out:** the PL, the Zybo's other parts (HDMI, audio, Pmods, the MIO LED
and buttons), the clock/MIO/DDR setup that `ps7_init` does on the board, and real timing.
Code that uses only the PS peripherals usually runs unchanged on the board; code that
depends on timing or clock setup may not.

## Your own programs

Add a program in `ps/CMakeLists.txt`:

```cmake
zynq_program(myprog examples/myprog/main.c)                 # plain bare-metal program
zybo_board_program(mygpio examples/mygpio/main.c            # with the board model (XGpio)
    KEYS "1.2.q" EXPECT "LD3..LD0 \\.\\.\\.\\*")              # its test: keys in, regex out
```

Then `uv run boardsim zybo run myprog`. `zybo build --system-toolchain` uses an
`arm-none-eabi-gcc` from your `PATH` instead of the one Conan downloads.

## The custom AXI-Lite peripheral

`pl/src/axi_lite_leds.vhdl` is a small hand-written AXI-Lite slave, with its C driver in
`ps/drivers/axi_leds.h` and a test program in `ps/examples/axi_leds/`:

| Offset | Name | Access | Bits |
|---|---|---|---|
| `0x0` | LED   | RW | 3:0 → LD3..LD0 |
| `0x4` | INPUT | RO | 3:0 = SW3..SW0, 7:4 = BTN3..BTN0 (synchronised, not debounced) |
| `0x8` | ID    | RO | `0x4C454453` ("LEDS") |
| `0xC` | –     | –  | answers SLVERR: on the CPU that is a data abort |

Its testbench checks the AXI rules too (no response before both handshakes, a slow
master). Port names follow Vivado's `s_axi_*` convention, so Vivado recognises the
interface when you add the file to a block design with *Add Module*. To use it on the
board: add it next to the Zynq PS, run connection automation (it lands at `0x43C0_0000`),
make `led`, `sw`, `btn` external, uncomment those pins in a copy of
`pl/constraints/Zybo-Master.xdc`, and build `axi_leds` with `-DAXI_LEDS_REAL=1`.

## On the real board

`vivado/zybo_gpio.tcl` (run by `boardsim zybo xsa`) does what you would click in the GUI:

1. New project, *Boards* tab → *Zybo*. Vivado 2023.2 doesn't ship the original Zybo's
   board files; the script loads Digilent's copy from
   `vivado/board_files/` (in the GUI: *Settings → Board Repository*, or install them from
   github.com/Digilent/vivado-boards).
   Set *Target language* to VHDL (in the wizard, or *Settings → General* later) so the
   wrapper is VHDL like the rest of the repo; Vivado defaults to Verilog.
2. *Create Block Design* → add *ZYNQ7 Processing System* → *Run Block Automation* (board preset on).
3. Add *AXI GPIO* → *Re-customize*: GPIO = `leds_4bits`, *Enable Dual Channel*, GPIO2 =
   `btns_4bits` → *Run Connection Automation* (all). No XDC needed: the board interfaces
   carry the pins.
4. *Validate Design*. The Address Editor shows `axi_gpio_0` at `0x4120_0000`: the same as
   the emulator. The script checks this and prints `CHECK:` lines.
5. *Create HDL Wrapper* → *Generate Bitstream* → *File → Export → Export Hardware*, with
   the bitstream.

Expected noise: four critical warnings `[PSU-1..4]` about negative DQS-to-clock DDR delays,
from Digilent's preset; they are harmless.

`vitis/build_apps.py` (run by `boardsim zybo vitis`) uses the Vitis Python API: a platform
component from the `.xsa` (standalone, `ps7_cortexa9_0`), and one *Empty Application* per
program with `ps/examples/<app>/xgpio_example.c` imported unchanged.

`vitis/run_jtag.tcl` (run by `boardsim zybo jtag`) does what Vitis *Run* does: reset,
program the PL with the bitstream, `ps7_init` + `ps7_post_config`, download the `.elf`,
run. Set jumper JP5 to JTAG, connect USB to the PROG/UART port (J11), power on. The serial
console is the board's second USB serial port at 115200 8N1 (Windows: a COM port; Linux:
usually `/dev/ttyUSB1`).

Platform notes:

- **Windows:** Vivado's installer offers the Digilent cable drivers; say yes.
- **Linux:** install the cable drivers once:
  `sudo <Vivado>/data/xicom/cable_drivers/lin64/install_script/install_drivers/install_drivers`.
  XSCT/XSDB need `xlsclients` (`x11-utils` on Debian/Ubuntu, `xorg-xlsclients` on Arch).
  On distributions other than Ubuntu/RHEL, Vitis' bundled cmake can't find OpenSSL 1.0;
  `boardsim` works around that. To start the Vitis IDE yourself on such a system:
  `LD_LIBRARY_PATH=$XILINX_VITIS/tps/lnx64/cmake-3.24.2/libs/Ubuntu vitis -w zybo/build/hw/vitis_ws`.
- **macOS:** there is no Vivado or Vitis; use the emulator, and a Windows/Linux machine
  for the real board.

The Zybo Z7 (outside the course) is covered in the main [README](../README.md#outside-the-course-zybo-z7).

## Further: co-simulation

To run the C driver against the simulated VHDL in one simulation, AMD's fork of QEMU can
connect to a SystemC/Verilator model of the PL over "remote-port"
([Xilinx/systemctlm-cosim-demo](https://github.com/Xilinx/systemctlm-cosim-demo)). That
is heavy to set up; the two separate tests above give most of the confidence.
