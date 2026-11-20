/* Stand-in for Xilinx's AXI GPIO driver (xgpio.h / xgpio_l.h, standalone BSP), with the
 * functions the tutorial uses. Same names, arguments and behaviour, so xgpio_example.c
 * compiles against this here and against the real driver in Vitis.
 *
 * Channels are numbered 1 and 2. Direction bits: 1 = input, 0 = output. */
#pragma once
#include "xil_io.h"
#include "xil_types.h"
#include "xparameters.h"
#include "xstatus.h"

/* Register offsets (xgpio_l.h, PG144), matching zybo/pl/src/axi_gpio.vhdl */
#define XGPIO_DATA_OFFSET  0x0
#define XGPIO_TRI_OFFSET   0x4
#define XGPIO_DATA2_OFFSET 0x8
#define XGPIO_TRI2_OFFSET  0xC
#define XGPIO_CHAN_OFFSET  8   /* channel 2 registers = channel 1 registers + 8 */

#define XGpio_ReadReg(BaseAddress, RegOffset) Xil_In32((BaseAddress) + (RegOffset))
#define XGpio_WriteReg(BaseAddress, RegOffset, Data) Xil_Out32((BaseAddress) + (RegOffset), (Data))

typedef struct {
#ifndef SDT
    u16 DeviceId;
#endif
    UINTPTR BaseAddress;
    int InterruptPresent;
    int IsDual;
} XGpio_Config;

typedef struct {
    UINTPTR BaseAddress;
    u32 IsReady;
    int InterruptPresent;
    int IsDual;
} XGpio;

/* Non-SDT: DeviceId is XPAR_GPIO_0_DEVICE_ID. SDT: pass the base address instead. */
#ifndef SDT
int XGpio_Initialize(XGpio *InstancePtr, u16 DeviceId);
#else
int XGpio_Initialize(XGpio *InstancePtr, UINTPTR BaseAddress);
#endif

void XGpio_SetDataDirection(XGpio *InstancePtr, unsigned Channel, u32 DirectionMask);
u32 XGpio_GetDataDirection(XGpio *InstancePtr, unsigned Channel);
u32 XGpio_DiscreteRead(XGpio *InstancePtr, unsigned Channel);
void XGpio_DiscreteWrite(XGpio *InstancePtr, unsigned Channel, u32 Data);
void XGpio_DiscreteSet(XGpio *InstancePtr, unsigned Channel, u32 Mask);    /* read, OR, write */
void XGpio_DiscreteClear(XGpio *InstancePtr, unsigned Channel, u32 Mask);  /* read, AND NOT, write */
