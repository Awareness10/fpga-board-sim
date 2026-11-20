# The program "{{name}}", built for the emulator by `boardsim zybo ...` (zybo/ps/CMakeLists.txt
# picks up every assignments/<name>/ps/CMakeLists.txt).
#
#   zybo_board_program(<name> <sources...> [KEYS <keys>] [EXPECT <regex>] [NO_TEST])
#
# Add new .c/.S files to the list. The test (`boardsim zybo test {{name}}`) runs the
# program in QEMU and passes if it exits with 0 and prints no "CHECK failed".
# A program that never returns needs KEYS "...q" (q quits) or NO_TEST.
zybo_board_program({{name}} main.c)
