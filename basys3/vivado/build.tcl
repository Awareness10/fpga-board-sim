# Build (and optionally program) a Basys3 bitstream in Vivado non-project mode.
# No .xpr project to keep in sync: the sources in the repo are the project.
#
#   vivado -mode batch -nojournal -nolog -source basys3/vivado/build.tcl \
#          -tclargs <design dir> <top entity> [program]
#   (or: uv run boardsim basys3 bit / boardsim basys3 program)
#
#   <design dir>  folder with src/ and constraints/, e.g. basys3 or your own project
#   <top entity>  e.g. basys3_top; constraints/<top>.xdc must exist
#   program       also load the bitstream onto a connected Basys3 (JTAG over USB)
#
# Sources: every src/*.vhd as VHDL-2008.
# Output: <design dir>/build/vivado/<top>/ with <top>.bit, utilization.rpt and timing.rpt.

if {[llength $argv] < 2} {
    puts "usage: vivado -mode batch -source build.tcl -tclargs <design dir> <top entity> \[program\]"
    exit 1
}
set dir  [file normalize [lindex $argv 0]]
set top  [lindex $argv 1]
set prog [expr {[lindex $argv 2] eq "program"}]
set part xc7a35tcpg236-1
set out  [file join $dir build vivado $top]
set xdc  [file join $dir constraints $top.xdc]
file mkdir $out

set srcs {}
foreach f [lsort [glob -directory [file join $dir src] *.vhd]] {
    lappend srcs $f
}
if {![file exists $xdc]} { puts "ERROR: missing $xdc"; exit 1 }
set names {}
foreach f $srcs { lappend names [file tail $f] }   ;# Vivado's Tcl 8.5 has no lmap
puts "Sources: [join $names {, }]"

read_vhdl -vhdl2008 $srcs
read_xdc $xdc

synth_design -top $top -part $part
report_utilization -file [file join $out utilization.rpt]
opt_design
place_design
route_design
report_timing_summary -file [file join $out timing.rpt]
report_drc -file [file join $out drc.rpt]

set bit [file join $out $top.bit]
write_bitstream -force $bit
puts "Bitstream: $bit"

if {$prog} {
    open_hw_manager
    connect_hw_server
    open_hw_target
    set dev [lindex [get_hw_devices xc7a35t*] 0]
    current_hw_device $dev
    set_property PROGRAM.FILE $bit $dev
    program_hw_devices $dev
    close_hw_manager
    puts "Programmed $dev"
}
