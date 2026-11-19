#include "bsp.h"

#ifndef BSP_SEMIHOSTING
#define BSP_SEMIHOSTING 1
#endif

/* ---- Cadence UART (UG585 ch. 19) ---- */
#define UART_CR      0x00   /* control */
#define UART_MR      0x04   /* mode: data bits, parity, stop bits */
#define UART_BAUDGEN 0x18
#define UART_SR      0x2C   /* channel status */
#define UART_FIFO    0x30   /* TX/RX FIFO */
#define UART_BAUDDIV 0x34

#define CR_RXRST  (1u << 0)
#define CR_TXRST  (1u << 1)
#define CR_RXEN   (1u << 2)
#define CR_RXDIS  (1u << 3)
#define CR_TXEN   (1u << 4)
#define CR_TXDIS  (1u << 5)
#define MR_8N1    0x20u     /* 8 data bits, no parity, 1 stop bit */
#define SR_RXEMPTY (1u << 1)
#define SR_TXEMPTY (1u << 3)
#define SR_TXFULL  (1u << 4)

#define UART(reg) MMIO32(UART1_BASE + (reg))

/* ---- A9 global timer ---- */
#define GT_COUNT_LO 0x00
#define GT_COUNT_HI 0x04
#define GT_CONTROL  0x08
#define GT(reg) MMIO32(GTIMER_BASE + (reg))

void bsp_init(void)
{
    /* baud = uart_ref_clk / (BAUDGEN * (BAUDDIV + 1)) = 100 MHz / (124 * 7) ~ 115200.
     * 100 MHz is the Zybo's default UART reference clock. */
    UART(UART_CR) = CR_TXDIS | CR_RXDIS;
    UART(UART_BAUDGEN) = 124;
    UART(UART_BAUDDIV) = 6;
    UART(UART_CR) = CR_TXRST | CR_RXRST;
    UART(UART_MR) = MR_8N1;
    UART(UART_CR) = CR_TXEN | CR_RXEN;

    GT(GT_CONTROL) = 1; /* timer enable, no prescaler */
}

uint64_t gtimer_read(void)
{
    /* The counter is two 32-bit halves: re-read if the high half ticked over in between. */
    uint32_t hi, lo;
    do {
        hi = GT(GT_COUNT_HI);
        lo = GT(GT_COUNT_LO);
    } while (GT(GT_COUNT_HI) != hi);
    return ((uint64_t)hi << 32) | lo;
}

void uart_putc(char c)
{
    if (c == '\n')
        uart_putc('\r');
    while (UART(UART_SR) & SR_TXFULL)
        ;
    UART(UART_FIFO) = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s)
        uart_putc(*s++);
}

/* ---- UART receive by interrupt (opt-in) ----
 * Polling UART_SR is a device access: on a real chip it's a slow bus read, and under
 * QEMU -icount it's slow for the host too. With uart_rx_irq_enable() the UART interrupts
 * on each received byte, irq_dispatch moves it into this ring buffer, and uart_rx_ready()
 * / uart_getc_nb() only touch RAM. */
#define UART_IER   0x08     /* interrupt enable */
#define UART_IDR   0x0C     /* interrupt disable */
#define UART_ISR   0x14     /* channel interrupt status, write 1 to clear */
#define UART_RTRIG 0x20     /* RX FIFO trigger level */
#define IXR_RTRIG  (1u << 0)

#define GICC(reg)   MMIO32(GIC_CPU_BASE + (reg))
#define GICD(reg)   MMIO32(GIC_DIST_BASE + (reg))
#define GICD8(reg)  (*(volatile uint8_t *)(uintptr_t)(GIC_DIST_BASE + (reg)))
#define ICCICR  0x00        /* CPU interface control */
#define ICCPMR  0x04        /* priority mask */
#define ICCIAR  0x0C        /* interrupt acknowledge */
#define ICCEOIR 0x10        /* end of interrupt */
#define ICDDCR  0x000       /* distributor control */
#define ICDISER 0x100       /* set-enable, 32 IDs per word */
#define ICDIPR  0x400       /* priority, one byte per ID */
#define ICDIPTR 0x800       /* CPU targets, one byte per ID */
#define ICDICFR 0xC00       /* config, 2 bits per ID: 01 = level, 11 = rising edge */

