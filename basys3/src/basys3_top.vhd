-- Basys3 top level: a counter ticking ~10x per second, shown on the 16 LEDs and
-- as 4 hex digits on the multiplexed 7-segment display.
--   btnC  = reset
--   sw(0) = pause
-- Port names match basys3/constraints/basys3_top.xdc (Digilent master XDC names).
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity basys3_top is
    generic (
        CLK_HZ  : positive := 100_000_000;  -- Basys3 oscillator
        TICK_HZ : positive := 10;           -- counter rate
        MUX_HZ  : positive := 1_000         -- 7-seg digit refresh rate
    );
    port (
        clk  : in  std_logic;
        btnC : in  std_logic;
        sw   : in  std_logic_vector(15 downto 0);
        led  : out std_logic_vector(15 downto 0);
        seg  : out std_logic_vector(6 downto 0);
        dp   : out std_logic;
        an   : out std_logic_vector(3 downto 0)
    );
end entity;

architecture rtl of basys3_top is
    constant TICK_DIV : positive := CLK_HZ / TICK_HZ;
    constant MUX_DIV  : positive := CLK_HZ / (MUX_HZ * 4);

    signal tick_cnt : natural range 0 to TICK_DIV - 1 := 0;
    signal mux_cnt  : natural range 0 to MUX_DIV - 1  := 0;
    signal tick     : std_logic := '0';
    signal sel      : unsigned(1 downto 0) := (others => '0');
    signal value    : std_logic_vector(15 downto 0);
    signal nibble   : std_logic_vector(3 downto 0);
begin
    -- Clock-enable generators (never derive new clocks from logic in an FPGA).
    process (clk)
    begin
        if rising_edge(clk) then
            tick <= '0';
            if tick_cnt = TICK_DIV - 1 then
                tick_cnt <= 0;
                tick     <= '1';
            else
                tick_cnt <= tick_cnt + 1;
            end if;

            if mux_cnt = MUX_DIV - 1 then
                mux_cnt <= 0;
                sel     <= sel + 1;
            else
                mux_cnt <= mux_cnt + 1;
            end if;
        end if;
    end process;

    u_counter : entity work.counter
        generic map (WIDTH => 16)
        port map (clk => clk, rst => btnC, en => tick and not sw(0), q => value);

    led <= value;

    -- Display multiplexing: one digit lit at a time, anodes active low.
    with sel select nibble <=
        value(3 downto 0)   when "00",
        value(7 downto 4)   when "01",
        value(11 downto 8)  when "10",
        value(15 downto 12) when others;

    with sel select an <=
        "1110" when "00",
        "1101" when "01",
        "1011" when "10",
        "0111" when others;

    u_seg : entity work.seven_seg port map (digit => nibble, seg => seg);
    dp <= '1';  -- decimal point off
end architecture;
