/* uint32_t sum_array(const uint32_t *a, uint32_t n)
 * AAPCS calling convention: arguments in r0-r3, result in r0, r4-r11 must be preserved,
 * lr holds the return address. */
    .syntax unified
    .arm
    .text
    .globl sum_array
    .type  sum_array, %function
sum_array:
    mov     r2, #0              /* r2 = running sum */
1:  subs    r1, r1, #1          /* n--, sets the flags */
    ldrhs   r3, [r0], #4        /* if n was > 0: r3 = *a++   (conditional + post-increment) */
    addhs   r2, r2, r3          /*               sum += r3 */
    bhs     1b
    mov     r0, r2
    bx      lr
    .size sum_array, . - sum_array
