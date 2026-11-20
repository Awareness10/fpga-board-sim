/* A C model of the tutorial's PL design, for running under QEMU (which has no FPGA):
 * an AXI GPIO at 0x4120_0000 wired like zybo/pl/src/zybo_gpio_top.vhdl
 *     channel 1 (all outputs) -> LD3..LD0
 *     channel 2 (all inputs)  <- BTN3..BTN0
 *     SW3..SW0 are on the board but not wired to the GPIO (as in zybo_gpio_top.vhdl)
 * plus a keyboard "board" on the UART:
 *     1 2 3 4   toggle BTN0..BTN3   (a terminal has no key-up events, so a key press
 *     5 6 7 8   toggle SW0..SW3      means pressed until you press it again)
 *     .         wait a moment (only useful in scripted runs: ctest pipes keys in)
 *     q         quit QEMU
 * The board state is printed whenever an LED or an input changes.
 *
 * GUI mode (boardsim zybo run): the GUI sends '@' once. From then on the model prints
 * machine-readable "@zybo key=value ..." lines instead of the [zybo] text: on every change
 * and every HEARTBEAT GPIO accesses (bus activity counters for the GUI).
 * The GUI sets inputs with explicit commands instead of toggles, so a lost key can't
 * invert a button:
 *     a b c d / A B C D   press / release BTN0..BTN3
 *     e f g h / E F G H   switch SW0..SW3 on / off
 *
 * Speed (data-oriented): under QEMU -icount every instruction the model runs is emulated
 * time the real chip wouldn't spend, and every device access is slow for the host. So the
 * hot path (each GPIO access, inlined into the driver from xil_io.h) only touches the
 * small zybo_hot struct: a precomputed read table, the registers, counters, a countdown. Keys arrive by UART
 * interrupt into a RAM ring buffer (uart_rx_irq_enable), so no access polls the UART.
 * Everything else (keys, telemetry, the text board) is the cold path: it runs on a change,
 * when a key is waiting, or when the heartbeat countdown runs out.
 *
 * This model and the VHDL in zybo/pl/ describe the same hardware. Keep them in sync:
 * zybo_gpio_tb checks the VHDL, the xgpio_* ctests check the software against this. */
#include "bsp.h"
#include "xgpio.h"
#include "xil_io.h"

#define WIDTH_MASK 0xFu               /* both channels are 4 bits wide */
#define HEARTBEAT (1u << 20)          /* GPIO accesses between GUI heartbeats */

enum { R_DATA, R_TRI, R_DATA2, R_TRI2 };          /* register index = offset / 4 */

/* Hot: read and written by the inlined Xil_In32 / Xil_Out32 (xil_io.h) on every access. */
struct zybo_hot zybo_hot = {
    .rd = {0, WIDTH_MASK, 0, WIDTH_MASK},
    .reg = {0, WIDTH_MASK, 0, WIDTH_MASK},        /* reset: all inputs (C_TRI_DEFAULT) */
    .countdown = 1,                               /* the first access starts the board */
};
#define H zybo_hot

/* Cold: only the cold path touches this. */
static struct {
    u32 btn, sw;                      /* board inputs */
    u32 shown_led;                    /* last LED state printed */
    u32 sent_sig;                     /* state last sent to the GUI */
    unsigned wait;                    /* accesses to skip before the next key */
    int started;
    int gui;                          /* machine-readable output for the GUI */
} b;

/* --- Wiring: what zybo_gpio_top.vhdl connects to the GPIO pins ---------------- */
static u32 leds(void) { return H.reg[R_DATA] & WIDTH_MASK; }  /* C_ALL_OUTPUTS: drives even if TRI=1 */
static u32 gpio2_pins(void) { return b.btn; }            /* GPIO2 board interface: btns_4bits */

/* Recompute the read table after a register or an input changed. */
static void refresh(void)
{
    H.rd[R_DATA] = leds();                        /* all outputs: reads back the register */
    H.rd[R_TRI] = H.reg[R_TRI];
    H.rd[R_DATA2] = gpio2_pins() & WIDTH_MASK;    /* all inputs: reads the pins */
    H.rd[R_TRI2] = H.reg[R_TRI2];
}

