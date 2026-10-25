#!/usr/bin/env python3
"""Per-output locked power control; restore original DDC brightness on activity."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import fcntl
import time


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


def save_state(state, saved):
    temporary = state.with_suffix('.tmp')
    with temporary.open('w') as output:
        json.dump(saved, output)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(state)
    directory_fd = os.open(state.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def migrate_state(state, legacy):
    if not state.exists() and legacy.exists():
        save_state(state, json.loads(legacy.read_text()))
        legacy.unlink()


def restore_hardware_power(state):
    if not state.exists():
        return []
    saved = json.loads(state.read_text())
    errors = []
    for monitor, bus in list(saved.items()):
        try:
            # Hard-off monitors cannot answer detect's initial DDC probes.
            # Use the address saved before power-off and send wake directly.
            run("ddcutil", "--bus", bus, "--skip-ddc-checks", "--noverify", "setvcp", "D6", "1")
            for attempt in range(3):
                try:
                    response = run("ddcutil", "--bus", bus, "getvcp", "D6", "--terse")
                    if re.search(r"VCP D6 SNC x0*1\b", response):
                        break
                    raise ValueError(f"Monitor did not return to hardware power-on: {response!r}")
                except (subprocess.SubprocessError, OSError, ValueError):
                    if attempt == 2:
                        raise
                    time.sleep(0.3)
            del saved[monitor]
            save_state(state, saved)
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            errors.append(f"{monitor}: hardware wake failed: {error}")
    if not saved:
        state.unlink()
    return errors


def apply(phase, main, sides, state):
    if phase == "off":
        run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "disable", monitor = ' + json.dumps(main) + ' })')
        return
    saved = json.loads(state.read_text()) if state.exists() else {}
    errors = []
    if phase == "wake":
        run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "enable" })')
        # DPMS wake succeeded. Legacy DDC recovery is best-effort: retain
        # failed addresses, but never block the next locked DPMS deadline.
        hardware_errors = restore_hardware_power(state.with_name("power.json"))
        if hardware_errors:
            print("; ".join(hardware_errors), file=sys.stderr)
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
                        # Persist before dimming so recovery survives reboot too.
                        save_state(state, saved)
                    set_brightness(bus, 0)
                else:
                    set_brightness(bus, saved[monitor])
                    del saved[monitor]
                    save_state(state, saved)
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                # One monitor failing must not prevent the other from dimming.
                errors.append(f"{monitor}: {error}")
    if not saved and state.exists():
        state.unlink()
    if errors:
        raise RuntimeError("; ".join(errors))


def apply_policy(config, phase, power_state=None):
    """100% powers outputs off; opted-in monitors also get hardware DDC off."""
    targets = []
    if phase in ("main", "both") and config["mainTint"] == 100:
        targets.append(config["main"])
    if phase in ("sides", "both") and config["sideTint"] == 100:
        targets.extend(config["sides"])
    hardware_targets = set(targets).intersection(config.get("ddcPowerOffMonitors", []))
    if hardware_targets and power_state is None:
        raise ValueError("Hardware power-off requires persistent wake state")
    saved = json.loads(power_state.read_text()) if power_state and power_state.exists() else {}
    available = {}
    errors = []
    if hardware_targets.difference(saved):
        try:
            available = buses()
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            errors.append(f"hardware power bus detection failed: {error}")
    for monitor in dict.fromkeys(targets):
        if monitor in hardware_targets:
            try:
                # A saved address is a wake-recovery journal, not evidence that
                # the previous write succeeded. Reuse it on bounded retries.
                bus = saved.get(monitor) or available.get(monitor)
                if not bus:
                    raise ValueError("no accessible DDC bus for hardware power-off")
                saved[monitor] = bus
                # Persist first: even a timed-out write may have powered off.
                save_state(power_state, saved)
                # D6=5 is write-only; readback verification cannot work once off.
                run("ddcutil", "--bus", bus, "--skip-ddc-checks", "--noverify", "setvcp", "D6", "5")
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                errors.append(f"{monitor}: hardware power-off failed: {error}")
        try:
            run("hyprctl", "dispatch", 'hl.dsp.dpms({ action = "disable", monitor = ' + json.dumps(monitor) + ' })')
        except (subprocess.SubprocessError, OSError) as error:
            errors.append(f"{monitor}: {error}")
    if errors:
        raise RuntimeError("; ".join(errors))


if __name__ == "__main__":
    action = sys.argv[1]
    directory = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "omarchy/lock-explorer-power"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / "mutex").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = directory / "brightness.json"
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if runtime:
            migrate_state(state, Path(runtime) / "lock-explorer-power/brightness.json")
        if action == "policy":
            phase, raw_config = sys.argv[2:]
            if phase not in ("main", "sides", "both"):
                raise SystemExit("Expected main, sides or both")
            apply_policy(json.loads(raw_config), phase, directory / "power.json")
        else:
            phase, main, *sides = sys.argv[1:]
            if phase not in ("off", "dim", "wake"):
                raise SystemExit("Expected off, dim, wake or policy")
            apply(phase, main, sides, state)
