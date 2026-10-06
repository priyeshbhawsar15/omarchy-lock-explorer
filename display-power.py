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
    fallback = {}
    for block in re.split(r"\n(?=Display |Invalid display)", run("ddcutil", "detect", "--brief")):
        bus = re.search(r"/dev/i2c-(\d+)", block)
        connector = re.search(r"DRM connector:\s+\S+-(DP-\d+|HDMI-A-\d+)", block)
        if not bus or not connector:
            continue
        if block.startswith("Display "):
            result.setdefault(connector[1], bus[1])
        elif block.startswith("Invalid display"):
            fallback.setdefault(connector[1], []).append(bus[1])
    # NVIDIA can expose duplicate buses and mark working DDC buses invalid
    # when detect's generic capability probe fails. VCP 10 is what we need.
    for monitor, candidates in fallback.items():
        if monitor in result:
            continue
        for bus in candidates:
            try:
                brightness(bus)
                result[monitor] = bus
                break
            except (subprocess.SubprocessError, OSError, ValueError):
                continue
    return result


def brightness(bus):
    value = run("ddcutil", "--bus", bus, "getvcp", "10", "--terse")
    match = re.search(r"VCP 10 C (\d+) (\d+)", value)
    if not match:
        raise ValueError(f"Unrecognized brightness response on bus {bus}: {value!r}")
    return int(match[1])


def set_brightness(bus, value):
    run("ddcutil", "--bus", bus, "setvcp", "10", str(value))
    actual = brightness(bus)
    if actual != value:
        raise ValueError(f"Brightness readback is {actual}, expected {value} on bus {bus}")


def apply(phase, main, sides, state):
    if phase == "off":
        run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "disable", monitor = ' + json.dumps(main) + ' })')
        return
    saved = json.loads(state.read_text()) if state.exists() else {}
    if phase == "wake":
        run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "enable" })')
    errors = []
    if phase == "dim" or saved:
        available = buses()
        for monitor in sides if phase == "dim" else list(saved):
            bus = available.get(monitor)
            if not bus:
                errors.append(f"{monitor}: no accessible DDC bus")
                continue
            try:
                if phase == "dim":
                    if monitor not in saved:
                        saved[monitor] = brightness(bus)
                        # Persist before dimming so recovery survives a shell restart.
                        state.write_text(json.dumps(saved))
                    set_brightness(bus, 0)
                else:
                    set_brightness(bus, saved[monitor])
                    del saved[monitor]
                    state.write_text(json.dumps(saved))
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                # One monitor failing must not prevent the other from dimming.
                errors.append(f"{monitor}: {error}")
    if not saved and state.exists():
        state.unlink()
    if errors:
        raise RuntimeError("; ".join(errors))


if __name__ == "__main__":
    phase, main, *sides = sys.argv[1:]
    if phase not in ("off", "dim", "wake"):
        raise SystemExit("Expected off, dim or wake")
    directory = Path(os.environ["XDG_RUNTIME_DIR"]) / "lock-explorer-power"
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / "mutex").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        apply(phase, main, sides, directory / "brightness.json")