static void lamps(u32 v, char on)
{
    for (int i = 3; i >= 0; i--)
        uart_putc(v & (1u << i) ? on : '.');
}

/* Everything the GUI draws that can change, packed into one word to detect changes. */
static u32 signature(void)
{
    return leds() | b.btn << 4 | b.sw << 8 | H.reg[R_TRI] << 12 | H.reg[R_TRI2] << 16
           | H.reg[R_DATA] << 20;
}

static void telemetry(void)
{
    kprintf("@zybo cfg=%s led=%x btn=%x sw=%x dout1=%x tri1=%x tri2=%x in2=%x rd=%u wr=%u op=%c off=%x val=%x\n",
            "btns", leds(), b.btn, b.sw, H.reg[R_DATA], H.reg[R_TRI],
            H.reg[R_TRI2], gpio2_pins() & WIDTH_MASK, H.reads, H.writes,
            H.last_op ? (char)H.last_op : '-', H.last_off, H.last_val);
    b.sent_sig = signature();
}

static void show(void)
{
    if (b.gui) {
        telemetry();
        return;
    }
    uart_puts("[zybo] LD3..LD0 ");
    lamps(leds(), '*');
    uart_puts("   BTN3..BTN0 ");
    lamps(b.btn, '#');
    uart_puts("   SW3..SW0 ");
    lamps(b.sw, '#');
    uart_putc('\n');
    b.shown_led = leds();
}

/* A register or input changed: tell the GUI, or print the text board if an LED changed. */
static void changed(void)
{
    if (b.gui) {
        if (signature() != b.sent_sig)
            telemetry();
    } else if (leds() != b.shown_led) {
        show();
    }
}

static void key(int c)
{
    u32 btn = b.btn, sw = b.sw;
    if (c >= '1' && c <= '4')
        btn ^= 1u << (c - '1');
    else if (c >= '5' && c <= '8')
        sw ^= 1u << (c - '5');
    else if (c >= 'a' && c <= 'd')            /* GUI: press / release a button */
        btn |= 1u << (c - 'a');
    else if (c >= 'A' && c <= 'D')
        btn &= ~(1u << (c - 'A'));
    else if (c >= 'e' && c <= 'h')            /* GUI: switch on / off */
        sw |= 1u << (c - 'e');
    else if (c >= 'E' && c <= 'H')
        sw &= ~(1u << (c - 'E'));
    else if (c == '@') {                      /* GUI connected: switch to @zybo lines */
        b.gui = 1;
        telemetry();
        return;
    } else if (c == '.') {
        b.wait = 20;
        return;
    } else if (c == 'q') {
        uart_puts("[zybo] quit\n");
        exit(0);
    } else {
        return;
    }
    b.btn = btn;
    b.sw = sw;
    refresh();
    if (c <= '8')
        show();                               /* keyboard: always print the board */
    else
        changed();
    b.wait = 4;                               /* give the program a few accesses to react */
}

/* Cold path: the first access, a key waiting in the ring buffer, or the heartbeat. */
void zybo_cold(void)
{
    if (!b.started) {
        b.started = 1;
        uart_puts("[zybo] board model, GPIO2 = btns_4bits");
        uart_puts(": keys 1-4 toggle BTN0-3, 5-8 toggle SW0-3, q quits\n");
        show();
        uart_rx_irq_enable();
    }
    if (H.countdown == 0) {
        H.countdown = HEARTBEAT;
        if (b.gui)
            telemetry();
    }
    if (uart_rx_ready()) {
        if (b.wait)
            b.wait--;
        else
            key(uart_getc_nb());
    }
}

/* A write changed a register (the inlined Xil_Out32 already filtered same-value writes). */
void zybo_changed(u32 reg, u32 value)
{
    H.reg[reg] = value;
    refresh();
    changed();
}
