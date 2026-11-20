/* {{name}}: the C side. The same file builds for the emulator and for the board:
 *
 *   emulator (`boardsim zybo run {{name}} --terminal`, `boardsim zybo test {{name}}`):
 *     the build defines ZYBO_BOARD_MODEL. QEMU has no FPGA, so the driver runs against
 *     a fake register block in RAM, and the program checks what the driver wrote.
 *     (The VHDL itself is tested by pl/tb/{{name}}_tb.vhdl.)
 *   board (`boardsim zybo vitis {{name}}`, then `boardsim zybo jtag {{name}}`):
 *     Vitis builds the other half, which talks to the real peripheral at {{NAME}}_BASE. */
#include "xil_printf.h"
#include "{{name}}.h"

#ifdef ZYBO_BOARD_MODEL
/* ---- Emulator: test the driver against a fake peripheral --------------------------- */

/* A failed EXPECT prints "CHECK failed", which makes the test fail. */
#define EXPECT(cond)                                                         \
    do {                                                                     \
        if (!(cond)) {                                                       \
            xil_printf("CHECK failed: %s (line %d)\n", #cond, __LINE__);     \
            return 1;                                                        \
        }                                                                    \
    } while (0)

/* Fake only what the driver should rely on: the ID, and the inputs the "board" sets. */
static struct {
    uint32_t led, input, id;
} fake = {.id = {{NAME}}_ID};

int main(void)
{
    {{name}}_regs *r = ({{name}}_regs *)&fake;
    xil_printf("{{name}}: driver against a fake register block\n");

    EXPECT({{name}}_probe(r));

    {{name}}_set_leds(r, 0x1F);            /* only 4 LEDs: the driver must mask */
    EXPECT(fake.led == 0xF);
    EXPECT({{name}}_get_leds(r) == 0xF);

    fake.input = 0x35;                     /* BTN = 0011, SW = 0101, as in the testbench */
    EXPECT({{name}}_switches(r) == 0x5);
    EXPECT({{name}}_buttons(r) == 0x3);

    xil_printf("{{name}}: driver OK\n");
    return 0;
}

#else
/* ---- Board: the real peripheral --------------------------------------------------- */
#include "sleep.h"

int main(void)
{
    {{name}}_regs *r = {{NAME}}_HW;
    if (!{{name}}_probe(r)) {
        xil_printf("{{name}} not found at 0x%08x (id 0x%08x)\r\n", {{NAME}}_BASE, r->id);
        return 1;
    }
    xil_printf("{{name}}: counting on the LEDs. Switches XOR in, BTN0 stops.\r\n");
    for (uint32_t n = 0; !({{name}}_buttons(r) & 1); n++) {
        {{name}}_set_leds(r, n ^ {{name}}_switches(r));
        usleep(250000);
    }
    {{name}}_set_leds(r, 0);
    xil_printf("{{name}}: stopped\r\n");
    return 0;
}
#endif
