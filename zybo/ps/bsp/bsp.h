/* Minimal board support for the Zynq-7000 PS (Zybo), real or in QEMU's xilinx-zynq-a9:
 * UART output, exit codes, CP15 register access, the A9 global timer.
 * No libc: everything a program needs is here. */
#pragma once
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>

/* --- Memory-mapped devices (Zynq-7000 TRM, UG585, appendix B) ------------- */
#define UART1_BASE   0xE0001000u   /* Cadence UART; UART1 = the Zybo's USB-UART (MIO 48/49) */
#define GTIMER_BASE  0xF8F00200u   /* Cortex-A9 global timer, 64-bit, runs at CPU clock / 2 */
#define PL_GP0_BASE  0x40000000u   /* M_AXI_GP0: start of the PL (your VHDL) address space */
#define GIC_CPU_BASE  0xF8F00100u  /* interrupt controller (ARM GIC v1): CPU interface */
#define GIC_DIST_BASE 0xF8F01000u  /* ... and distributor */
#define UART1_IRQ    82u           /* UART1's interrupt ID (UG585 table 7-4) */

#define MMIO32(addr) (*(volatile uint32_t *)(uintptr_t)(addr))

/* --- CP15 system registers: the ARM counterpart of RISC-V CSRs -------------
 * e.g. cp15_read(c0, c0, 0) = MIDR (CPU id), cp15_read(c1, c0, 0) = SCTLR. */
#define cp15_read(crn, crm, op2) ({ uint32_t v_; \
    __asm__ volatile("mrc p15, 0, %0, " #crn ", " #crm ", " #op2 : "=r"(v_)); v_; })
#define cp15_write(crn, crm, op2, val) \
    __asm__ volatile("mcr p15, 0, %0, " #crn ", " #crm ", " #op2 ::"r"((uint32_t)(val)))

static inline uint32_t read_cpsr(void)
{
    uint32_t v;
    __asm__ volatile("mrs %0, cpsr" : "=r"(v));
    return v;
}

/* 64-bit global timer count (started by bsp_init). */
uint64_t gtimer_read(void);

/* --- Output -------------------------------------------------------------- */
void uart_putc(char c);
void uart_puts(const char *s);
/* Next received character, or -1 if none has arrived (does not wait). */
int uart_getc_nb(void);

/* Receive by interrupt instead of polling: after this, received bytes go into a RAM ring
 * buffer (from the UART1 IRQ), uart_getc_nb reads from it, and uart_rx_ready() is a check
 * that touches no device register. Turns on IRQs (cpsie i). */
void uart_rx_irq_enable(void);
#define UART_RX_BUF_SIZE 64u
extern volatile uint32_t uart_rx_head, uart_rx_tail;
static inline int uart_rx_ready(void) { return uart_rx_head != uart_rx_tail; }
/* printf subset: %d %i %u %x %X %p %s %c %% with optional width and 0-padding, e.g. %08x.
 * All integers are 32-bit. */
int kprintf(const char *fmt, ...);
int kvprintf(const char *fmt, va_list ap);

/* Called by crt0.S before main: sets up UART1 (115200 8N1) and the global timer. */
void bsp_init(void);

/* --- Program end --------------------------------------------------------- */
/* In QEMU (-semihosting) this quits QEMU with status `code` (0 = success), so ctest can
 * tell passing programs from failing ones. On the real board without a debugger there
 * is nobody to exit to: build with -DBSP_SEMIHOSTING=0 and it just stops the CPU. */
_Noreturn void exit(int code);

/* Test helper: prints a message on failure and exits with code 1. */
#define CHECK(cond)                                                          \
    do {                                                                     \
        if (!(cond)) {                                                       \
            kprintf("CHECK failed: %s  (%s:%d)\n", #cond, __FILE__, __LINE__); \
            exit(1);                                                         \
        }                                                                    \
    } while (0)

/* Functions the compiler may emit calls to even without libc. */
void *memset(void *dst, int c, size_t n);
void *memcpy(void *dst, const void *src, size_t n);
void *memmove(void *dst, const void *src, size_t n);
int memcmp(const void *a, const void *b, size_t n);
size_t strlen(const char *s);