volatile uint8_t uart_rx_buf[UART_RX_BUF_SIZE];
volatile uint32_t uart_rx_head, uart_rx_tail;
static int rx_irq_on;

void uart_rx_irq_enable(void)
{
    const unsigned id = UART1_IRQ;
    GICD(ICDDCR) = 1;
    GICD8(ICDIPR + id) = 0xA0;
    GICD8(ICDIPTR + id) = 0x01;                                   /* CPU0 */
    GICD(ICDICFR + 4 * (id / 16)) = (GICD(ICDICFR + 4 * (id / 16)) & ~(3u << (2 * (id % 16))))
                                    | (1u << (2 * (id % 16)));   /* level, like the UART's line */
    GICD(ICDISER + 4 * (id / 32)) = 1u << (id % 32);
    GICC(ICCPMR) = 0xF0;
    GICC(ICCICR) = 1;

    UART(UART_RTRIG) = 1;           /* interrupt as soon as one byte is in the FIFO */
    UART(UART_ISR) = UART(UART_ISR);
    UART(UART_IER) = IXR_RTRIG;
    rx_irq_on = 1;
    __asm__ volatile("cpsie i" ::: "memory");
}

/* Called from irq_entry (crt0.S). No VFP use, so irq_entry needn't save VFP registers. */
__attribute__((target("general-regs-only"))) void irq_dispatch(void)
{
    uint32_t iar = GICC(ICCIAR);
    uint32_t id = iar & 0x3FF;
    if (id == UART1_IRQ) {
        while (!(UART(UART_SR) & SR_RXEMPTY)) {
            uint8_t c = (uint8_t)UART(UART_FIFO);
            uint32_t next = (uart_rx_head + 1) % UART_RX_BUF_SIZE;
            if (next != uart_rx_tail) {             /* full: drop the byte */
                uart_rx_buf[uart_rx_head] = c;
                uart_rx_head = next;
            }
        }
        UART(UART_ISR) = IXR_RTRIG;
    }
    if (id < 1020)                                  /* 1023 = spurious, no EOI */
        GICC(ICCEOIR) = iar;
}

int uart_getc_nb(void)
{
    if (rx_irq_on) {
        if (uart_rx_tail == uart_rx_head)
            return -1;
        int c = uart_rx_buf[uart_rx_tail];
        uart_rx_tail = (uart_rx_tail + 1) % UART_RX_BUF_SIZE;
        return c;
    }
    if (UART(UART_SR) & SR_RXEMPTY)
        return -1;
    return (int)(UART(UART_FIFO) & 0xFF);
}

/* ---- Tiny printf ---- */
static int put_uint(uint32_t v, unsigned base, int upper, int width, char pad)
{
    char buf[11];
    const char *digits = upper ? "0123456789ABCDEF" : "0123456789abcdef";
    int n = 0, out = 0;
    do {
        buf[n++] = digits[v % base];
        v /= base;
    } while (v);
    for (; width > n; width--, out++)
        uart_putc(pad);
    while (n)
        uart_putc(buf[--n]), out++;
    return out;
}

