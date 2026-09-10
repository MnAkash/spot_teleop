#!/usr/bin/env python3
"""
Quick SpaceMouse monitor with rolling plots.

- Streams x/y/z + roll/pitch/yaw and button states.
- Uses a rolling time window so you can spot stale samples or lag.
- Close the plot window or press Ctrl+C to quit.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pyspacemouse


def main():
    window_sec = 5.0          # how many seconds to show
    target_hz = 60.0          # nominal polling/plot rate
    maxlen = int(window_sec * target_hz) + 5

    pyspacemouse.open()
    print("SpaceMouse opened. Move the puck; close the plot or Ctrl+C to exit.")

    # Only plot x and y for lower overhead
    dof_names = ["x", "y"]
    series: Dict[str, deque] = {k: deque(maxlen=maxlen) for k in dof_names}
    times = deque(maxlen=maxlen)
    buttons: List[int] = [0, 0]
    button_history: List[deque] = []
    last_state_t = None

    # Figure/axes setup
    plt.ion()
    fig, (ax_dof, ax_btn) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    lines_dof = []
    for name in dof_names:
        (line,) = ax_dof.plot([], [], label=name)
        lines_dof.append(line)
    ax_dof.set_ylabel("DOF (-1..1)")
    ax_dof.set_ylim(-1.1, 1.1)
    ax_dof.legend(loc="upper left")
    ax_dof.grid(True, linestyle="--", alpha=0.4)

    ax_btn.set_ylabel("Buttons")
    ax_btn.set_ylim(-0.2, 1.2)
    ax_btn.grid(True, linestyle="--", alpha=0.4)

    t0 = time.time()
    target_dt = 1.0 / target_hz
    stale_count = 0

    try:
        while plt.fignum_exists(fig.number):
            loop_start = time.time()
            now = loop_start - t0
            state = pyspacemouse.read()

            if state is None:
                stale = True
                values = [0.0] * len(dof_names)
            else:
                stale = last_state_t is not None and abs(state.t - last_state_t) < 1e-6
                last_state_t = state.t
                values = [getattr(state, k) for k in dof_names]
                buttons = list(state.buttons)

            if stale:
                stale_count += 1
            else:
                stale_count = 0

            times.append(now)
            for name, val in zip(dof_names, values):
                series[name].append(val)

            # Ensure button history matches current button count
            if len(button_history) != len(buttons):
                button_history = [deque(maxlen=maxlen) for _ in buttons]
            for dq, val in zip(button_history, buttons):
                dq.append(val)

            # Update DOF lines
            for line, name in zip(lines_dof, dof_names):
                line.set_data(times, series[name])

            # Update button lines
            ax_btn.cla()
            ax_btn.set_ylabel("Buttons")
            ax_btn.set_ylim(-0.2, 1.2)
            ax_btn.grid(True, linestyle="--", alpha=0.4)
            for idx, dq in enumerate(button_history):
                ax_btn.step(times, dq, where="post", label=f"btn{idx}")
            if button_history:
                ax_btn.legend(loc="upper left", ncol=4)

            # X-limits roll with window
            if times:
                t_min = max(0.0, times[-1] - window_sec)
                ax_dof.set_xlim(t_min, t_min + window_sec)
                ax_btn.set_xlim(t_min, t_min + window_sec)

            # Annotate stale status
            ax_dof.set_title(
                f"SpaceMouse stream ({'stale' if stale_count > 2 else 'live'})"
            )

            fig.canvas.draw()
            fig.canvas.flush_events()

            sleep = max(0.0, target_dt - (time.time() - loop_start))
            time.sleep(sleep)
    except KeyboardInterrupt:
        pass
    finally:
        plt.ioff()
        plt.close(fig)
        pyspacemouse.close()
        print("Closed.")


if __name__ == "__main__":
    main()
