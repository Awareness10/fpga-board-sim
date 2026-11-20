/* {{name}}: a program for the tutorial's block design (Zynq PS + axi_gpio_0):
 *     GPIO  (channel 1) = LD3..LD0     (outputs)
 *     GPIO2 (channel 2) = BTN3..BTN0   (inputs)
 * Starting point: copy the buttons to the LEDs.
 *
 * The same file runs on the emulated board (`boardsim zybo run {{name}}`, with the board
 * view in the browser) and on the real Zybo through Vitis (`boardsim zybo vitis {{name}}`,
 * then `boardsim zybo jtag {{name}}`). The Xilinx driver API (XGpio_*) is the real one in
 * Vitis; in the emulator, zybo/ps/xil/ has stand-ins with the same names. */
#include "xparameters.h"
#include "xgpio.h"
#include "xil_printf.h"

#define LED_CHANNEL 1
#define BTN_CHANNEL 2

XGpio Gpio;

int main(void)
{
#ifndef SDT
    int status = XGpio_Initialize(&Gpio, XPAR_GPIO_0_DEVICE_ID);
#else
    int status = XGpio_Initialize(&Gpio, XPAR_XGPIO_0_BASEADDR);
#endif
    if (status != XST_SUCCESS) {
        xil_printf("GPIO initialization failed\r\n");
        return XST_FAILURE;
    }

    XGpio_SetDataDirection(&Gpio, LED_CHANNEL, 0x0);         /* 0 = output */
    XGpio_SetDataDirection(&Gpio, BTN_CHANNEL, 0xFFFFFFFF);  /* 1 = input */
    xil_printf("{{name}}: buttons -> LEDs\r\n");

    while (1) {
        u32 btn = XGpio_DiscreteRead(&Gpio, BTN_CHANNEL);
        XGpio_DiscreteWrite(&Gpio, LED_CHANNEL, btn);
    }
}
