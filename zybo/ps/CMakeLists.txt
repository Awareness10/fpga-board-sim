cmake_minimum_required(VERSION 3.27)
project(zybo_ps LANGUAGES C ASM)

# Bare-metal programs for the Zynq-7000 PS (Cortex-A9), run under QEMU's xilinx-zynq-a9
# machine. CPU flags and the compiler come from the Conan profile (cortexa9-baremetal-gcc).

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)               # GNU C: statement expressions, inline asm
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)    # for clangd / editor completion

set(LINKER_SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/bsp/link.ld)

add_compile_options(
    -ffreestanding -fno-builtin -fno-common
    -ffunction-sections -fdata-sections
    # The MMU is off, so all memory is "strongly ordered": unaligned loads/stores fault.
    -mno-unaligned-access
    -Wall -Wextra
    $<$<CONFIG:Debug>:-Og> $<$<CONFIG:Debug>:-g3>
)
add_link_options(
    -nostdlib -static
    -T${LINKER_SCRIPT}
    -Wl,--gc-sections
    -Wl,-Map=$<TARGET_FILE:$<TARGET_PROPERTY:NAME>>.map
    -Wl,--no-warn-rwx-segments           # code and data share DDR on purpose
)

# --- Board support package (startup code, UART, exit, mini libc) + drivers ---
add_library(bsp STATIC bsp/crt0.S bsp/bsp.c)
target_include_directories(bsp PUBLIC bsp drivers)
# Stop GCC from turning the memset/memcpy loops into calls to... memset/memcpy.
target_compile_options(bsp PRIVATE -fno-tree-loop-distribute-patterns)
target_link_libraries(bsp PUBLIC gcc)    # libgcc: the A9 has no divide instruction (__aeabi_uidiv)

find_program(ARM_OBJDUMP NAMES ${CMAKE_OBJDUMP} arm-none-eabi-objdump)

# Programs run in QEMU through src/boardsim/qemu.py (standard library only), so the
# tests work the same on Windows, macOS and Linux.
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(QEMU_RUN ${CMAKE_CURRENT_SOURCE_DIR}/../../src/boardsim/qemu.py)

enable_testing()

# zynq_program(<name> <sources...> [NO_TEST])
#   builds <name>.elf, writes <name>.lst (C mixed with disassembly) and registers a ctest
#   that runs it under QEMU, plus a "run-<name>" target for interactive use.
function(zynq_program name)
    cmake_parse_arguments(ARG "NO_TEST" "" "" ${ARGN})
    add_executable(${name} ${ARG_UNPARSED_ARGUMENTS})
    set_target_properties(${name} PROPERTIES SUFFIX ".elf")
    target_link_libraries(${name} PRIVATE bsp)
    set_property(TARGET ${name} APPEND PROPERTY LINK_DEPENDS ${LINKER_SCRIPT})

    if(ARM_OBJDUMP)
        add_custom_command(TARGET ${name} POST_BUILD
            COMMAND ${ARM_OBJDUMP} -d -S --no-show-raw-insn $<TARGET_FILE:${name}>
                    > $<TARGET_FILE_DIR:${name}>/${name}.lst
            VERBATIM)
    endif()

    if(NOT ARG_NO_TEST)
        add_test(NAME ${name} COMMAND ${Python3_EXECUTABLE} ${QEMU_RUN} $<TARGET_FILE:${name}> --timeout 10)
    endif()
    add_custom_target(run-${name}
        COMMAND ${Python3_EXECUTABLE} ${QEMU_RUN} $<TARGET_FILE:${name}> --interactive
        DEPENDS ${name} USES_TERMINAL VERBATIM)
endfunction()

zynq_program(hello    examples/hello/main.c)
zynq_program(asm_sum  examples/asm_sum/main.c examples/asm_sum/sum.S)
zynq_program(axi_leds examples/axi_leds/main.c)
# Add your own: zynq_program(myprog examples/myprog/main.c)

# --- Peronnin tutorial: Xilinx's xgpio_example.c on a model of the Zybo ---
# xil/   = stand-ins for the Vitis BSP headers (xgpio.h, xparameters.h, xil_io.h, ...)
# model/ = the PL design (AXI GPIO -> LEDs / buttons) in C, since QEMU has no FPGA
add_library(zybo_model STATIC xil/xgpio.c model/zybo_board.c)
target_include_directories(zybo_model PUBLIC xil)
# SDT: Vitis 2023.2's unified IDE builds with the system-device-tree driver API.
target_compile_definitions(zybo_model PUBLIC ZYBO_BOARD_MODEL=1 SDT)
target_link_libraries(zybo_model PUBLIC bsp)

# zybo_board_program(<name> <source> KEYS <keys> EXPECT <regex>)
#   Like zynq_program, but linked with the board model. The ctest types KEYS into the UART
#   (1-4 toggle BTN0-3, 5-8 SW0-3, . waits, q quits) and passes if the output matches
#   EXPECT (the [zybo] board lines) and the program exits with 0.
function(zybo_board_program name source)
    cmake_parse_arguments(ARG "" "KEYS;EXPECT" "" ${ARGN})
    zynq_program(${name} ${source} NO_TEST)
    target_link_libraries(${name} PRIVATE zybo_model)
    add_test(NAME ${name}
        COMMAND ${Python3_EXECUTABLE} ${QEMU_RUN} $<TARGET_FILE:${name}>
                --keys "${ARG_KEYS}" --expect "${ARG_EXPECT}" --timeout 20)
endfunction()

# Steps 14-17: the example as imported. Expect LD0 on, off, on.
zybo_board_program(xgpio_blink examples/xgpio_blink/xgpio_example.c
    KEYS "..q"
    EXPECT "LD3..LD0 \\.\\.\\.\\*.*LD3..LD0 \\.\\.\\.\\..*LD3..LD0 \\.\\.\\.\\*.*quit")
# Step 18: buttons copied to the LEDs. Press BTN0, BTN1, BTN3, release BTN0; then flip SW0,
# which isn't wired to the GPIO, so the LEDs stay as they are.
zybo_board_program(xgpio_btns examples/xgpio_btns/xgpio_example.c
    KEYS "1.2.4.1.5.q"
    EXPECT "LD3..LD0 \\.\\.\\.\\*.*LD3..LD0 \\.\\.\\*\\*.*LD3..LD0 \\*\\.\\*\\*.*LD3..LD0 \\*\\.\\*\\.   BTN3..BTN0 #\\.#\\.   SW3..SW0 \\.\\.\\.\\..*LD3..LD0 \\*\\.\\*\\.   BTN3..BTN0 #\\.#\\.   SW3..SW0 \\.\\.\\.#.*quit")
