-- AXI GPIO: a stand-in for Xilinx's "AXI GPIO" IP (PG144), the block the Peronnin tutorial
-- adds in Vivado. Same register map, generics and port names, so Xilinx's XGpio driver
-- (and zybo/ps/xil/xgpio.c) works with it unchanged. Interrupts are not implemented.
--
-- Register map (byte offsets; Vivado puts axi_gpio_0 at 0x4120_0000):
--   0x000  GPIO_DATA   channel 1 data. Write: output value. Read: input pins for bits that
--                      are inputs, the output value for bits that are outputs.
--   0x004  GPIO_TRI    channel 1 direction, one bit per pin: 1 = input, 0 = output
--   0x008  GPIO2_DATA  channel 2, same as above   (only if C_IS_DUAL = 1)
--   0x00C  GPIO2_TRI
--   others             read 0, writes ignored, response OKAY (like the Xilinx IP)
--
-- gpio_io_t is the tri-state control for each pin (1 = pin is an input, output driver off).
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity axi_gpio is
    generic (
        C_GPIO_WIDTH     : integer range 1 to 32 := 32;
        C_GPIO2_WIDTH    : integer range 1 to 32 := 32;
        C_IS_DUAL        : integer range 0 to 1  := 0;
        -- Set by Vivado when you pick a board interface like leds_4bits (all outputs) or
        -- btns_4bits (all inputs): reads of DATA then return the register / the pins only.
        C_ALL_INPUTS     : integer range 0 to 1  := 0;
        C_ALL_OUTPUTS    : integer range 0 to 1  := 0;
        C_ALL_INPUTS_2   : integer range 0 to 1  := 0;
        C_ALL_OUTPUTS_2  : integer range 0 to 1  := 0;
        C_DOUT_DEFAULT   : std_logic_vector(31 downto 0) := x"00000000";
        C_TRI_DEFAULT    : std_logic_vector(31 downto 0) := x"FFFFFFFF";   -- all inputs after reset
        C_DOUT_DEFAULT_2 : std_logic_vector(31 downto 0) := x"00000000";
        C_TRI_DEFAULT_2  : std_logic_vector(31 downto 0) := x"FFFFFFFF"
    );
    port (
        s_axi_aclk    : in  std_logic;
        s_axi_aresetn : in  std_logic;
        s_axi_awaddr  : in  std_logic_vector(8 downto 0);
        s_axi_awvalid : in  std_logic;
        s_axi_awready : out std_logic;
        s_axi_wdata   : in  std_logic_vector(31 downto 0);
        s_axi_wstrb   : in  std_logic_vector(3 downto 0);
        s_axi_wvalid  : in  std_logic;
        s_axi_wready  : out std_logic;
        s_axi_bresp   : out std_logic_vector(1 downto 0);
        s_axi_bvalid  : out std_logic;
        s_axi_bready  : in  std_logic;
        s_axi_araddr  : in  std_logic_vector(8 downto 0);
        s_axi_arvalid : in  std_logic;
        s_axi_arready : out std_logic;
        s_axi_rdata   : out std_logic_vector(31 downto 0);
        s_axi_rresp   : out std_logic_vector(1 downto 0);
        s_axi_rvalid  : out std_logic;
        s_axi_rready  : in  std_logic;
        -- channel 1
        gpio_io_i  : in  std_logic_vector(C_GPIO_WIDTH - 1 downto 0);
        gpio_io_o  : out std_logic_vector(C_GPIO_WIDTH - 1 downto 0);
        gpio_io_t  : out std_logic_vector(C_GPIO_WIDTH - 1 downto 0);
        -- channel 2
        gpio2_io_i : in  std_logic_vector(C_GPIO2_WIDTH - 1 downto 0) := (others => '0');
        gpio2_io_o : out std_logic_vector(C_GPIO2_WIDTH - 1 downto 0);
        gpio2_io_t : out std_logic_vector(C_GPIO2_WIDTH - 1 downto 0)
    );
end entity;

architecture rtl of axi_gpio is
    subtype word is std_logic_vector(31 downto 0);

    -- Keep only the bytes whose strobe bit is set.
    function apply_strb(old, wdata : word; strb : std_logic_vector(3 downto 0)) return word is
        variable r : word := old;
    begin
        for b in 0 to 3 loop
            if strb(b) = '1' then
                r(8 * b + 7 downto 8 * b) := wdata(8 * b + 7 downto 8 * b);
            end if;
        end loop;
        return r;
    end function;

    -- What a read of a DATA register returns: pin for inputs, register for outputs.
    function data_read(dout, tri, pins : word; width, all_in, all_out : natural) return word is
        variable r : word := (others => '0');
    begin
        for i in 0 to width - 1 loop
            if all_out = 1 then
                r(i) := dout(i);
            elsif all_in = 1 or tri(i) = '1' then
                r(i) := pins(i);
            else
                r(i) := dout(i);
            end if;
        end loop;
        return r;
    end function;

    function mask(v : word; width : natural) return word is
        variable r : word := (others => '0');
    begin
        r(width - 1 downto 0) := v(width - 1 downto 0);
        return r;
    end function;

    signal awready, wready, bvalid, arready, rvalid : std_logic := '0';
    signal dout1, tri1, dout2, tri2 : word;
    -- Pins synchronised to the clock with two flip-flops (buttons are asynchronous).
    signal pins1_meta, pins1, pins2_meta, pins2 : word := (others => '0');
