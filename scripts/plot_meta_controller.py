"""Live plot of Meta Quest right-controller position vs time.

Connects to the Quest via the same OculusReader used by teleop, then live-plots
the right-controller position (x, y, z) against elapsed wall-clock time in a
rolling window. Move the controller and watch the traces track in real time; a
freeze-then-jump indicates lag in the input stream.

Usage:
    python plot_meta_controller.py            # auto-detect IP (wifi adb) / USB
    META_QUEST_IP=192.168.1.44 python plot_meta_controller.py
"""
import os
import time
from collections import deque

import numpy as np
import matplotlib.pyplot as plt

from spot_teleop.reader import OculusReader, get_connecteed_device_ip

HAND = "r"  # which controller to watch: 'r' (arm control) or 'l'
WINDOW_SEC = 10.0  # seconds of history to show
POLL_HZ = 90.0


def get_position(transforms):
    """Return the (x, y, z) translation of the chosen controller, or None."""
    if HAND not in transforms:
        return None
    mat = transforms[HAND]
    return np.array([mat[0, 3], mat[1, 3], mat[2, 3]], dtype=float)


def main():
    meta_ip = os.environ.get("META_QUEST_IP") or get_connecteed_device_ip()
    print(f"Connecting to Meta Quest (ip={meta_ip}) ...")
    reader = OculusReader(ip_address=meta_ip)

    plt.ion()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_title(f"Meta '{HAND}' controller position vs time")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("position [m]")
    ax.grid(True, alpha=0.3)
    (line_x,) = ax.plot([], [], label="x")
    (line_y,) = ax.plot([], [], label="y")
    (line_z,) = ax.plot([], [], label="z")
    ax.legend(loc="upper left")

    maxlen = int(WINDOW_SEC * POLL_HZ)
    ts = deque(maxlen=maxlen)
    px = deque(maxlen=maxlen)
    py = deque(maxlen=maxlen)
    pz = deque(maxlen=maxlen)

    t0 = time.time()
    last_pos = np.zeros(3)
    period = 1.0 / POLL_HZ

    try:
        while True:
            with reader._lock:
                transforms = dict(reader.last_transforms)

            pos = get_position(transforms)
            if pos is not None:
                last_pos = pos

            t = time.time() - t0
            ts.append(t)
            px.append(last_pos[0])
            py.append(last_pos[1])
            pz.append(last_pos[2])

            line_x.set_data(ts, px)
            line_y.set_data(ts, py)
            line_z.set_data(ts, pz)

            ax.set_xlim(max(0.0, t - WINDOW_SEC), t if t > 0 else WINDOW_SEC)
            ax.relim()
            ax.autoscale_view(scalex=False, scaley=True)

            fig.canvas.draw_idle()
            plt.pause(0.001)
            time.sleep(period)
    except KeyboardInterrupt:
        print("Stopping Meta controller plot.")
    finally:
        reader.stop()
        plt.ioff()
        plt.show(block=False)


if __name__ == "__main__":
    main()
