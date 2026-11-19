/* Stand-in for Xilinx's xil_io.h. Every Xilinx driver reaches the hardware through
 * Xil_In32 / Xil_Out32, which makes it the right place to swap the hardware for a model:
 *
 *   on the board / in Vitis:  a plain volatile load or store to the address
 *   in QEMU (ZYBO_BOARD_MODEL): the PL is missing, so addresses that belong to the PL go
 *                              to a C model of the Zybo's AXI GPIO, LEDs and buttons
 *                              (model/zybo_board.c); everything else is real MMIO.
 *
 * Under QEMU -icount every instruction is emulated time, and every call/return costs the
 * host a lookup. So a GPIO access is inlined here like a real load would be: it touches
 * only the model's small "hot" struct (precomputed read values, registers, counters).
 * The rest of the model (keys, telemetry, the text board) is in zybo_cold / zybo_changed,
 * which run only when a key is waiting, a register changes, or the heartbeat is due. */
#pragma once
#include "xil_types.h"

#if ZYBO_BOARD_MODEL
#include "bsp.h"
#include "xparameters.h"
#define ZYBO_PL_BASE XPAR_GPIO_0_BASEADDR
#define ZYBO_PL_SIZE 0x10000u            /* Vivado reserves 64 KB per AXI-Lite peripheral */

struct zybo_hot {
    u32 rd[4];          /* what a read of DATA, TRI, DATA2, TRI2 returns (kept up to date) */
    u32 reg[4];         /* the registers as written: dout1, tri1, dout2, tri2 (4-bit) */
    u32 countdown;      /* accesses until the cold path runs regardless (heartbeat) */
    u32 reads, writes;  /* AXI GPIO accesses so far */
    u32 last_off, last_val, last_op;   /* last access, shown in the GUI ('R' / 'W') */
};
extern struct zybo_hot zybo_hot;
void zybo_cold(void);                    /* first access, key waiting, heartbeat */
void zybo_changed(u32 reg, u32 value);   /* a register gets a new value */

static inline __attribute__((always_inline)) void zybo_tick(void)
{
    if (__builtin_expect(--zybo_hot.countdown == 0 || uart_rx_ready(), 0))
        zybo_cold();
}

static inline __attribute__((always_inline)) u32 Xil_In32(UINTPTR Addr)
{
    u32 off = (u32)(Addr - ZYBO_PL_BASE);  /* unsigned: below the base wraps to huge */
    if (off >= ZYBO_PL_SIZE)
        return *(volatile u32 *)Addr;
    zybo_tick();
    zybo_hot.reads++;
    zybo_hot.last_op = 'R';
    zybo_hot.last_off = off;
    /* 4 registers at 0x0..0xC; anything else (incl. unaligned) reads 0 */
    return zybo_hot.last_val = (off < 16 && !(off & 3)) ? zybo_hot.rd[off >> 2] : 0;
}

static inline __attribute__((always_inline)) void Xil_Out32(UINTPTR Addr, u32 Value)
{
    u32 off = (u32)(Addr - ZYBO_PL_BASE);
    if (off >= ZYBO_PL_SIZE) {
        *(volatile u32 *)Addr = Value;
        return;
    }
    zybo_tick();
    zybo_hot.writes++;
    zybo_hot.last_op = 'W';
    zybo_hot.last_off = off;
    zybo_hot.last_val = Value;
    if (off < 16 && !(off & 3) && zybo_hot.reg[off >> 2] != (Value & 0xFu))
        zybo_changed(off >> 2, Value & 0xFu);   /* same value again: nothing to do */
}
#else
static inline u32 Xil_In32(UINTPTR Addr) { return *(volatile u32 *)Addr; }
static inline void Xil_Out32(UINTPTR Addr, u32 Value) { *(volatile u32 *)Addr = Value; }
#endif
