/******************************************************************************
* Copyright (C) 2002 - 2021 Xilinx, Inc.  All rights reserved.
* Copyright (c) 2022 - 2023 Advanced Micro Devices, Inc. All Rights Reserved.
* SPDX-License-Identifier: MIT
******************************************************************************/

/*****************************************************************************/
/**
* @file xgpio_example.c
*
* Peronnin tutorial, Roadmap step 18: the blink example changed to copy the push-buttons
* (GPIO channel 2) to the LEDs (channel 1). The changes from "Code changes from led
* blinking to btns copy to leds" are marked with  // CHANGED.
******************************************************************************/

/***************************** Include Files *********************************/

#include "xparameters.h"
#include "xgpio.h"
#include "xil_printf.h"

/************************** Constant Definitions *****************************/

#define LEDS 0x0F   /* all 4 LEDs */                                    // CHANGED (was LED 0x01)

#ifndef SDT
#define GPIO_EXAMPLE_DEVICE_ID  XPAR_GPIO_0_DEVICE_ID
#else
#define	XGPIO_AXI_BASEADDRESS	XPAR_XGPIO_0_BASEADDR
#endif

#define LED_DELAY     10000000

#define LED_CHANNEL 1
#define BTN_CHANNEL 2                                                   // CHANGED (added)

/************************** Variable Definitions *****************************/

XGpio Gpio; /* The Instance of the GPIO Driver */

int main(void)
{
	int Status;
	/* volatile int Delay;  removed: no delay loops any more */      // CHANGED

	/* Initialize the GPIO driver */
#ifndef SDT
	Status = XGpio_Initialize(&Gpio, GPIO_EXAMPLE_DEVICE_ID);
#else
	Status = XGpio_Initialize(&Gpio, XGPIO_AXI_BASEADDRESS);
#endif
	if (Status != XST_SUCCESS) {
		xil_printf("Gpio Initialization Failed\r\n");
		return XST_FAILURE;
	}

	/* Set the direction for all signals as inputs except the LED output */
	XGpio_SetDataDirection(&Gpio, LED_CHANNEL, ~LEDS);              // CHANGED (~LED -> ~LEDS)
	XGpio_SetDataDirection(&Gpio, BTN_CHANNEL, 0xFFFFFFFF);         // CHANGED (added)

	/* Loop forever copying the buttons to the LEDs */
	while (1) {
		u32 btn = XGpio_DiscreteRead(&Gpio, BTN_CHANNEL);       // CHANGED (added)
		XGpio_DiscreteWrite(&Gpio, LED_CHANNEL, btn);           // CHANGED (LED -> btn)
		/* the delay loops and XGpio_DiscreteClear are removed */   // CHANGED
	}

}
