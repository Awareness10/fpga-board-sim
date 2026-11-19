# Load one of the apps onto the real Zybo over JTAG (what Vitis "Run" does), no IDE needed.
# Board: JP5 jumper on JTAG (or any boot mode), USB cable in PROG/UART (J12), power on.
#
# Easiest: `uv run boardsim zybo jtag <app>`, after `boardsim zybo vitis`. Directly:
#   xsdb zybo/vitis/run_jtag.tcl <workspace dir> <app>
# Serial output: 115200 8N1 on the board's second USB serial port
#   (Linux /dev/ttyUSB1, Windows a COMx port, macOS /dev/tty.usbserial-*)
#
# Steps: program the PL with the bitstream, init the PS (clocks, DDR, MIO) with ps7_init,
# enable the PS-PL level shifters (ps7_post_config), download the .elf, run.

if {[llength $argv] < 1} { error "usage: xsdb run_jtag.tcl <workspace dir> \[app\]" }
set ws   [file normalize [lindex $argv 0]]
set app  [expr {[llength $argv] > 1 ? [lindex $argv 1] : "xgpio_blink"}]
set plat zybo_platform
set hw   $ws/$plat/export/$plat/hw/sdt
set elf  $ws/$app/build/$app.elf
set bit  [lindex [glob -nocomplain $hw/*.bit] 0]
foreach f [list $elf $bit $hw/ps7_init.tcl] {
    if {$f eq "" || ![file exists $f]} { error "missing '$f': run `boardsim zybo vitis` first" }
}
puts "INFO: $app on $plat\n  bit $bit\n  elf $elf"

connect
if {[llength [targets -target-properties]] == 0} {
    error "no board found over JTAG: check the USB cable (PROG/UART port), the power switch, and\
           on Linux the Digilent cable drivers (see the README)"
}
puts [targets]

# Reset the whole system so a previous run doesn't leave the PS half-configured
targets -set -nocase -filter {name =~ "APU*"}
rst -system
after 1000

targets -set -nocase -filter {name =~ "xc7z0*"}
fpga -file $bit

targets -set -nocase -filter {name =~ "APU*"}
source $hw/ps7_init.tcl
ps7_init
ps7_post_config

targets -set -nocase -filter {name =~ "*A9*#0"}
dow $elf
con
puts "INFO: running $app (xsdb exits; the program keeps running)"
disconnect
