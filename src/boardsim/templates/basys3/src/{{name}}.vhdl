-- {{name}}: top level for the Basys3.
--   led(14:0) = sw(14:0)
--   led(15)   blinks once per second; btnC = reset
--
-- Port names match the Basys3 master XDC (clk, sw, btnC/U/L/R/D, led, seg, dp, an):
-- the board view connects ports by these names, and constraints/{{name}}.xdc gives
-- their pins. Add seg/dp/an (7-segment) or other buttons as you need them.
--
-- CLK_HZ: compute every divider from it (never hard-code 100_000_000). The board view
-- then runs the design with a slower clock at real speed, and the testbench can use a
-- tiny value so it finishes quickly.
library ieee;
use ieee.std_logic_1164.all;

entity {{name}} is
    generic (
        CLK_HZ : positive := 100_000_000   -- the Basys3 oscillator
    );
    port (
        clk  : in  std_logic;
        btnC : in  std_logic;
        sw   : in  std_logic_vector(15 downto 0);
        led  : out std_logic_vector(15 downto 0)
    );
end entity;

architecture rtl of {{name}} is
    constant HALF_SECOND : positive := CLK_HZ / 2;
    signal count : natural range 0 to HALF_SECOND - 1 := 0;
    signal blink : std_logic := '0';
begin
    process (clk)
    begin
        if rising_edge(clk) then
            if btnC = '1' then
                count <= 0;
                blink <= '0';
            elsif count = HALF_SECOND - 1 then
                count <= 0;
                blink <= not blink;
            else
                count <= count + 1;
            end if;
        end if;
    end process;

    led(14 downto 0) <= sw(14 downto 0);
    led(15) <= blink;
end architecture;
