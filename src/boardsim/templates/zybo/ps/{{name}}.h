/* Driver for the {{name}} peripheral (pl/src/{{name}}.vhdl).
 * The register struct below must match the VHDL register map, in the same order.
 *
 * Every function takes the register block as a pointer instead of a fixed address, so
 * the same driver runs against the real peripheral on the board ({{NAME}}_HW) and
 * against a fake register block in RAM in the emulator (see main.c). */
#pragma once
#include <stdint.h>

/* Where Vivado puts the first AXI-Lite peripheral on M_AXI_GP0. `boardsim zybo xsa`
 * prints the address it got ("CHECK: ... base"); change this if it differs. */
#define {{NAME}}_BASE 0x43C00000u
#define {{NAME}}_ID   0xC0DE0001u          /* C_ID in the VHDL */

typedef struct {
    volatile uint32_t led;                 /* 0x0  RW  bits 3:0 = LD3..LD0 */
    volatile const uint32_t input;         /* 0x4  RO  bits 3:0 = SW3..SW0, 7:4 = BTN3..BTN0 */
    volatile const uint32_t id;            /* 0x8  RO  {{NAME}}_ID */
} {{name}}_regs;

#define {{NAME}}_HW (({{name}}_regs *)(uintptr_t){{NAME}}_BASE)

/* 1 if the peripheral answers with the right ID. (Without the bitstream loaded, the read
 * hangs or aborts instead: the PL has to be configured first.) */
static inline int {{name}}_probe(const {{name}}_regs *r) { return r->id == {{NAME}}_ID; }

static inline void {{name}}_set_leds({{name}}_regs *r, uint32_t pattern) { r->led = pattern & 0xF; }
static inline uint32_t {{name}}_get_leds(const {{name}}_regs *r) { return r->led & 0xF; }
static inline uint32_t {{name}}_switches(const {{name}}_regs *r) { return r->input & 0xF; }
static inline uint32_t {{name}}_buttons(const {{name}}_regs *r) { return (r->input >> 4) & 0xF; }
