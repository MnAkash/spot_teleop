#!/usr/bin/env python3
"""
Test sequence using SpotRobotController:
1) Undock
2) Move base to (x=5, y=0, yaw=0) in vision frame
3) Unstow arm
4) Stow arm
5) Move base to (x=3, y=0, yaw=0) in vision frame
6) Dock
"""
from __future__ import annotations

import math
import os
import time

from bosdyn.client.frame_helpers import VISION_FRAME_NAME

from spot_teleop.spot_controller import SpotRobotController

def _yaw_to_quat_xyzw(yaw: float):
    half = 0.5 * float(yaw)
    return 0.0, 0.0, math.sin(half), math.cos(half)


def main():
    robot_ip = os.environ.get("SPOT_ROBOT_IP", "192.168.1.138")
    user = os.environ.get("BOSDYN_CLIENT_USERNAME", "user")
    password = os.environ.get("BOSDYN_CLIENT_PASSWORD", "password")

    print(f"Connecting to Spot at {robot_ip} ...")
    spot = SpotRobotController(robot_ip, user, password)

    goal1 = (5.0, 0.0, 0.0)
    goal2 = (3.0, 0.0, 0.0)

    try:
        print("[1/6] Undock")
        spot.undock()
        time.sleep(1.0)

        print("[2/6] Stand")
        spot.stand()
        time.sleep(1.0)

        print(f"[3/6] Move base to x={goal1[0]}, y={goal1[1]}, yaw={goal1[2]} in vision")
        move_timeout_1 = 25.0
        qx1, qy1, qz1, qw1 = _yaw_to_quat_xyzw(goal1[2])
        goal1_pose = [goal1[0], goal1[1], 0.0, qx1, qy1, qz1, qw1]
        spot.move_base_to_pose(
            goal1_pose,
            timeout=move_timeout_1,
            frame_name=VISION_FRAME_NAME,
            blocking=True,
        )

        print("[4/6] Unstow arm")
        spot.unstow_arm()

        print("[5/6] Stow arm")
        spot.stow_arm()

        print(f"[6/6] Move base to x={goal2[0]}, y={goal2[1]}, yaw={goal2[2]} in vision")
        move_timeout_2 = 20.0
        qx2, qy2, qz2, qw2 = _yaw_to_quat_xyzw(goal2[2])
        goal2_pose = [goal2[0], goal2[1], 0.0, qx2, qy2, qz2, qw2]
        spot.move_base_to_pose(
            goal2_pose,
            timeout=move_timeout_2,
            frame_name=VISION_FRAME_NAME,
            blocking=True,
        )

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
    except Exception as e:
        print(f"[!] Sequence error: {e}")
    finally:
        print("[Final] Dock")
        try:
            spot.dock()
        except Exception as e:
            print(f"[!] Dock failed: {e}")


if __name__ == "__main__":
    main()
