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
