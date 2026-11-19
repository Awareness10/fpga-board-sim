-- Testbench for zybo_gpio_top: the PS process below does over AXI what the tutorial's
-- xgpio_example.c does through the XGpio driver, register access by register access,
-- while a "user" process presses buttons.
--
--   XGpio_SetDataDirection(&Gpio, ch, mask)  ->  write GPIO_TRI / GPIO2_TRI
--   XGpio_DiscreteWrite(&Gpio, ch, value)    ->  write GPIO_DATA / GPIO2_DATA
--   XGpio_DiscreteRead(&Gpio, ch)            ->  read  GPIO_DATA / GPIO2_DATA
--   XGpio_DiscreteClear(&Gpio, ch, mask)     ->  read DATA, clear the mask bits, write it back
library ieee;
use ieee.std_logic_1164.all;
use work.axil_master_pkg.all;

entity zybo_gpio_tb is
end entity;

architecture sim of zybo_gpio_tb is
    constant T : time := 10 ns;

    -- AXI GPIO register offsets (PG144), the same as XGPIO_*_OFFSET in xgpio_l.h
    constant GPIO_DATA  : natural := 16#000#;
    constant GPIO_TRI   : natural := 16#004#;
    constant GPIO2_DATA : natural := 16#008#;
    constant GPIO2_TRI  : natural := 16#00C#;

    signal clk, done, sw_done : std_logic := '0';
    signal aresetn : std_logic := '0';
    signal m : axil_m2s := AXIL_M2S_IDLE;
    signal s : axil_s2m;
    signal led : std_logic_vector(3 downto 0);
    signal btn, sw : std_logic_vector(3 downto 0) := (others => '0');
    signal phase : natural := 0;   -- 0 = setup, 1 = blink, 2 = buttons -> LEDs loop

    function lamps(v : std_logic_vector(3 downto 0)) return string is
        variable r : string(1 to 4);
    begin
        for i in 3 downto 0 loop
            if v(i) = '1' then r(4 - i) := '*'; else r(4 - i) := '.'; end if;
        end loop;
        return r;
    end function;
begin
    clk <= not clk after T / 2 when done = '0';

    dut : entity work.zybo_gpio_top
        port map (
            s_axi_aclk => clk, s_axi_aresetn => aresetn,
            s_axi_awaddr => m.awaddr(8 downto 0), s_axi_awvalid => m.awvalid, s_axi_awready => s.awready,
            s_axi_wdata => m.wdata, s_axi_wstrb => m.wstrb, s_axi_wvalid => m.wvalid, s_axi_wready => s.wready,
            s_axi_bresp => s.bresp, s_axi_bvalid => s.bvalid, s_axi_bready => m.bready,
            s_axi_araddr => m.araddr(8 downto 0), s_axi_arvalid => m.arvalid, s_axi_arready => s.arready,
            s_axi_rdata => s.rdata, s_axi_rresp => s.rresp, s_axi_rvalid => s.rvalid, s_axi_rready => m.rready,
            led => led, btn => btn, sw => sw);

    -- The ARM running the tutorial code.
    ps : process
        variable d, r : std_logic_vector(31 downto 0);
        variable resp : std_logic_vector(1 downto 0);
        procedure wr(addr : natural; data : std_logic_vector(31 downto 0)) is
        begin
            axil_check_write(clk, m, s, addr, data);
        end procedure;
        procedure rd(addr : natural; expect : std_logic_vector(31 downto 0)) is
        begin
            axil_check_read(clk, m, s, addr, expect);
        end procedure;
    begin
        aresetn <= '0';
        wait for 5 * T;
        wait until rising_edge(clk);
        aresetn <= '1';

        report "1. after reset: channel 1 all inputs (TRI=1), LEDs off";
        rd(GPIO_TRI, x"0000000F");
        rd(GPIO2_TRI, x"0000000F");
        rd(GPIO_DATA, x"00000000");
        assert led = "0000" report "LEDs not off after reset" severity error;

        report "2. original example: blink LED 0 (LED = 0x01)";
        phase <= 1;
        wr(GPIO_TRI, x"FFFFFFFE");                    -- SetDataDirection(LED_CHANNEL, ~LED)
        rd(GPIO_TRI, x"0000000E");                    --   only 4 bits exist
        for i in 1 to 2 loop
            wr(GPIO_DATA, x"00000001");               -- DiscreteWrite(LED_CHANNEL, LED)
            assert led = "0001" report "LED 0 should be on, LEDs = " & lamps(led) severity error;
            report "   blink on : LD3..LD0 " & lamps(led);
            axil_read(clk, m, s, GPIO_DATA, d, resp); -- DiscreteClear(LED_CHANNEL, LED):
            wr(GPIO_DATA, d and x"FFFFFFFE");         --   read, clear bit 0, write back
            assert led = "0000" report "LED 0 should be off, LEDs = " & lamps(led) severity error;
            report "   blink off: LD3..LD0 " & lamps(led);
        end loop;

        report "3. modified example: copy the buttons to the LEDs (LEDS = 0x0F)";
        wr(GPIO_TRI, x"FFFFFFF0");                    -- SetDataDirection(LED_CHANNEL, ~LEDS)
        wr(GPIO2_TRI, x"FFFFFFFF");                   -- SetDataDirection(BTN_CHANNEL, 0xFFFFFFFF)
        phase <= 2;
        while sw_done = '0' loop                      -- while (1) {
            axil_read(clk, m, s, GPIO2_DATA, r, resp);--   u32 btn = DiscreteRead(BTN_CHANNEL);
            wr(GPIO_DATA, r);                         --   DiscreteWrite(LED_CHANNEL, btn);
        end loop;                                     -- }

        report "zybo_gpio_tb: done";
        done <= '1';
        std.env.finish;
    end process;

    -- The person at the board: press buttons, check the LEDs follow.
    user : process
        procedure press(b : std_logic_vector(3 downto 0)) is
        begin
            btn <= b;
            -- Within 20 cycles: 2 for the synchroniser + one read and one write over AXI.
            for i in 1 to 20 loop
                wait until rising_edge(clk);
                exit when led = b;
            end loop;
            assert led = b report "BTN3..BTN0 " & lamps(b) & " but LD3..LD0 " & lamps(led) severity error;
            report "   " & "BTN3..BTN0 " & lamps(b) & "  ->  LD3..LD0 " & lamps(led);
        end procedure;
    begin
        wait until phase = 2;
        wait for 10 * T;
        press("0001");
        press("0011");
        press("1000");
        press("0000");
        press("1111");
        -- The switches are not wired to the GPIO: they must have no effect.
        sw <= "1010";
        wait for 20 * T;
        assert led = "1111" report "unconnected inputs changed the LEDs" severity error;
        press("0000");
        sw_done <= '1';
        wait;
    end process;
end architecture;
