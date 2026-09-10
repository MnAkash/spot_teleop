#!/usr/bin/env python3
"""
Lightweight SpaceMouse live viewer (text only, minimal lag).

Shows raw x/y/z and roll/pitch/yaw plus buttons in a single updating line.
Marks samples as "STALE" if the HID timestamp doesn't advance between reads.

Exit with Ctrl+C.
"""
from __future__ import annotations

import sys
import time
from typing import List

import pyspacemouse


def fmt_axis(name: str, val: float) -> str:
    return f"{name}={val:+.3f}"


def main():
    target_display_hz = 60.0
    target_dt = 1.0 / target_display_hz

    pyspacemouse.open()
    print("SpaceMouse opened. Press Ctrl+C to quit.")

    last_t = None
    try:
        while True:
            loop_start = time.time()
            state = pyspacemouse.read()

            if state is None:
                line = "No data (is the device connected?)"
            else:
                stale = last_t is not None and abs(state.t - last_t) < 1e-6
                last_t = state.t

                axes = [
                    fmt_axis("x", state.x),
                    fmt_axis("y", state.y),
                    fmt_axis("z", state.z),
                    fmt_axis("roll", state.roll),
                    fmt_axis("pitch", state.pitch),
                    fmt_axis("yaw", state.yaw),
                ]
                buttons: List[int] = list(state.buttons)
                line = (
                    f"t={state.t:.6f}  {'STALE' if stale else 'live '}  "
                    + "  ".join(axes)
                    + f"  buttons={buttons}"
                )

            sys.stdout.write("\r" + line + " " * 4)
            sys.stdout.flush()

            sleep = max(0.0, target_dt - (time.time() - loop_start))
            time.sleep(sleep)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nClosing SpaceMouse...")
        try:
            pyspacemouse.close()
        except Exception:
            pass
        print("Done.")


if __name__ == "__main__":
    main()
