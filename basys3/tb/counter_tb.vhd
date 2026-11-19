-- Self-checking testbench for counter. Run: boardsim basys3 test
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.finish;

entity counter_tb is
end entity;

architecture sim of counter_tb is
    constant PERIOD : time := 10 ns;   -- 100 MHz, like the Basys3
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal en  : std_logic := '0';
    signal q   : std_logic_vector(3 downto 0);
begin
    clk <= not clk after PERIOD / 2;

    dut : entity work.counter
        generic map (WIDTH => 4)
        port map (clk => clk, rst => rst, en => en, q => q);

    stimulus : process
    begin
        wait until rising_edge(clk);
        rst <= '0';
        wait until rising_edge(clk);
        assert q = "0000" report "not reset" severity error;

        -- Disabled: must hold.
        wait for 3 * PERIOD;
        assert q = "0000" report "counted while disabled" severity error;

        -- Count 20 cycles: 4-bit counter wraps to 20 mod 16 = 4.
        en <= '1';
        for i in 1 to 20 loop
            wait until rising_edge(clk);
        end loop;
        en <= '0';
        wait until rising_edge(clk);
        assert unsigned(q) = 4
            report "expected 4, got " & integer'image(to_integer(unsigned(q)))
            severity error;

        report "counter_tb: done";
        finish;
    end process;
end architecture;