int kvprintf(const char *fmt, va_list ap)
{
    int out = 0;
    for (; *fmt; fmt++) {
        if (*fmt != '%') {
            uart_putc(*fmt), out++;
            continue;
        }
        fmt++;
        char pad = ' ';
        int width = 0;
        if (*fmt == '0')
            pad = '0', fmt++;
        while (*fmt >= '0' && *fmt <= '9')
            width = width * 10 + (*fmt++ - '0');

        switch (*fmt) {
        case 'd':
        case 'i': {
            int v = va_arg(ap, int);
            uint32_t u = (uint32_t)v;
            if (v < 0) {
                uart_putc('-'), out++;
                u = -u;
                if (width)
                    width--;
            }
            out += put_uint(u, 10, 0, width, pad);
            break;
        }
        case 'u': out += put_uint(va_arg(ap, unsigned), 10, 0, width, pad); break;
        case 'x': out += put_uint(va_arg(ap, unsigned), 16, 0, width, pad); break;
        case 'X': out += put_uint(va_arg(ap, unsigned), 16, 1, width, pad); break;
        case 'p':
            uart_puts("0x"), out += 2;
            out += put_uint((uint32_t)(uintptr_t)va_arg(ap, void *), 16, 0, 8, '0');
            break;
        case 'c': uart_putc((char)va_arg(ap, int)), out++; break;
        case 's': {
            const char *s = va_arg(ap, const char *);
            s = s ? s : "(null)";
            for (int len = (int)strlen(s); width > len; width--, out++)
                uart_putc(pad);
            while (*s)
                uart_putc(*s++), out++;
            break;
        }
        case '%': uart_putc('%'), out++; break;
        case '\0': return out;
        default: uart_putc('%'), uart_putc(*fmt), out += 2; break;
        }
    }
    return out;
}

int kprintf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = kvprintf(fmt, ap);
    va_end(ap);
    return n;
}

/* ---- Exit ---- */
_Noreturn void exit(int code)
{
    while (!(UART(UART_SR) & SR_TXEMPTY)) /* let the last characters leave */
        ;
#if BSP_SEMIHOSTING
    /* ARM semihosting SYS_EXIT_EXTENDED (0x20): QEMU exits with status `code`.
     * r0 = operation, r1 = pointer to {reason, exit code}. */
    static uint32_t block[2];
    block[0] = 0x20026; /* ADP_Stopped_ApplicationExit */
    block[1] = (uint32_t)code;
    register uint32_t r0 __asm__("r0") = 0x20;
    register uint32_t *r1 __asm__("r1") = block;
#if defined(__thumb__)
    __asm__ volatile("svc 0xab" : "+r"(r0) : "r"(r1) : "memory");
#else
    __asm__ volatile("svc 0x123456" : "+r"(r0) : "r"(r1) : "memory");
#endif
#endif
    for (;;)
        __asm__ volatile("wfe");
}

/* ---- Exception handler (called from the stubs in crt0.S) ---- */
_Noreturn void exception_handler(uint32_t type, uint32_t lr)
{
    static const char *const names[] = {
        "reset", "undefined instruction", "SVC", "prefetch abort",
        "data abort", "reserved", "IRQ", "FIQ",
    };
    /* LR points past the faulting instruction: by 4 for undef/prefetch, by 8 for data abort. */
    uint32_t pc = lr - (type == 4 ? 8 : 4);
    kprintf("\n*** EXCEPTION: %s at pc=0x%08x\n", names[type & 7], pc);
    if (type == 4)
        kprintf("    DFSR=0x%08x (fault status)  DFAR=0x%08x (address)\n",
                cp15_read(c5, c0, 0), cp15_read(c6, c0, 0));
    if (type == 3)
        kprintf("    IFSR=0x%08x  IFAR=0x%08x\n", cp15_read(c5, c0, 1), cp15_read(c6, c0, 2));
    exit(100);
}

/* ---- Memory/string functions the compiler is allowed to call ---- */
void *memset(void *dst, int c, size_t n)
{
    unsigned char *d = dst;
    while (n--)
        *d++ = (unsigned char)c;
    return dst;
}

void *memcpy(void *dst, const void *src, size_t n)
{
    unsigned char *d = dst;
    const unsigned char *s = src;
    while (n--)
        *d++ = *s++;
    return dst;
}

void *memmove(void *dst, const void *src, size_t n)
{
    unsigned char *d = dst;
    const unsigned char *s = src;
    if (d < s)
        while (n--)
            *d++ = *s++;
    else
        while (n--)
            d[n] = s[n];
    return dst;
}

int memcmp(const void *a, const void *b, size_t n)
{
    const unsigned char *x = a, *y = b;
    for (; n; n--, x++, y++)
        if (*x != *y)
            return *x - *y;
    return 0;
}

size_t strlen(const char *s)
{
    size_t n = 0;
    while (s[n])
        n++;
    return n;
}
