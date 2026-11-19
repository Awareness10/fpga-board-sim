-- Self-checking testbench for axi_lite_leds. The AXI master in sim/axil_master_pkg.vhd
-- plays the part of the ARM (the PS's M_AXI_GP0 port): what the C driver does in
-- software, this does in simulation, cycle by cycle.
library ieee;
use ieee.std_logic_1164.all;
use work.axil_master_pkg.all;

entity axi_lite_leds_tb is
end entity;

architecture sim of axi_lite_leds_tb is
    constant T : time := 10 ns;   -- 100 MHz, the usual FCLK_CLK0 of the PS

    -- Register map (same as the DUT header and zybo/ps/drivers/axi_leds.h)
    constant REG_LED   : natural := 16#0#;
    constant REG_INPUT : natural := 16#4#;
    constant REG_ID    : natural := 16#8#;
    constant REG_NONE  : natural := 16#C#;

    signal clk, done : std_logic := '0';
    signal aresetn   : std_logic := '0';
    signal m : axil_m2s := AXIL_M2S_IDLE;
    signal s : axil_s2m;
    signal led, sw, btn : std_logic_vector(3 downto 0) := (others => '0');
begin
    clk <= not clk after T / 2 when done = '0';

    dut : entity work.axi_lite_leds
        port map (
            s_axi_aclk => clk, s_axi_aresetn => aresetn,
            s_axi_awaddr => m.awaddr(3 downto 0), s_axi_awprot => "000", s_axi_awvalid => m.awvalid,
            s_axi_awready => s.awready,
            s_axi_wdata => m.wdata, s_axi_wstrb => m.wstrb, s_axi_wvalid => m.wvalid, s_axi_wready => s.wready,
            s_axi_bresp => s.bresp, s_axi_bvalid => s.bvalid, s_axi_bready => m.bready,
            s_axi_araddr => m.araddr(3 downto 0), s_axi_arprot => "000", s_axi_arvalid => m.arvalid,
            s_axi_arready => s.arready,
            s_axi_rdata => s.rdata, s_axi_rresp => s.rresp, s_axi_rvalid => s.rvalid, s_axi_rready => m.rready,
            led => led, sw => sw, btn => btn);

    stimulus : process
        -- Short names for this testbench: the clock and bus signals are always the same.
        procedure wr(addr : natural; data : std_logic_vector(31 downto 0);
                     expect_resp : std_logic_vector(1 downto 0) := AXI_OKAY;
                     strb : std_logic_vector(3 downto 0) := "1111"; w_delay, b_delay : natural := 0) is
        begin
            axil_check_write(clk, m, s, addr, data, expect_resp, strb, w_delay, b_delay);
        end procedure;
        procedure rd(addr : natural; expect : std_logic_vector(31 downto 0);
                     expect_resp : std_logic_vector(1 downto 0) := AXI_OKAY; r_delay : natural := 0) is
        begin
            axil_check_read(clk, m, s, addr, expect, expect_resp, r_delay);
        end procedure;
    begin
        aresetn <= '0';
        wait for 5 * T;
        wait until rising_edge(clk);
        aresetn <= '1';

        report "1. reset values and ID";
        assert led = "0000" report "LEDs not off after reset" severity error;
        rd(REG_LED, x"00000000");
        rd(REG_ID, x"4C454453");

        report "2. write LEDs, read them back";
        wr(REG_LED, x"0000000A");
        assert led = "1010" report "led port is " & to_string(led) & ", expected 1010" severity error;
        rd(REG_LED, x"0000000A");
        wr(REG_LED, x"FFFFFFFF");                 -- only bits 3:0 exist
        rd(REG_LED, x"0000000F");

        report "3. byte strobe 0 leaves the register alone";
        wr(REG_LED, x"00000003", strb => "0000");
        rd(REG_LED, x"0000000F");

        report "4. switches and buttons";
        sw  <= "0101";
        btn <= "0011";
        wait for 3 * T;                            -- 2-FF synchroniser delay
        rd(REG_INPUT, x"00000035");

        report "5. read-only registers ignore writes";
        wr(REG_ID, x"DEADBEEF");
        rd(REG_ID, x"4C454453");
        wr(REG_INPUT, x"FFFFFFFF");
        rd(REG_INPUT, x"00000035");

        report "6. unmapped address answers SLVERR";
        rd(REG_NONE, x"00000000", expect_resp => AXI_SLVERR);
        wr(REG_NONE, x"00000001", expect_resp => AXI_SLVERR);
        rd(REG_LED, x"0000000F");                  -- and changed nothing

        report "7. slow master: W after AW, late BREADY / RREADY";
        wr(REG_LED, x"00000006", w_delay => 4, b_delay => 6);
        assert led = "0110" report "led port is " & to_string(led) & ", expected 0110" severity error;
        rd(REG_LED, x"00000006", r_delay => 5);

        report "8. reset in the middle clears the LEDs";
        aresetn <= '0';
        wait until rising_edge(clk);
        aresetn <= '1';
        wait until rising_edge(clk);
        assert led = "0000" report "LEDs not off after second reset" severity error;

        report "axi_lite_leds_tb: done";
        done <= '1';
        std.env.finish;
    end process;
end architecture;
