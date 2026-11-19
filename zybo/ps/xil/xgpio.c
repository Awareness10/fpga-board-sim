/* Minimal re-implementation of Xilinx's XGpio driver (see xgpio.h). */
#include "xgpio.h"
#include "bsp.h"

/* What Vitis generates as xgpio_g.c: one entry per AXI GPIO in the design. */
static const XGpio_Config XGpio_ConfigTable[XPAR_XGPIO_NUM_INSTANCES] = {
    {
#ifndef SDT
        .DeviceId = XPAR_GPIO_0_DEVICE_ID,
#endif
        .BaseAddress = XPAR_GPIO_0_BASEADDR,
        .InterruptPresent = XPAR_GPIO_0_INTERRUPT_PRESENT,
        .IsDual = XPAR_GPIO_0_IS_DUAL,
    },
};

/* The real driver uses Xil_AssertVoid for these; report and stop instead.
 * Like Xil_Assert*, the check is inline (a few compares) and only the report is a call. */
static __attribute__((noinline, noreturn)) void bad_channel(const XGpio *g, unsigned ch, const char *fn)
{
    if (g == 0 || g->IsReady != XIL_COMPONENT_IS_READY)
        kprintf("%s: XGpio not initialised (call XGpio_Initialize first)\n", fn);
    else
        kprintf("%s: invalid channel %u (this GPIO has %s)\n", fn, ch, g->IsDual ? "channels 1 and 2" : "only channel 1");
    exit(1);
}

static inline __attribute__((always_inline)) void check_channel(const XGpio *g, unsigned ch, const char *fn)
{
    if (__builtin_expect(g == 0 || g->IsReady != XIL_COMPONENT_IS_READY
                         || (ch != 1 && !(ch == 2 && g->IsDual)), 0))
        bad_channel(g, ch, fn);
}

#define CHAN(ch) (((ch) - 1) * XGPIO_CHAN_OFFSET)

#ifndef SDT
int XGpio_Initialize(XGpio *InstancePtr, u16 DeviceId)
#else
int XGpio_Initialize(XGpio *InstancePtr, UINTPTR BaseAddress)
#endif
{
    for (int i = 0; i < XPAR_XGPIO_NUM_INSTANCES; i++) {
        const XGpio_Config *c = &XGpio_ConfigTable[i];
#ifndef SDT
        if (c->DeviceId != DeviceId)
            continue;
#else
        if (c->BaseAddress != BaseAddress)
            continue;
#endif
        InstancePtr->BaseAddress = c->BaseAddress;
        InstancePtr->InterruptPresent = c->InterruptPresent;
        InstancePtr->IsDual = c->IsDual;
        InstancePtr->IsReady = XIL_COMPONENT_IS_READY;
        return XST_SUCCESS;
    }
    InstancePtr->IsReady = 0;
    return XST_DEVICE_NOT_FOUND;
}

void XGpio_SetDataDirection(XGpio *InstancePtr, unsigned Channel, u32 DirectionMask)
{
    check_channel(InstancePtr, Channel, __func__);
    XGpio_WriteReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_TRI_OFFSET, DirectionMask);
}

u32 XGpio_GetDataDirection(XGpio *InstancePtr, unsigned Channel)
{
    check_channel(InstancePtr, Channel, __func__);
    return XGpio_ReadReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_TRI_OFFSET);
}

u32 XGpio_DiscreteRead(XGpio *InstancePtr, unsigned Channel)
{
    check_channel(InstancePtr, Channel, __func__);
    return XGpio_ReadReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_DATA_OFFSET);
}

void XGpio_DiscreteWrite(XGpio *InstancePtr, unsigned Channel, u32 Data)
{
    check_channel(InstancePtr, Channel, __func__);
    XGpio_WriteReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_DATA_OFFSET, Data);
}

void XGpio_DiscreteSet(XGpio *InstancePtr, unsigned Channel, u32 Mask)
{
    check_channel(InstancePtr, Channel, __func__);
    u32 cur = XGpio_ReadReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_DATA_OFFSET);
    XGpio_WriteReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_DATA_OFFSET, cur | Mask);
}

void XGpio_DiscreteClear(XGpio *InstancePtr, unsigned Channel, u32 Mask)
{
    check_channel(InstancePtr, Channel, __func__);
    u32 cur = XGpio_ReadReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_DATA_OFFSET);
    XGpio_WriteReg(InstancePtr->BaseAddress, CHAN(Channel) + XGPIO_DATA_OFFSET, cur & ~Mask);
}
