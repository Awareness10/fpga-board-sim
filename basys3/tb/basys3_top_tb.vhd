-- Simulates the Basys3 top level with shrunken clock dividers so things happen
-- in a few microseconds instead of seconds. Open the waveform with: boardsim basys3 wave basys3_top_tb
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.finish;

entity basys3_top_tb is
end entity;

architecture sim of basys3_top_tb is
    signal clk  : std_logic := '0';
    signal btnC : std_logic := '1';
    signal sw   : std_logic_vector(15 downto 0) := (others => '0');
    signal led  : std_logic_vector(15 downto 0);
    signal seg  : std_logic_vector(6 downto 0);
    signal dp   : std_logic;
    signal an   : std_logic_vector(3 downto 0);
begin
    clk <= not clk after 5 ns;

    -- 100 "Hz" clock, 10 ticks/s -> one count every 10 clocks.
    dut : entity work.basys3_top
        generic map (CLK_HZ => 100, TICK_HZ => 10, MUX_HZ => 5)
        port map (clk => clk, btnC => btnC, sw => sw, led => led, seg => seg, dp => dp, an => an);

    process
        variable held : std_logic_vector(15 downto 0);
    begin
        wait for 20 ns;
        btnC <= '0';
        wait for 1 us;                 -- 100 clocks -> ~10 counts
        assert unsigned(led) >= 9 and unsigned(led) <= 10
            report "unexpected count " & integer'image(to_integer(unsigned(led))) severity error;

        sw(0) <= '1';                  -- pause
        wait for 20 ns;
        held := led;
        report "paused at " & integer'image(to_integer(unsigned(held)));
        wait for 500 ns;
        assert led = held report "counted while paused" severity error;

        report "basys3_top_tb: done";
        finish;
    end process;
end architecture;
