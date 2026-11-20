-- Self-checking testbench for {{name}}. Run: uv run boardsim basys3 test {{name}}
-- Waveform:                                   uv run boardsim basys3 wave {{name}}_tb
-- A failed assert stops the test (severity failure) and the test fails.
library ieee;
use ieee.std_logic_1164.all;

entity {{name}}_tb is
end entity;

architecture sim of {{name}}_tb is
    -- The design only counts clock cycles, so the testbench tells it the clock is 1 kHz
    -- (half a second = 500 cycles) but runs it at 1 MHz: 500 cycles take 0.5 ms here.
    -- (Test runs stop after 10 ms of simulated time; a testbench must finish before.)
    constant CLK_HZ : positive := 1_000;
    constant T      : time := 1 us;
    signal clk, done : std_logic := '0';
    signal btnC : std_logic := '1';
    signal sw   : std_logic_vector(15 downto 0) := (others => '0');
    signal led  : std_logic_vector(15 downto 0);
begin
    clk <= not clk after T / 2 when done = '0';

    dut : entity work.{{name}}
        generic map (CLK_HZ => CLK_HZ)
        port map (clk => clk, btnC => btnC, sw => sw, led => led);

    stimulus : process
    begin
        wait for 3 * T;
        btnC <= '0';

        report "1. LEDs follow the switches";
        sw <= x"1234";
        wait for T;
        assert led(14 downto 0) = sw(14 downto 0)
            report "led is " & to_hstring(led) & ", expected the switches" severity failure;

        report "2. led(15) toggles after half a second";
        assert led(15) = '0' report "led(15) not off after reset" severity failure;
        wait for 500 * T;
        assert led(15) = '1' report "led(15) did not turn on" severity failure;

        report "{{name}}_tb: done";
        done <= '1';
        std.env.finish;
    end process;
end architecture;
