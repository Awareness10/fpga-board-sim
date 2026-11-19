/* Stand-in for Xilinx's xil_printf.h: a small printf on the UART, here the BSP's kprintf. */
#pragma once
#include "bsp.h"

#define xil_printf kprintf
