# Basys3 (Artix-7)

```sh
uv run boardsim basys3 run              # basys3_top on the emulated board, in the browser
uv run boardsim basys3 test             # every testbench in tb/
uv run boardsim basys3 wave counter_tb  # a testbench in GTKWave or Surfer
uv run boardsim basys3 bit              # Vivado: bitstream
uv run boardsim basys3 program          # Vivado: bitstream + program a connected Basys3
```

| Folder | |
|---|---|
| `src/` | the design: `basys3_top` (counter on LEDs + 7-segment), `counter`, `seven_seg` |
| `tb/` | self-checking testbenches, one per `*_tb.vhdl` |
| `sim/` | `basys3_sim_pkg`: testbench helpers that print the board (LEDs, switches, 7-segment as text) |
| `constraints/` | Digilent's master XDC, and `<top>.xdc` per top-level entity |
| `vivado/build.tcl` | batch synthesis → implementation → bitstream (→ program) |

## Your own design

```sh
uv run boardsim new basys3 lab1     # assignments/lab1: top entity, testbench, pins
uv run boardsim basys3 run lab1     # and test / wave lab1_tb / bit / program
```

Every command takes an assignment name or a folder (default: this folder); the top entity
is the one named like the folder, else `basys3_top`, or pass `--top <entity>`:

```
my_design/
  src/*.vhdl              your design
  tb/*_tb.vhdl            testbenches (for test / wave)
  constraints/<top>.xdc  pins (for bit / program): copy lines from Basys-3-Master.xdc
```

Testbenches in your folder can use `basys3_sim_pkg` from this folder's `sim/`.
The whole workflow: [HOW-TO-USE.md](../HOW-TO-USE.md).

## How the board view works

`basys3 run` generates a small VHDL harness around your top entity
(`build/gui/boardsim_basys3_gui.vhdl`) and runs it in GHDL. The harness connects every
port it recognises by name, as in the Basys3 master XDC: `clk`, `sw`, `btnC`, `btnU`,
`btnL`, `btnR`, `btnD`, `led`, `seg`, `dp`, `an` (narrower vectors like
`led(7 downto 0)` are fine). Other outputs are left open; other inputs are an error.

The simulation runs in frames of 10 ms of simulated time (`--frame-ms`). For each frame
the browser sends the switches and buttons, GHDL simulates the frame while sampling the
outputs, and sends back how long each LED and each digit was lit. So a dimmed (PWM) LED
looks dimmed, and a multiplexed 7-segment display shows all four digits, like on the
board. `report` and failed `assert` messages show in the page's console.

**Speed.** GHDL simulates roughly half a million clock cycles per second, so the
Basys3's real 100 MHz clock runs about 200 times slower than the board. If your top
entity has a clock-frequency generic (`CLK_HZ`, `CLK_FREQ`, `CLK_FREQ_HZ`, `CLOCK_HZ`,
`G_CLK_HZ`), the board view sets it to 250 kHz and runs the clock at 250 kHz too: as
long as your dividers are computed from that generic, everything happens at the real
speed, just with fewer clock cycles in between. That's how `basys3_top` does it:

```vhdl
generic (CLK_HZ : positive := 100_000_000);   -- the real board's clock by default
...
constant TICK_DIV : positive := CLK_HZ / TICK_HZ;   -- not a hard-coded 10_000_000
```

Use `--clk-hz` to pick another frequency, `--generic NAME=VALUE` to override other
generics, and `--max-speed` to let simulated time run ahead of real time. A design without
a `clk` port (purely combinational) needs no clock at all and is always fast.
