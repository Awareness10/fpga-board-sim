-- Simulation-only helpers: a text "view" of the Basys3 board, so testbenches can
-- show what the LEDs and the 7-segment display would look like.
-- Not synthesizable; never put this in a design that goes to the FPGA.
library ieee;
use ieee.std_logic_1164.all;
use std.textio.all;

package basys3_sim_pkg is
    -- 7-segment patterns, listed left to right.
    type seg_vector is array (natural range <>) of std_logic_vector(6 downto 0);
    -- Active-low segment pattern (seg(6..0) = g f e d c b a) -> '0'..'9', 'A'..'F',
    -- ' ' when every segment is off, '?' for anything else.
    function seg_to_char(seg : std_logic_vector(6 downto 0)) return character;

    -- "*" for a lit LED, "." for an unlit one, grouped by 4, leftmost = highest index.
    function bits_to_string(v : std_logic_vector; on_c : character := '*'; off_c : character := '.') return string;

    -- digits(1) = leftmost display digit (an(3)) ... digits(4) = rightmost (an(0)).
    -- dots(i) = '1' when the decimal point of the digit on an(i) is lit.
    -- Example: "012.5"
    function display_to_string(digits : string(1 to 4); dots : std_logic_vector(3 downto 0)) return string;

    -- Prints one line, e.g.  "[board] sw 0000 0000 0000 0011 | led .... .... .... ..**"
    procedure print_board(sw : std_logic_vector(15 downto 0); led : std_logic_vector(15 downto 0));
    procedure print_line(s : string);

    -- Draws 7-segment digits as ASCII art, left to right, e.g.
    --      _       _
    --   |  _|  _| |_
    --   | |_   _|. _|
    -- dots: '1' = decimal point lit, same left-to-right order as segs.
    procedure print_segments(segs : seg_vector; dots : std_logic_vector; indent : string := "  ");
end package;

package body basys3_sim_pkg is
    function seg_to_char(seg : std_logic_vector(6 downto 0)) return character is
        type table_t is array (0 to 15) of std_logic_vector(6 downto 0);
        constant TABLE : table_t := (
            "1000000", "1111001", "0100100", "0110000", "0011001", "0010010", "0000010", "1111000",
            "0000000", "0010000", "0001000", "0000011", "1000110", "0100001", "0000110", "0001110");
        constant HEX : string(1 to 16) := "0123456789ABCDEF";
    begin
        if seg = "1111111" then
            return ' ';
        end if;
        for i in TABLE'range loop
            if seg = TABLE(i) then
                return HEX(i + 1);
            end if;
        end loop;
        return '?';
    end function;

    function bits_to_string(v : std_logic_vector; on_c : character := '*'; off_c : character := '.') return string is
        variable s : string(1 to v'length + (v'length - 1) / 4);
        variable n : natural := 0;
        variable k : natural := v'length;        -- bits remaining, used to place spaces
    begin
        for i in v'range loop                    -- descending range: leftmost first
            n := n + 1;
            if v(i) = '1' then
                s(n) := on_c;
            elsif v(i) = '0' then
                s(n) := off_c;
            else
                s(n) := 'X';                     -- U, X, Z...: undriven/conflicting signal
            end if;
            k := k - 1;
            if k mod 4 = 0 and k /= 0 then
                n := n + 1;
                s(n) := ' ';
            end if;
        end loop;
        return s;
    end function;

    function display_to_string(digits : string(1 to 4); dots : std_logic_vector(3 downto 0)) return string is
        variable s : string(1 to 8);
        variable n : natural := 0;
    begin
        for pos in 1 to 4 loop
            n := n + 1;
            s(n) := digits(pos);
            if dots(4 - pos) = '1' then
                n := n + 1;
                s(n) := '.';
            end if;
        end loop;
        return s(1 to n);
    end function;

    procedure print_line(s : string) is
        variable l : line;
    begin
        write(l, s);
        writeline(output, l);
    end procedure;

    procedure print_board(sw : std_logic_vector(15 downto 0); led : std_logic_vector(15 downto 0)) is
    begin
        print_line("[board] sw " & bits_to_string(sw, '1', '0') & " | led " & bits_to_string(led));
    end procedure;
    procedure print_segments(segs : seg_vector; dots : std_logic_vector; indent : string := "  ") is
        alias sg : seg_vector(0 to segs'length - 1) is segs;           -- normalize to 0..n-1
        alias dt : std_logic_vector(0 to dots'length - 1) is dots;
        variable l1, l2, l3 : line;
        function lit(s : std_logic_vector(6 downto 0); i : natural; c : character) return character is
        begin
            if s(i) = '0' then return c; else return ' '; end if;   -- active low
        end function;
    begin
        write(l1, indent); write(l2, indent); write(l3, indent);
        for k in sg'range loop
            write(l1, ' ' & lit(sg(k), 0, '_') & "  ");
            write(l2, lit(sg(k), 5, '|') & lit(sg(k), 6, '_') & lit(sg(k), 1, '|') & ' ');
            write(l3, lit(sg(k), 4, '|') & lit(sg(k), 3, '_') & lit(sg(k), 2, '|'));
            if k <= dt'high and dt(k) = '1' then write(l3, '.'); else write(l3, ' '); end if;
        end loop;
        writeline(output, l1); writeline(output, l2); writeline(output, l3);
    end procedure;
end package body;

-------------------------------------------------------------------------------
-- Watches the multiplexed 7-segment display and remembers what each digit
-- shows, like your eyes do on the real board.
library ieee;
use ieee.std_logic_1164.all;
use work.basys3_sim_pkg.all;

entity basys3_display_monitor is
    port (
        clk    : in  std_logic;
        seg    : in  std_logic_vector(6 downto 0);
        dp     : in  std_logic;
        an     : in  std_logic_vector(3 downto 0);
        digits : out string(1 to 4);                 -- digits(1) = leftmost
        segs   : out seg_vector(0 to 3);             -- raw patterns, segs(0) = leftmost
        dots   : out std_logic_vector(3 downto 0);   -- indexed like an
        multi  : out boolean                         -- latched: >1 digit was on at once
    );
end entity;

architecture sim of basys3_display_monitor is
begin
    process (clk)
        variable active, idx : integer;
        variable d : string(1 to 4) := "    ";
        variable p : std_logic_vector(3 downto 0) := "0000";
        variable sv : seg_vector(0 to 3) := (others => "1111111");
        variable m : boolean := false;
    begin
        if rising_edge(clk) then
            active := 0;
            idx := 0;
            for i in 0 to 3 loop
                if an(i) = '0' then
                    active := active + 1;
                    idx := i;
                end if;
            end loop;
            if active = 1 then
                d(4 - idx) := seg_to_char(seg);
                sv(3 - idx) := seg;
                p(idx) := not dp;
            elsif active > 1 then
                m := true;
            end if;
            digits <= d;
            segs <= sv;
            dots <= p;
            multi <= m;
        end if;
    end process;
end architecture;
