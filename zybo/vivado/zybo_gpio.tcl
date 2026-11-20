# The Peronnin tutorial's Vivado part (block design -> bitstream -> .xsa), as a script.
# It does what the GUI steps do:
#   ZYNQ7 PS (board preset) --M_AXI_GP0--> axi_gpio_0
#       GPIO  (channel 1) = leds_4bits
#       GPIO2 (channel 2) = btns_4bits
# The board interfaces carry the pin constraints, so no .xdc is needed.
#
# Boards: zybo (the original Zybo, XC7Z010, 512 MB DDR3: the course's board, default).
#         z7-10, z7-20 (Zybo Z7): outside the course, kept because they cost two lines.
#
# Easiest: `uv run boardsim zybo xsa [--bd-only]`. Directly:
#   vivado -mode batch -source zybo/vivado/zybo_gpio.tcl -tclargs <out dir> [zybo|z7-10|z7-20] [bd]
#     "bd": stop after the block design (quick check, no synthesis)
# Output: <out dir>/<name>/      (project; open the .xpr in the GUI to look around)
#         <out dir>/<name>.xsa   (for Vitis, bitstream included)
#   name = zybo for the original Zybo, zybo_z7-10 / zybo_z7-20 for the Zybo Z7.

if {[llength $argv] < 1} { error "usage: -tclargs <out dir> \[zybo|z7-10|z7-20\] \[bd\]" }
set out   [file normalize [lindex $argv 0]]
set board [expr {[llength $argv] > 1 ? [lindex $argv 1] : "zybo"}]
set stop  [expr {[llength $argv] > 2 ? [lindex $argv 2] : "all"}]
set gpio2 btns_4bits

# The Zybo Z7 board files ship with Vivado 2023.2; the original Zybo's don't, so a copy of
# Digilent's (github.com/Digilent/vivado-boards, MIT) is kept in board_files/ next to this script.
set_param board.repoPaths [list [file normalize [file join [file dirname [info script]] board_files]]]

switch $board {
    zybo  { set part xc7z010clg400-1; set bpname zybo;      set name zybo }
    z7-10 { set part xc7z010clg400-1; set bpname zybo-z7-10; set name zybo_z7-10 }
    z7-20 { set part xc7z020clg400-1; set bpname zybo-z7-20; set name zybo_z7-20 }
    default { error "board must be zybo, z7-10 or z7-20, got '$board'" }
}

set outdir $out/$name

# --- 1. Project for the Zybo board ---
create_project $name $outdir -part $part -force
# VHDL like the rest of the repo (Vivado's default is Verilog): the block design's top and
# the HDL wrapper come out as .vhd. Xilinx IP keeps its own sources (the PS7 is Verilog-only).
set_property target_language VHDL [current_project]
set bp [lindex [lsort [get_board_parts "digilentinc.com:${bpname}:*"]] end]
if {$bp eq ""} { error "No Digilent board files for $bpname. Install them from github.com/Digilent/vivado-boards" }
set_property board_part $bp [current_project]
puts "INFO: board part $bp"

# --- 2. Block design: Zynq PS + block automation (DDR, FIXED_IO, UART1, FCLK_CLK0 from the preset) ---
create_bd_design design_1
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7 processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} \
    [get_bd_cells processing_system7_0]

# --- 3. AXI GPIO on the board interfaces (GUI: Board tab, or "Run Connection Automation") ---
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio axi_gpio_0
set_property -dict [list CONFIG.GPIO_BOARD_INTERFACE leds_4bits \
                         CONFIG.GPIO2_BOARD_INTERFACE $gpio2] [get_bd_cells axi_gpio_0]
apply_bd_automation -rule xilinx.com:bd_rule:board -config [list Board_Interface leds_4bits] \
    [get_bd_intf_pins axi_gpio_0/GPIO]
apply_bd_automation -rule xilinx.com:bd_rule:board -config [list Board_Interface $gpio2] \
    [get_bd_intf_pins axi_gpio_0/GPIO2]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config {Master "/processing_system7_0/M_AXI_GP0" Clk_master "Auto" Clk_slave "Auto" Clk_xbar "Auto" intc_ip "New AXI Interconnect" master_apm "0"} \
    [get_bd_intf_pins axi_gpio_0/S_AXI]

validate_bd_design
save_bd_design

# --- What the emulation assumes: check it here instead of by eye ---
set seg [get_bd_addr_segs -of_objects [get_bd_addr_spaces processing_system7_0/Data] -filter {NAME =~ *axi_gpio_0*}]
set base [format 0x%08X [get_property OFFSET $seg]]
set range [format 0x%X [get_property RANGE $seg]]
set cfg [get_bd_cells axi_gpio_0]
puts "CHECK: axi_gpio_0 base $base range $range (zybo/ps/xil/xparameters.h expects 0x41200000)"
foreach p {C_GPIO_WIDTH C_ALL_OUTPUTS C_IS_DUAL C_GPIO2_WIDTH C_ALL_INPUTS_2 C_INTERRUPT_PRESENT GPIO_BOARD_INTERFACE GPIO2_BOARD_INTERFACE} {
    puts "CHECK: $p = [get_property CONFIG.$p $cfg]"
}
puts "CHECK: FCLK_CLK0 = [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ [get_bd_cells processing_system7_0]] MHz"
puts "CHECK: UART1 = [get_property CONFIG.PCW_UART1_PERIPHERAL_ENABLE [get_bd_cells processing_system7_0]]"
if {$base ne "0x41200000"} { puts "WARNING: address differs from the emulation; update zybo/ps/xil/xparameters.h" }

if {$stop eq "bd"} { puts "INFO: stopping after the block design"; return }

# --- 4. HDL wrapper, bitstream, .xsa (GUI: Create HDL Wrapper, Generate Bitstream, Export Hardware) ---
set wrapper [make_wrapper -files [get_files design_1.bd] -top]
add_files -norecurse $wrapper
set_property top design_1_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs [expr {max(1, [get_param general.maxThreads])}]
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "implementation failed, see $outdir/$name.runs/impl_1/runme.log" }

open_run impl_1
report_utilization -file $outdir/utilization.rpt
report_timing_summary -file $outdir/timing.rpt
puts "CHECK: WNS = [get_property SLACK [get_timing_paths -max_paths 1 -setup]] ns"

write_hw_platform -fixed -include_bit -force -file $out/$name.xsa
puts "INFO: wrote $out/$name.xsa"
