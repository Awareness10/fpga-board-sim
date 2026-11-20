-- Exhaustive testbench for the 7-segment decoder.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.finish;

entity seven_seg_tb is
end entity;

architecture sim of seven_seg_tb is
    type patterns_t is array (0 to 15) of std_logic_vector(6 downto 0);
    constant EXPECTED : patterns_t := (
        "1000000", "1111001", "0100100", "0110000", "0011001", "0010010", "0000010", "1111000",
        "0000000", "0010000", "0001000", "0000011", "1000110", "0100001", "0000110", "0001110");
    signal digit : std_logic_vector(3 downto 0);
    signal seg   : std_logic_vector(6 downto 0);
begin
    dut : entity work.seven_seg port map (digit => digit, seg => seg);

    process
    begin
        for i in 0 to 15 loop
            digit <= std_logic_vector(to_unsigned(i, 4));
            wait for 1 ns;
            assert seg = EXPECTED(i)
                report "digit " & integer'image(i) & " wrong pattern" severity error;
        end loop;
        report "seven_seg_tb: done";
        finish;
    end process;
end architecture;
