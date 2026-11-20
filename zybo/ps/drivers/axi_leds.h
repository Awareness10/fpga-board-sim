/* Driver for the axi_lite_leds peripheral in zybo/pl/src/axi_lite_leds.vhdl.
 * The register layout below must match the VHDL register map.
 *
 * Every function takes the register block as a pointer instead of a fixed address, so
 * the same driver runs against:
 *   - the real peripheral in the PL:  axi_leds_regs *hw = AXI_LEDS_HW;
 *   - a fake in RAM, under QEMU, which has no PL (see examples/axi_leds/main.c). */
#pragma once
#include <stdint.h>

/* Vivado's default address for the first AXI-Lite peripheral on M_AXI_GP0.
 * Check Vivado's Address Editor if yours differs. */
#define AXI_LEDS_BASE 0x43C00000u
#define AXI_LEDS_ID   0x4C454453u   /* "LEDS" */

typedef struct {
    volatile uint32_t led;          /* 0x0  RW  bits 3:0 = LD3..LD0 */
    volatile const uint32_t input;  /* 0x4  RO  bits 3:0 = SW3..SW0, bits 7:4 = BTN3..BTN0 */
    volatile const uint32_t id;     /* 0x8  RO  AXI_LEDS_ID */
} axi_leds_regs;

#define AXI_LEDS_HW ((axi_leds_regs *)(uintptr_t)AXI_LEDS_BASE)

/* 1 if the peripheral answers with the right ID. (On a board without the bitstream
 * loaded the read hangs or aborts instead: the PL has to be configured first.) */
static inline int axi_leds_probe(const axi_leds_regs *r) { return r->id == AXI_LEDS_ID; }

static inline void axi_leds_set(axi_leds_regs *r, uint32_t pattern) { r->led = pattern & 0xF; }
static inline uint32_t axi_leds_get(const axi_leds_regs *r) { return r->led & 0xF; }
static inline void axi_leds_toggle(axi_leds_regs *r, uint32_t mask) { r->led = (r->led ^ mask) & 0xF; }

static inline uint32_t axi_leds_switches(const axi_leds_regs *r) { return r->input & 0xF; }
static inline uint32_t axi_leds_buttons(const axi_leds_regs *r) { return (r->input >> 4) & 0xF; }
