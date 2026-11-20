-- The PL half of the Peronnin tutorial's block design (Roadmap steps 3-5), written out by hand:
--   ZYNQ7 PS --M_AXI_GP0--> axi_gpio_0 (0x4120_0000)
--                             GPIO  (channel 1): 4 outputs -> LEDs     "leds_4bits"
--                             GPIO2 (channel 2): 4 inputs  <- buttons  "btns_4bits"
-- In Vivado, block automation and the board interfaces do this wiring. Here the AXI port
-- comes from a testbench, which plays the PS.
--
-- The switches (sw) are on the board but not wired to the GPIO, just like in the tutorial's
-- block design.
library ieee;
use ieee.std_logic_1164.all;

entity zybo_gpio_top is
    port (
        s_axi_aclk    : in  std_logic;
        s_axi_aresetn : in  std_logic;
        s_axi_awaddr  : in  std_logic_vector(8 downto 0);
        s_axi_awvalid : in  std_logic;
        s_axi_awready : out std_logic;
        s_axi_wdata   : in  std_logic_vector(31 downto 0);
        s_axi_wstrb   : in  std_logic_vector(3 downto 0);
        s_axi_wvalid  : in  std_logic;
        s_axi_wready  : out std_logic;
        s_axi_bresp   : out std_logic_vector(1 downto 0);
        s_axi_bvalid  : out std_logic;
        s_axi_bready  : in  std_logic;
        s_axi_araddr  : in  std_logic_vector(8 downto 0);
        s_axi_arvalid : in  std_logic;
        s_axi_arready : out std_logic;
        s_axi_rdata   : out std_logic_vector(31 downto 0);
        s_axi_rresp   : out std_logic_vector(1 downto 0);
        s_axi_rvalid  : out std_logic;
        s_axi_rready  : in  std_logic;
        led : out std_logic_vector(3 downto 0);
        btn : in  std_logic_vector(3 downto 0);
        sw  : in  std_logic_vector(3 downto 0)
    );
end entity;

architecture rtl of zybo_gpio_top is
begin
    axi_gpio_0 : entity work.axi_gpio
        generic map (
            C_GPIO_WIDTH   => 4, C_ALL_OUTPUTS  => 1,    -- leds_4bits
            C_IS_DUAL      => 1,
            C_GPIO2_WIDTH  => 4, C_ALL_INPUTS_2 => 1)    -- btns_4bits
        port map (
            s_axi_aclk => s_axi_aclk, s_axi_aresetn => s_axi_aresetn,
            s_axi_awaddr => s_axi_awaddr, s_axi_awvalid => s_axi_awvalid, s_axi_awready => s_axi_awready,
            s_axi_wdata => s_axi_wdata, s_axi_wstrb => s_axi_wstrb, s_axi_wvalid => s_axi_wvalid,
            s_axi_wready => s_axi_wready,
            s_axi_bresp => s_axi_bresp, s_axi_bvalid => s_axi_bvalid, s_axi_bready => s_axi_bready,
            s_axi_araddr => s_axi_araddr, s_axi_arvalid => s_axi_arvalid, s_axi_arready => s_axi_arready,
            s_axi_rdata => s_axi_rdata, s_axi_rresp => s_axi_rresp, s_axi_rvalid => s_axi_rvalid,
            s_axi_rready => s_axi_rready,
            gpio_io_i  => "0000",    -- all-outputs channel: no inputs
            gpio_io_o  => led,
            gpio_io_t  => open,
            gpio2_io_i => btn,
            gpio2_io_o => open,
            gpio2_io_t => open);
end architecture;
