# The program "{{name}}", built for the emulator by `boardsim zybo ...` (zybo/ps/CMakeLists.txt
# picks up every assignments/<name>/ps/CMakeLists.txt).
#
#   zybo_board_program(<name> <sources...> [KEYS <keys>] [EXPECT <regex>] [NO_TEST])
#
# The test (`boardsim zybo test {{name}}`) types KEYS into the board (1-4 toggle BTN0-3,
# 5-8 toggle SW0-3, . waits, q quits) and passes if the board lines match EXPECT and the
# program exits with 0. Here: press BTN0, expect LD0 on. Change both when you change
# what the program does, or use NO_TEST instead.
zybo_board_program({{name}} main.c
    KEYS "1.q"
    EXPECT "LD3..LD0 \\.\\.\\.\\*")
