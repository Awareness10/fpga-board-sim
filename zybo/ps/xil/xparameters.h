/* What Vitis would generate as xparameters.h from the tutorial's .xsa (Roadmap step 12),
 * written by hand: one AXI GPIO (axi_gpio_0) at Vivado's default address on M_AXI_GP0,
 * dual channel, no interrupt. If your Vivado Address Editor shows another address,
 * change it here (and in the real flow, Vitis picks it up from the .xsa). */
#pragma once

#define XPAR_XGPIO_NUM_INSTANCES 1

/* Classic (non-SDT) names: look up by device ID */
#define XPAR_GPIO_0_DEVICE_ID          0
#define XPAR_GPIO_0_BASEADDR           0x41200000
#define XPAR_GPIO_0_HIGHADDR           0x4120FFFF
#define XPAR_GPIO_0_INTERRUPT_PRESENT  0
#define XPAR_GPIO_0_IS_DUAL            1

/* System-device-tree (SDT) names, used by the Vitis 2023.2 unified IDE */
#define XPAR_XGPIO_0_BASEADDR          XPAR_GPIO_0_BASEADDR
#define XPAR_AXI_GPIO_0_BASEADDR       XPAR_GPIO_0_BASEADDR
