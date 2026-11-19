/* Stand-in for Xilinx's xil_types.h (standalone BSP): the type names Xilinx code uses. */
#pragma once
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int32_t s32;
typedef uintptr_t UINTPTR;
typedef intptr_t INTPTR;

#ifndef TRUE
#define TRUE 1U
#define FALSE 0U
#endif
#define XIL_COMPONENT_IS_READY 0x11111111U