begin
    s_axi_awready <= awready;
    s_axi_wready  <= wready;
    s_axi_bvalid  <= bvalid;
    s_axi_arready <= arready;
    s_axi_rvalid  <= rvalid;
    s_axi_bresp   <= "00";  -- always OKAY

    gpio_io_o  <= dout1(C_GPIO_WIDTH - 1 downto 0);
    gpio_io_t  <= tri1(C_GPIO_WIDTH - 1 downto 0);
    gpio2_io_o <= dout2(C_GPIO2_WIDTH - 1 downto 0);
    gpio2_io_t <= tri2(C_GPIO2_WIDTH - 1 downto 0);

    sync : process (s_axi_aclk)
    begin
        if rising_edge(s_axi_aclk) then
            pins1_meta <= (others => '0');
            pins1_meta(C_GPIO_WIDTH - 1 downto 0) <= gpio_io_i;
            pins2_meta <= (others => '0');
            pins2_meta(C_GPIO2_WIDTH - 1 downto 0) <= gpio2_io_i;
            pins1 <= pins1_meta;
            pins2 <= pins2_meta;
        end if;
    end process;

    -- Write: same handshake as axi_lite_leds (accept AW + W together, then answer on B).
    write_ch : process (s_axi_aclk)
    begin
        if rising_edge(s_axi_aclk) then
            if s_axi_aresetn = '0' then
                awready <= '0';
                wready  <= '0';
                bvalid  <= '0';
                dout1 <= mask(C_DOUT_DEFAULT, C_GPIO_WIDTH);
                tri1  <= mask(C_TRI_DEFAULT, C_GPIO_WIDTH);
                dout2 <= mask(C_DOUT_DEFAULT_2, C_GPIO2_WIDTH);
                tri2  <= mask(C_TRI_DEFAULT_2, C_GPIO2_WIDTH);
            else
                awready <= '0';
                wready  <= '0';
                if bvalid = '1' and s_axi_bready = '1' then
                    bvalid <= '0';
                end if;

                if awready = '1' then
                    case to_integer(unsigned(s_axi_awaddr(8 downto 2))) is
                        when 0 => dout1 <= mask(apply_strb(dout1, s_axi_wdata, s_axi_wstrb), C_GPIO_WIDTH);
                        when 1 => tri1  <= mask(apply_strb(tri1, s_axi_wdata, s_axi_wstrb), C_GPIO_WIDTH);
                        when 2 =>
                            if C_IS_DUAL = 1 then
                                dout2 <= mask(apply_strb(dout2, s_axi_wdata, s_axi_wstrb), C_GPIO2_WIDTH);
                            end if;
                        when 3 =>
                            if C_IS_DUAL = 1 then
                                tri2 <= mask(apply_strb(tri2, s_axi_wdata, s_axi_wstrb), C_GPIO2_WIDTH);
                            end if;
                        when others => null;
                    end case;
                    bvalid <= '1';
                elsif s_axi_awvalid = '1' and s_axi_wvalid = '1' and bvalid = '0' then
                    awready <= '1';
                    wready  <= '1';
                end if;
            end if;
        end if;
    end process;

    read_ch : process (s_axi_aclk)
    begin
        if rising_edge(s_axi_aclk) then
            if s_axi_aresetn = '0' then
                arready <= '0';
                rvalid  <= '0';
                s_axi_rdata <= (others => '0');
                s_axi_rresp <= "00";
            else
                arready <= '0';
                if rvalid = '1' and s_axi_rready = '1' then
                    rvalid <= '0';
                end if;

                if arready = '1' then
                    s_axi_rdata <= (others => '0');
                    s_axi_rresp <= "00";
                    case to_integer(unsigned(s_axi_araddr(8 downto 2))) is
                        when 0 => s_axi_rdata <= data_read(dout1, tri1, pins1, C_GPIO_WIDTH, C_ALL_INPUTS, C_ALL_OUTPUTS);
                        when 1 => s_axi_rdata <= tri1;
                        when 2 =>
                            if C_IS_DUAL = 1 then
                                s_axi_rdata <= data_read(dout2, tri2, pins2, C_GPIO2_WIDTH, C_ALL_INPUTS_2, C_ALL_OUTPUTS_2);
                            end if;
                        when 3 =>
                            if C_IS_DUAL = 1 then
                                s_axi_rdata <= tri2;
                            end if;
                        when others => null;
                    end case;
                    rvalid <= '1';
                elsif s_axi_arvalid = '1' and rvalid = '0' then
                    arready <= '1';
                end if;
            end if;
        end if;
    end process;
end architecture;
