/* Hello world on the Zynq's Cortex-A9, plus a peek at a few CP15 system registers,
 * the global timer and the FPU. */
#include "bsp.h"

static const char *mode_name(uint32_t cpsr)
{
    switch (cpsr & 0x1F) {
    case 0x10: return "USR";
    case 0x13: return "SVC";
    case 0x1F: return "SYS";
    default: return "other";
    }
}

/* Newton's method for sqrt(x): compiles to VFP instructions (vdiv.f32, vadd.f32 ...),
 * see hello.lst. This only works because crt0.S switched the FPU on. */
static float my_sqrtf(float x)
{
    float g = x;
    for (int i = 0; i < 20; i++)
        g = 0.5f * (g + x / g);
    return g;
}

int main(void)
{
    kprintf("Hello from the Zynq-7000 (Cortex-A9)!\n");

    uint32_t midr = cp15_read(c0, c0, 0);
    kprintf("MIDR    : 0x%08x  (0x41.fc09. = ARM Cortex-A9; 0x413fc090 = revision r3p0)\n", midr);
    kprintf("MPIDR   : 0x%08x  (CPU %u)\n", cp15_read(c0, c0, 5), cp15_read(c0, c0, 5) & 3);
    kprintf("SCTLR   : 0x%08x  (MMU %s, D-cache %s)\n", cp15_read(c1, c0, 0),
            cp15_read(c1, c0, 0) & 1 ? "on" : "off", cp15_read(c1, c0, 0) & 4 ? "on" : "off");
    uint32_t cpsr = read_cpsr();
    kprintf("CPSR    : 0x%08x  (mode %s, IRQ %s)\n", cpsr, mode_name(cpsr),
            cpsr & 0x80 ? "masked" : "enabled");

    uint64_t t0 = gtimer_read();
    volatile uint32_t sum = 0;
    for (uint32_t i = 0; i < 1000; i++)
        sum += i;
    uint64_t t1 = gtimer_read();
    kprintf("sum 0..999 = %u  (%u global-timer ticks; in QEMU timing is only approximate)\n", sum,
            (uint32_t)(t1 - t0));
    CHECK(sum == 499500);

    float r = my_sqrtf(2.0f);
    kprintf("sqrt(2) ~ %u.%06u  (FPU)\n", (uint32_t)r, (uint32_t)((r - (uint32_t)r) * 1e6f));
    CHECK(r > 1.41421f && r < 1.41422f);

    return 0; /* -> exit(0) -> QEMU quits with status 0 */
}
