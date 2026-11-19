/* Calling an ARM assembly function (sum.S) from C. */
#include "bsp.h"

uint32_t sum_array(const uint32_t *a, uint32_t n);

int main(void)
{
    static const uint32_t data[] = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3};
    uint32_t n = sizeof data / sizeof *data;

    uint32_t s = sum_array(data, n);
    kprintf("sum_array(pi digits) = %u\n", s);
    CHECK(s == 39);
    CHECK(sum_array(data, 0) == 0);
    CHECK(sum_array(data, 1) == 3);
    return 0;
}
