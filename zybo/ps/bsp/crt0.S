/* Startup code for the Cortex-A9 in the Zynq-7000: the first instructions the CPU executes.
 * On the real board the boot ROM + FSBL (or Vitis/JTAG) run before this and set up
 * clocks, DDR and the MIO pins; QEMU starts here directly. */
    .syntax unified
    .arm

/* ---- Exception vector table ----------------------------------------------------
 * The CPU jumps to VBAR + 4*n on exception n. Each entry branches to a stub that
 * reports the exception (see exception_handler in bsp.c). */
    .section .vectors, "ax"
    .balign 32
vectors:
    b       _start              /* 0x00 reset */
    b       undef_entry         /* 0x04 undefined instruction */
    b       svc_entry           /* 0x08 supervisor call (QEMU semihosting catches svc 0x123456 first) */
    b       pabort_entry        /* 0x0C prefetch abort: bad instruction fetch */
    b       dabort_entry        /* 0x10 data abort: bad load/store, e.g. an AXI SLVERR */
    b       .                   /* 0x14 reserved */
    b       irq_entry           /* 0x18 IRQ (only enabled by uart_rx_irq_enable) */
    b       fiq_entry           /* 0x1C FIQ */

/* Processor modes (CPSR.M) */
    .equ MODE_FIQ, 0x11
    .equ MODE_IRQ, 0x12
    .equ MODE_SVC, 0x13
    .equ MODE_ABT, 0x17
    .equ MODE_UND, 0x1B

    .section .text.init, "ax"
    .globl _start
_start:
    cpsid   if                  /* interrupts off */

    /* Only CPU0 runs the program; CPU1 (the Zynq has two A9 cores) parks. */
    mrc     p15, 0, r0, c0, c0, 5       /* MPIDR */
    ands    r0, r0, #3
    bne     park

    /* Point VBAR at our vector table and make sure SCTLR.V (high vectors) is off. */
    ldr     r0, =vectors
    mcr     p15, 0, r0, c12, c0, 0      /* VBAR */
    mrc     p15, 0, r0, c1, c0, 0       /* SCTLR */
    bic     r0, r0, #(1 << 13)
    mcr     p15, 0, r0, c1, c0, 0
    isb

    /* Every exception mode has its own banked SP: give each one a stack. */
    cps     #MODE_UND
    ldr     sp, =__und_stack_top
    cps     #MODE_ABT
    ldr     sp, =__abt_stack_top
    cps     #MODE_IRQ
    ldr     sp, =__irq_stack_top
    cps     #MODE_FIQ
    ldr     sp, =__fiq_stack_top
    cps     #MODE_SVC                   /* the program runs in SVC mode */
    ldr     sp, =__stack_top

    /* Enable the FPU (VFPv3 + NEON): coprocessors 10/11 full access, then FPEXC.EN.
     * Without this the first float instruction is an undefined-instruction exception. */
    mrc     p15, 0, r0, c1, c0, 2       /* CPACR */
    orr     r0, r0, #(0xF << 20)
    mcr     p15, 0, r0, c1, c0, 2
    isb
    mov     r0, #0x40000000
    vmsr    fpexc, r0

    /* Zero .bss (C requires uninitialised globals to start at 0). */
    ldr     r0, =__bss_start
    ldr     r1, =__bss_end
    mov     r2, #0
1:  cmp     r0, r1
    strlo   r2, [r0], #4
    blo     1b

    bl      bsp_init                    /* UART */
    mov     r0, #0                      /* argc */
    mov     r1, #0                      /* argv */
    bl      main
    bl      exit                        /* exit(main's return value), never returns */

park:
    wfe
    b       park

/* ---- Exception stubs: exception_handler(type, lr) in C, never returns ---------- */
    .text
    .macro exc_stub name, type
\name:
    mov     r0, #\type
    mov     r1, lr
    bl      exception_handler
    .endm

    exc_stub undef_entry,  1
    exc_stub svc_entry,    2
    exc_stub pabort_entry, 3
    exc_stub dabort_entry, 4
    exc_stub fiq_entry,    7

/* ---- IRQ: save what a C function may clobber, run irq_dispatch (bsp.c), return ----
 * LR_irq = interrupted instruction + 4. irq_dispatch is built general-regs-only, so the
 * VFP registers don't need saving. 6 registers = 24 bytes keeps SP 8-byte aligned. */
irq_entry:
    sub     lr, lr, #4
    push    {r0-r3, r12, lr}
    bl      irq_dispatch
    ldm     sp!, {r0-r3, r12, pc}^      /* ^ with pc: also restores CPSR from SPSR_irq */
