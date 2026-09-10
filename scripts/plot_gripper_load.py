"""Live rolling-window plot of the gripper joint load (arm0.f1x torque, N*m).

Connects and powers on Spot but does NOT undock or move the robot; it just
polls robot state and plots the gripper motor's load after initialization.

Gripper control: press '[' to close a step, ']' to open a step. Starts open.
"""
import os
import threading
import time
from collections import deque

import matplotlib.pyplot as plt
from pynput import keyboard as pynput_keyboard

from spot_teleop.spot_controller import SpotRobotController

robot_ip = os.environ.get("SPOT_ROBOT_IP", "192.168.1.138")
user = os.environ.get("BOSDYN_CLIENT_USERNAME", "user")
password = os.environ.get("BOSDYN_CLIENT_PASSWORD", "password")

print(f"Connecting to Spot at {robot_ip} ...")
print(f"user: {user}, password: {len(password) * '*'}")

controller = SpotRobotController(robot_ip, user, password)

WINDOW = 200
RATE_HZ = 20.0
GRIPPER_STEP = 0.01

# --- gripper open/close via '[' and ']' -----------------------------------
gripper_opening = 1.0  # start open
gripper_lock = threading.Lock()
gripper_dirty = True  # send initial "open" command


def _on_press(key):
    global gripper_opening, gripper_dirty
    try:
        k = key.char
    except AttributeError:
        return
    if k not in ("[", "]"):
        return
    with gripper_lock:
        if k == "[":
            gripper_opening = max(0.0, gripper_opening - GRIPPER_STEP)
        else:
            gripper_opening = min(1.0, gripper_opening + GRIPPER_STEP)
        gripper_dirty = True


listener = pynput_keyboard.Listener(on_press=_on_press)
listener.daemon = True
listener.start()

plt.ion()
fig, ax = plt.subplots(figsize=(8, 4))
ax.set_title("Gripper joint load (arm0.f1x)  |  '[' close  ']' open")
ax.set_xlabel("samples")
ax.set_ylabel("Load [N*m]")
ax.set_xlim(0, WINDOW)
ax.grid(True, alpha=0.3)

xs = deque(maxlen=WINDOW)
loads = deque(maxlen=WINDOW)
(line_load,) = ax.plot([], [], label="gripper load")
ax.legend(loc="upper left")

k = 0
try:
    while True:
        with gripper_lock:
            dirty = gripper_dirty
            opening = gripper_opening
            gripper_dirty = False
        if dirty:
            controller.send_gripper(opening)
            print(f"[gripper] opening={opening:.2f}")

        load = controller.current_gripper_torque()

        xs.append(k)
        loads.append(load)
        k += 1

        line_load.set_data(xs, loads)
        ax.set_xlim(max(0, k - WINDOW), k if k > 0 else WINDOW)
        ax.relim()
        ax.autoscale_view(scalex=False, scaley=True)

        fig.canvas.draw_idle()
        plt.pause(0.001)
        time.sleep(1.0 / RATE_HZ)
except KeyboardInterrupt:
    print("Stopping gripper load plot.")
finally:
    listener.stop()
    plt.ioff()
    plt.show(block=False)
