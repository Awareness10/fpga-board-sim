#!/usr/bin/env python3
# The Peronnin tutorial's Vitis part (Unified IDE 2023.2), as a script:
#   platform component from the .xsa (standalone, ps7_cortexa9_0)  ->  app components
#   with the same source files the emulation runs.
#
# Easiest: `uv run boardsim zybo vitis [assignment]`, after `boardsim zybo xsa`. Directly:
#   vitis -s zybo/vitis/build_apps.py <xsa> <workspace dir> [app | app=<source dir> ...]
#   app            one of zybo/ps/examples/ (default: xgpio_blink xgpio_btns)
#   app=<dir>      every .c/.h/.S file in <dir>, e.g. lab1=assignments/lab1/ps
# Output: <workspace dir>/  (open this folder as the workspace in the Vitis IDE)
#         <workspace dir>/<app>/build/<app>.elf
import os
import shutil
import sys

import vitis

here = os.path.dirname(os.path.abspath(__file__))
examples = os.path.join(os.path.dirname(here), "ps", "examples")
if len(sys.argv) < 3:
    raise SystemExit("usage: vitis -s build_apps.py <xsa> <workspace dir> [app ...]")
xsa, ws = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
apps = sys.argv[3:] or ["xgpio_blink", "xgpio_btns"]
plat_name = "zybo_platform"   # a unique name: get_platform() also searches the built-in platforms
if not os.path.isfile(xsa):
    raise SystemExit(f"missing {xsa}: run `boardsim zybo xsa` first")

if os.path.isdir(ws):
    shutil.rmtree(ws)
os.makedirs(ws)

client = vitis.create_client()
client.set_workspace(ws)
results = []
try:
    platform = client.create_platform_component(
        name=plat_name, hw=xsa, os="standalone", cpu="ps7_cortexa9_0")
    platform.build()
    xpfm = client.get_platform(plat_name)

    for spec in apps:
        app, _, src = spec.partition("=")
        src = os.path.abspath(src) if src else os.path.join(examples, app)
        files = sorted(f for f in os.listdir(src) if os.path.splitext(f)[1] in (".c", ".h", ".S", ".s"))
        if not files:
            raise SystemExit(f"no .c/.h/.S files in {src}")
        comp = client.create_app_component(
            name=app, platform=xpfm, domain="standalone_ps7_cortexa9_0",
            template="empty_application")
        comp.import_files(from_loc=src, files=files, dest_dir_in_cmp="src")
        comp.build()
        elf = os.path.join(ws, app, "build", app + ".elf")
        results.append((app, os.path.isfile(elf)))
finally:
    for app, ok in results:
        print(f"RESULT: {app:12s} {'OK' if ok else 'NO ELF'}")
    vitis.dispose()

if not results or not all(ok for _, ok in results):
    sys.exit(1)
