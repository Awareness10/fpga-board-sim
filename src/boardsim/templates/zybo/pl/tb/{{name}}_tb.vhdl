-- Self-checking testbench for {{name}}. Run: uv run boardsim zybo test {{name}}
-- Waveform:                                   uv run boardsim zybo wave {{name}}_tb
--
-- The AXI master procedures (axil_check_write / axil_check_read, from
-- zybo/pl/sim/axil_master_pkg.vhdl) play the ARM's part: what your C driver does in
-- software, this does in simulation, cycle by cycle. A failed check stops the test.
library ieee;
use ieee.std_logic_1164.all;
use work.axil_master_pkg.all;

entity {{name}}_tb is
end entity;

architecture sim of {{name}}_tb is
    constant T : time := 10 ns;   -- 100 MHz, the usual FCLK_CLK0 of the PS

    -- Register map (same as pl/src/{{name}}.vhdl and ps/{{name}}.h)
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

    dut : entity work.{{name}}
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
        -- wr: write and check the response; rd: read and check the value
        procedure wr(addr : natural; data : std_logic_vector(31 downto 0);
                     expect_resp : std_logic_vector(1 downto 0) := AXI_OKAY) is
        begin
            axil_check_write(clk, m, s, addr, data, expect_resp);
        end procedure;
        procedure rd(addr : natural; expect : std_logic_vector(31 downto 0);
                     expect_resp : std_logic_vector(1 downto 0) := AXI_OKAY) is
        begin
            axil_check_read(clk, m, s, addr, expect, expect_resp);
        end procedure;
    begin
        aresetn <= '0';
        wait for 5 * T;
        wait until rising_edge(clk);
        aresetn <= '1';

        report "1. reset values and ID";
        rd(REG_LED, x"00000000");
        rd(REG_ID, x"C0DE0001");

        report "2. write the LEDs, read them back";
        wr(REG_LED, x"0000000A");
        assert led = "1010" report "led port is " & to_string(led) & ", expected 1010" severity failure;
        rd(REG_LED, x"0000000A");

        report "3. switches and buttons";
        sw  <= "0101";
        btn <= "0011";
        wait for 3 * T;                            -- 2-flip-flop synchroniser delay
        rd(REG_INPUT, x"00000035");

        report "4. unmapped address answers SLVERR";
        rd(REG_NONE, x"00000000", expect_resp => AXI_SLVERR);

        report "{{name}}_tb: done";
        done <= '1';
        std.env.finish;
    end process;
end architecture;
