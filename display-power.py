#!/usr/bin/env python3
"""Per-output locked power control; restore original DDC brightness on activity."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import fcntl


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=20)


def buses():
    result = {}
    for block in re.split(r"\n(?=Display |Invalid display)", run("ddcutil", "detect", "--brief")):
        if not block.startswith("Display "):
            continue
        bus = re.search(r"/dev/i2c-(\d+)", block)
        connector = re.search(r"DRM connector:\s+\S+-(DP-\d+|HDMI-A-\d+)", block)
        if bus and connector:
            result[connector[1]] = bus[1]
    return result


def apply(phase, main, sides, state):
    if phase == "off":
        run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "disable", monitor = ' + json.dumps(main) + ' })')
        return
    saved = json.loads(state.read_text()) if state.exists() else {}
    if phase == "wake":
        run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "enable" })')
    if phase == "dim" or saved:
        available = buses()
        for monitor in sides if phase == "dim" else list(saved):
            bus = available.get(monitor)
            if not bus:
                continue
            try:
                if phase == "dim":
                    if monitor not in saved:
                        value = run("ddcutil", "--bus", bus, "getvcp", "10", "--terse")
                        match = re.search(r"VCP 10 C (\d+) (\d+)", value)
                        if not match:
                            continue
                        saved[monitor] = int(match[1])
                        # Persist before dimming so recovery survives a shell restart.
                        state.write_text(json.dumps(saved))
                    run("ddcutil", "--bus", bus, "setvcp", "10", "0")
                else:
                    run("ddcutil", "--bus", bus, "setvcp", "10", str(saved[monitor]))
                    del saved[monitor]
                    state.write_text(json.dumps(saved))
            except (subprocess.SubprocessError, OSError) as error:
                print(f"{monitor}: {error}", file=sys.stderr)
    if not saved and state.exists():
        state.unlink()


if __name__ == "__main__":
    phase, main, *sides = sys.argv[1:]
    if phase not in ("off", "dim", "wake"):
        raise SystemExit("Expected off, dim or wake")
    directory = Path(os.environ["XDG_RUNTIME_DIR"]) / "lock-explorer-power"
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / "mutex").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        apply(phase, main, sides, directory / "brightness.json")
