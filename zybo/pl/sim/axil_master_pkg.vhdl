-- AXI4-Lite master for testbenches (a "BFM", bus functional model). It does in
-- simulation what the ARM does when C code runs `*(volatile uint32_t *)addr = data`:
-- one AXI-Lite transaction, cycle by cycle, while checking the slave follows the AXI rules.
--
--   signal m : axil_m2s := AXIL_M2S_IDLE;   -- master -> slave  (connect to s_axi_aw*/w*/ar*, bready, rready)
--   signal s : axil_s2m;                    -- slave  -> master (connect to s_axi_*ready, b*, r*)
--   axil_write(clk, m, s, 16#4#, x"0000000F", resp);
--   axil_check_read(clk, m, s, 16#0#, x"00000005");
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package axil_master_pkg is
    constant AXI_OKAY   : std_logic_vector(1 downto 0) := "00";
    constant AXI_SLVERR : std_logic_vector(1 downto 0) := "10";

    type axil_m2s is record
        awaddr  : std_logic_vector(31 downto 0);
        awvalid : std_logic;
        wdata   : std_logic_vector(31 downto 0);
        wstrb   : std_logic_vector(3 downto 0);
        wvalid  : std_logic;
        bready  : std_logic;
        araddr  : std_logic_vector(31 downto 0);
        arvalid : std_logic;
        rready  : std_logic;
    end record;

    type axil_s2m is record
        awready : std_logic;
        wready  : std_logic;
        bresp   : std_logic_vector(1 downto 0);
        bvalid  : std_logic;
        arready : std_logic;
        rdata   : std_logic_vector(31 downto 0);
        rresp   : std_logic_vector(1 downto 0);
        rvalid  : std_logic;
    end record;

    constant AXIL_M2S_IDLE : axil_m2s := (
        awaddr => (others => '0'), awvalid => '0', wdata => (others => '0'), wstrb => "0000",
        wvalid => '0', bready => '0', araddr => (others => '0'), arvalid => '0', rready => '0');

    -- One write. w_delay: cycles before W is offered (AW goes first);
    -- b_delay: cycles before the master is ready for the response (back-pressure).
    procedure axil_write(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                         addr : natural; data : std_logic_vector(31 downto 0);
                         resp : out std_logic_vector(1 downto 0);
                         strb : std_logic_vector(3 downto 0) := "1111";
                         w_delay, b_delay : natural := 0);

    -- One read. r_delay: cycles before the master is ready for the data.
    procedure axil_read(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                        addr : natural; data : out std_logic_vector(31 downto 0);
                        resp : out std_logic_vector(1 downto 0); r_delay : natural := 0);

    -- Write / read and report an error if the response (or data) is not what we expect.
    procedure axil_check_write(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                               addr : natural; data : std_logic_vector(31 downto 0);
                               expect_resp : std_logic_vector(1 downto 0) := "00";
                               strb : std_logic_vector(3 downto 0) := "1111";
                               w_delay, b_delay : natural := 0);
    procedure axil_check_read(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                              addr : natural; expect : std_logic_vector(31 downto 0);
                              expect_resp : std_logic_vector(1 downto 0) := "00";
                              r_delay : natural := 0);

    function hex_addr(addr : natural) return string;
end package;

package body axil_master_pkg is
    function hex_addr(addr : natural) return string is
    begin
        return "0x" & to_hstring(std_logic_vector(to_unsigned(addr, 12)));
    end function;

    procedure axil_write(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                         addr : natural; data : std_logic_vector(31 downto 0);
                         resp : out std_logic_vector(1 downto 0);
                         strb : std_logic_vector(3 downto 0) := "1111";
                         w_delay, b_delay : natural := 0) is
        variable aw_done, w_done, b_on : boolean := false;
        variable w_on : boolean := w_delay = 0;
        variable cycle : natural := 0;
    begin
        m.awaddr  <= std_logic_vector(to_unsigned(addr, 32));
        m.wdata   <= data;
        m.wstrb   <= strb;
        m.awvalid <= '1';
        if w_on then m.wvalid <= '1'; end if;
        loop
            wait until rising_edge(clk);
            -- Values read here are the ones just before this edge, like a flip-flop sees them.
            assert s.bvalid = '0' or (aw_done and w_done)
                report "AXI rule broken: BVALID before both AW and W handshakes" severity error;
            if b_on and s.bvalid = '1' then
                resp := s.bresp;
                m.bready <= '0';
                exit;
            end if;
            if not aw_done and s.awready = '1' then aw_done := true; m.awvalid <= '0'; end if;
            if w_on and not w_done and s.wready = '1' then w_done := true; m.wvalid <= '0'; end if;
            cycle := cycle + 1;
            if not w_on and cycle >= w_delay then w_on := true; m.wvalid <= '1'; end if;
            if aw_done and w_done and not b_on and cycle >= b_delay then b_on := true; m.bready <= '1'; end if;
            assert cycle < 100 report "write " & hex_addr(addr) & " timed out (no handshake)" severity failure;
        end loop;
    end procedure;

    procedure axil_read(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                        addr : natural; data : out std_logic_vector(31 downto 0);
                        resp : out std_logic_vector(1 downto 0); r_delay : natural := 0) is
        variable ar_done, r_on : boolean := false;
        variable cycle : natural := 0;
    begin
        m.araddr  <= std_logic_vector(to_unsigned(addr, 32));
        m.arvalid <= '1';
        loop
            wait until rising_edge(clk);
            assert s.rvalid = '0' or ar_done
                report "AXI rule broken: RVALID before the AR handshake" severity error;
            if r_on and s.rvalid = '1' then
                data := s.rdata;
                resp := s.rresp;
                m.rready <= '0';
                exit;
            end if;
            if not ar_done and s.arready = '1' then ar_done := true; m.arvalid <= '0'; end if;
            cycle := cycle + 1;
            if ar_done and not r_on and cycle >= r_delay then r_on := true; m.rready <= '1'; end if;
            assert cycle < 100 report "read " & hex_addr(addr) & " timed out (no handshake)" severity failure;
        end loop;
    end procedure;

    procedure axil_check_write(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                               addr : natural; data : std_logic_vector(31 downto 0);
                               expect_resp : std_logic_vector(1 downto 0) := "00";
                               strb : std_logic_vector(3 downto 0) := "1111";
                               w_delay, b_delay : natural := 0) is
        variable r : std_logic_vector(1 downto 0);
    begin
        axil_write(clk, m, s, addr, data, r, strb, w_delay, b_delay);
        assert r = expect_resp
            report "write " & hex_addr(addr) & ": resp " & to_string(r) & ", expected " &
                   to_string(expect_resp) severity error;
    end procedure;

    procedure axil_check_read(signal clk : in std_logic; signal m : inout axil_m2s; signal s : in axil_s2m;
                              addr : natural; expect : std_logic_vector(31 downto 0);
                              expect_resp : std_logic_vector(1 downto 0) := "00";
                              r_delay : natural := 0) is
        variable d : std_logic_vector(31 downto 0);
        variable r : std_logic_vector(1 downto 0);
    begin
        axil_read(clk, m, s, addr, d, r, r_delay);
        assert r = expect_resp
            report "read " & hex_addr(addr) & ": resp " & to_string(r) & ", expected " &
                   to_string(expect_resp) severity error;
        if expect_resp = AXI_OKAY then
            assert d = expect
                report "read " & hex_addr(addr) & ": got 0x" & to_hstring(d) & ", expected 0x" &
                       to_hstring(expect) severity error;
        end if;
    end procedure;
end package body;
