/* Zynq-7000 PS memory map (Zybo Z7: 1 GB DDR at 0x0000_0000).
 * The first 1 MB of DDR overlaps the on-chip memory (OCM) after boot, so programs
 * start at 0x0010_0000, like Xilinx's own standalone BSP. QEMU's xilinx-zynq-a9 machine
 * loads the ELF at these addresses and jumps to the entry point (_start). */
OUTPUT_ARCH(arm)
ENTRY(_start)

MEMORY
{
    DDR (rwx) : ORIGIN = 0x00100000, LENGTH = 16M
}

STACK_SIZE     = 64K;    /* SVC mode: main() and everything it calls */
EXC_STACK_SIZE = 1K;     /* each of UND / ABT / IRQ / FIQ mode */

SECTIONS
{
    .text : {
        KEEP(*(.vectors))            /* exception vector table, 32-byte aligned (VBAR) */
        KEEP(*(.text.init))          /* _start */
        *(.text .text.*)
    } > DDR

    .rodata : ALIGN(8) {
        *(.rodata .rodata.*)
    } > DDR

    /* Stack-unwinding tables GCC may emit for ARM; kept so the linker does not complain. */
    .ARM.exidx : ALIGN(4) {
        *(.ARM.exidx* .gnu.linkonce.armexidx.*)
    } > DDR

    .data : ALIGN(8) {
        *(.data .data.*)
    } > DDR

    .bss (NOLOAD) : ALIGN(8) {
        __bss_start = .;
        *(.bss .bss.* COMMON)
        . = ALIGN(8);
        __bss_end = .;
    } > DDR

    .stack (NOLOAD) : ALIGN(16) {
        . += EXC_STACK_SIZE; __und_stack_top = .;
        . += EXC_STACK_SIZE; __abt_stack_top = .;
        . += EXC_STACK_SIZE; __irq_stack_top = .;
        . += EXC_STACK_SIZE; __fiq_stack_top = .;
        . += STACK_SIZE;     __stack_top     = .;
    } > DDR

    /DISCARD/ : { *(.note.* .comment .ARM.attributes.discard) }
}
