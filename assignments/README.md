# Your assignments

One folder per assignment. Start one with

```sh
uv run boardsim new zybo lab1           # Zybo: your own AXI peripheral (VHDL) + C
uv run boardsim new zybo lab1 --gpio    # Zybo: C only, on the tutorial's AXI GPIO
uv run boardsim new basys3 lab1         # Basys3: VHDL
```

and use its name with any command: `uv run boardsim zybo test lab1`,
`uv run boardsim basys3 run lab1`, ... The whole workflow is in [HOW-TO-USE.md](../HOW-TO-USE.md).
