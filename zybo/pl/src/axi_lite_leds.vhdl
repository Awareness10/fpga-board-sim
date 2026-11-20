-- AXI4-Lite slave: the ARM (PS) drives the Zybo's 4 LEDs and reads its switches and buttons.
--
-- Register map (byte offsets from the base address Vivado assigns, usually 0x43C0_0000).
-- Keep in sync with zybo/ps/drivers/axi_leds.h.
--   0x0  LED    RW  bits 3:0 -> led(3:0)              reset 0
--   0x4  INPUT  RO  bits 3:0 = sw, bits 7:4 = btn     (synchronised, not debounced)
--   0x8  ID     RO  0x4C454453 ("LEDS"): lets software check the peripheral is there
--   0xC  -          unmapped: read and write answer SLVERR (the CPU sees a bus error)
-- Writes to RO registers are ignored and answer OKAY.
--
-- Port names follow Vivado's s_axi_* convention, so Vivado recognises the AXI
-- interface automatically when the file is added to a block design.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity axi_lite_leds is
    generic (
        C_ID : std_logic_vector(31 downto 0) := x"4C454453"
    );
    port (
        s_axi_aclk    : in  std_logic;
        s_axi_aresetn : in  std_logic;
        -- write address channel
        s_axi_awaddr  : in  std_logic_vector(3 downto 0);
        s_axi_awprot  : in  std_logic_vector(2 downto 0);
        s_axi_awvalid : in  std_logic;
        s_axi_awready : out std_logic;
        -- write data channel
        s_axi_wdata   : in  std_logic_vector(31 downto 0);
        s_axi_wstrb   : in  std_logic_vector(3 downto 0);
        s_axi_wvalid  : in  std_logic;
        s_axi_wready  : out std_logic;
        -- write response channel
        s_axi_bresp   : out std_logic_vector(1 downto 0);
        s_axi_bvalid  : out std_logic;
        s_axi_bready  : in  std_logic;
        -- read address channel
        s_axi_araddr  : in  std_logic_vector(3 downto 0);
        s_axi_arprot  : in  std_logic_vector(2 downto 0);
        s_axi_arvalid : in  std_logic;
        s_axi_arready : out std_logic;
        -- read data channel
        s_axi_rdata   : out std_logic_vector(31 downto 0);
        s_axi_rresp   : out std_logic_vector(1 downto 0);
        s_axi_rvalid  : out std_logic;
        s_axi_rready  : in  std_logic;
        -- board I/O
        led : out std_logic_vector(3 downto 0);
        sw  : in  std_logic_vector(3 downto 0);
        btn : in  std_logic_vector(3 downto 0)
    );
end entity;

architecture rtl of axi_lite_leds is
    constant RESP_OKAY   : std_logic_vector(1 downto 0) := "00";
    constant RESP_SLVERR : std_logic_vector(1 downto 0) := "10";

    signal awready, wready, bvalid, arready, rvalid : std_logic := '0';
    signal led_reg : std_logic_vector(3 downto 0) := (others => '0');
    -- Two flip-flops per input: switches and buttons are asynchronous to the clock.
    signal in_meta, in_sync : std_logic_vector(7 downto 0) := (others => '0');
begin
    s_axi_awready <= awready;
    s_axi_wready  <= wready;
    s_axi_bvalid  <= bvalid;
    s_axi_arready <= arready;
    s_axi_rvalid  <= rvalid;
    led <= led_reg;

    sync : process (s_axi_aclk)
    begin
        if rising_edge(s_axi_aclk) then
            in_meta <= btn & sw;
            in_sync <= in_meta;
        end if;
    end process;

    -- Write: wait until address AND data are both offered, accept them together
    -- (ready high for one cycle), then answer on B once both handshakes are done.
    write_ch : process (s_axi_aclk)
    begin
        if rising_edge(s_axi_aclk) then
            if s_axi_aresetn = '0' then
                awready <= '0';
                wready  <= '0';
                bvalid  <= '0';
                s_axi_bresp <= RESP_OKAY;
                led_reg <= (others => '0');
            else
                awready <= '0';
                wready  <= '0';
                if bvalid = '1' and s_axi_bready = '1' then
                    bvalid <= '0';
                end if;

                if awready = '1' then
                    -- AW and W handshakes complete on this edge (master holds valid until ready).
                    case s_axi_awaddr(3 downto 2) is
                        when "00" =>
                            if s_axi_wstrb(0) = '1' then
                                led_reg <= s_axi_wdata(3 downto 0);
                            end if;
                            s_axi_bresp <= RESP_OKAY;
                        when "01" | "10" => s_axi_bresp <= RESP_OKAY;  -- read-only: ignore
                        when others      => s_axi_bresp <= RESP_SLVERR;
                    end case;
                    bvalid <= '1';
                elsif s_axi_awvalid = '1' and s_axi_wvalid = '1' and bvalid = '0' then
                    awready <= '1';
                    wready  <= '1';
                end if;
            end if;
        end if;
    end process;

    -- Read: accept the address for one cycle, then hold the data on R until taken.
    read_ch : process (s_axi_aclk)
    begin
        if rising_edge(s_axi_aclk) then
            if s_axi_aresetn = '0' then
                arready <= '0';
                rvalid  <= '0';
                s_axi_rdata <= (others => '0');
                s_axi_rresp <= RESP_OKAY;
            else
                arready <= '0';
                if rvalid = '1' and s_axi_rready = '1' then
                    rvalid <= '0';
                end if;

                if arready = '1' then
                    s_axi_rdata <= (others => '0');
                    s_axi_rresp <= RESP_OKAY;
                    case s_axi_araddr(3 downto 2) is
                        when "00"   => s_axi_rdata(3 downto 0) <= led_reg;
                        when "01"   => s_axi_rdata(7 downto 0) <= in_sync;
                        when "10"   => s_axi_rdata <= C_ID;
                        when others => s_axi_rresp <= RESP_SLVERR;
                    end case;
                    rvalid <= '1';
                elsif s_axi_arvalid = '1' and rvalid = '0' then
                    arready <= '1';
                end if;
            end if;
        end if;
    end process;
end architecture;
