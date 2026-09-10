import os
import h5py, time
import numpy as np
from spot_teleop.spot_controller import SpotRobotController
from bosdyn.client.math_helpers  import SE3Pose, Quat

robot_ip = os.environ.get("SPOT_ROBOT_IP", "192.168.1.138")
user     = os.environ.get("BOSDYN_CLIENT_USERNAME", "user")
password = os.environ.get("BOSDYN_CLIENT_PASSWORD", "password")

print(f"Connecting to Spot at {robot_ip} ...")
print(f"user: {user}, password: {password}")

controller = SpotRobotController(robot_ip, user, password)
# controller.undock()

# print("Moving base forward 5 meters")
# controller.move_base_to(goal_x=3.0, goal_y=0, goal_heading=0, timeout=10) # move forward 0.5 meter
# print("Base moved.")
# time.sleep(3)
# controller.move_base_to(goal_x=2.0, goal_y=0, goal_heading=0, timeout=10)
# time.sleep(3)
# controller.move_base_to(goal_x=3.0, goal_y=0, goal_heading=0, timeout=10) 

# time.sleep(5) # wait for the robot to undock
# controller.dock()
import time
import matplotlib.pyplot as plt
from collections import deque

plt.ion()
fig, ax = plt.subplots(figsize=(8, 4))
ax.set_title("End-effector force (hand frame)")
ax.set_xlabel("samples")
ax.set_ylabel("Force [N]")
ax.set_ylim(-5, 20)
ax.set_xlim(0, 100)
ax.grid(True, alpha=0.3)

xs = deque(maxlen=100)
fx = deque(maxlen=100)
fy = deque(maxlen=100)
fz = deque(maxlen=100)

(line_fx,) = ax.plot([], [], label='Fx')
(line_fy,) = ax.plot([], [], label='Fy')
(line_fz,) = ax.plot([], [], label='Fz')
ax.legend(loc="upper left")

k = 0

try:
    while True:
        man = controller.state_client.get_robot_state().manipulator_state
        force = np.array([
                man.estimated_end_effector_force_in_hand.x,
                man.estimated_end_effector_force_in_hand.y,
                man.estimated_end_effector_force_in_hand.z], dtype=np.float32)
        
        
        xs.append(k)
        fx.append(force[0])
        fy.append(force[1])
        fz.append(force[2])
        k += 1

        # update plot data
        line_fx.set_data(xs, fx)
        line_fy.set_data(xs, fy)
        line_fz.set_data(xs, fz)

        # keep x-axis following the window
        ax.set_xlim(max(0, k - 100), k if k > 0 else 100)

        fig.canvas.draw_idle()
        plt.pause(0.001)
        time.sleep(0.05)  # ~20 Hz
except KeyboardInterrupt:
    print("Stopping force plot.")
finally:
    plt.ioff()
    plt.show(block=False)