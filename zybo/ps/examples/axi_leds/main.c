/* Drives the PL's axi_lite_leds peripheral: a binary counter on LD3..LD0, and the
 * switches mirrored into the pattern.
 *
 * QEMU has no FPGA fabric, so by default the driver runs against a fake register block
 * in RAM and the program checks what the driver wrote. On the real board, with the
 * bitstream loaded, build with -DAXI_LEDS_REAL=1 to talk to the hardware at 0x43C0_0000.
 * (The hardware itself is tested in simulation: zybo/pl/tb/axi_lite_leds_tb.vhdl.) */
#include "axi_leds.h"
#include "bsp.h"

#ifndef AXI_LEDS_REAL
#define AXI_LEDS_REAL 0
#endif

static void delay(uint32_t ticks)
{
    uint64_t end = gtimer_read() + ticks;
    while (gtimer_read() < end)
        ;
}

static void show(uint32_t p)
{
    kprintf("LD3..LD0: %c%c%c%c\n", p & 8 ? '*' : '.', p & 4 ? '*' : '.', p & 2 ? '*' : '.',
            p & 1 ? '*' : '.');
}

#if AXI_LEDS_REAL
int main(void)
{
    axi_leds_regs *leds = AXI_LEDS_HW;
    if (!axi_leds_probe(leds)) {
        kprintf("axi_lite_leds not found at 0x%08x (id=0x%08x)\n", AXI_LEDS_BASE, leds->id);
        return 1;
    }
    kprintf("axi_lite_leds found. Counting; flip switches to XOR them in, BTN0 to stop.\n");
    for (uint32_t n = 0; !(axi_leds_buttons(leds) & 1); n++) {
        axi_leds_set(leds, n ^ axi_leds_switches(leds));
        delay(333333333 / 4); /* global timer = 333 MHz on the Zybo: 0.25 s */
    }
    axi_leds_set(leds, 0);
    return 0;
}
#else
/* RAM stand-in for the peripheral. Only the parts the driver should rely on are faked:
 * the ID, and the input register that the "board" (this test) controls. */
static struct {
    uint32_t led, input, id;
} fake = {.id = AXI_LEDS_ID};

int main(void)
{
    axi_leds_regs *leds = (axi_leds_regs *)&fake;
    kprintf("QEMU: axi_leds driver against a fake register block at %p\n", (void *)leds);

    CHECK(axi_leds_probe(leds));
    fake.id = 0;
    CHECK(!axi_leds_probe(leds)); /* wrong ID -> not found */
    fake.id = AXI_LEDS_ID;

    for (uint32_t n = 0; n < 6; n++) {
        axi_leds_set(leds, n);
        show(axi_leds_get(leds));
        CHECK(fake.led == n);
        delay(1000);
    }

    axi_leds_set(leds, 0x1F); /* only 4 LEDs: driver must mask */
    CHECK(fake.led == 0xF);
    axi_leds_toggle(leds, 0x5);
    CHECK(fake.led == 0xA);

    fake.input = 0x35; /* BTN = 0011, SW = 0101 (same values as the VHDL testbench) */
    CHECK(axi_leds_switches(leds) == 0x5);
    CHECK(axi_leds_buttons(leds) == 0x3);

    kprintf("driver OK\n");
    return 0;
}
#endif
