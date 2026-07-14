"""Stream Spot camera color + depth side by side."""

import argparse
import os
import sys
import time

import cv2
import numpy as np

import bosdyn.client
import bosdyn.client.util
from bosdyn.client.image import ImageClient


def decode_depth(image_response):
    """Convert a Spot depth image response to a uint16 numpy array."""
    depth = np.frombuffer(image_response.shot.image.data, dtype=np.uint16)
    depth = depth.reshape(image_response.shot.image.rows, image_response.shot.image.cols)
    return depth


def decode_color(image_response):
    """Convert a Spot color/fisheye image response to BGR uint8."""
    data = np.frombuffer(image_response.shot.image.data, dtype=np.uint8)
    color = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if color is None:
        raise ValueError("Failed to decode color image.")
    return color


def select_sources(camera: str, to_depth: bool) -> tuple[str, str]:
    """Return (depth_source, color_source) names matching get_depth_plus_visual_image.py."""
    if camera != "hand" and to_depth:
        raise ValueError("`--to-depth` is only supported for `--camera hand`.")

    if camera != "hand":
        return f"{camera}_depth_in_visual_frame", f"{camera}_fisheye_image"

    if to_depth:
        return "hand_depth", "hand_color_in_hand_depth_frame"

    return "hand_depth_in_hand_color_frame", "hand_color_image"


def maybe_rotate(image: np.ndarray, camera: str, auto_rotate: bool) -> np.ndarray:
    """Rotate front/right images upright if requested."""
    if not auto_rotate:
        return image
    if camera.startswith("front"):
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if camera.startswith("right"):
        return cv2.rotate(image, cv2.ROTATE_180)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show Spot camera color + depth side by side in real time."
    )
    env_default_host = os.environ.get("SPOT_ROBOT_IP", "192.168.1.138")
    bosdyn.client.util.add_base_arguments(parser)
    # Allow hostname via positional or --hostname by making the positional optional.
    for action in parser._actions:
        if action.dest == "hostname" and not action.option_strings:
            action.nargs = "?"
            action.required = False
            action.default = env_default_host
            break
    parser.add_argument(
        "--hostname",
        dest="hostname_opt",
        help=f"Robot hostname/IP (alternative to positional hostname, default env SPOT_ROBOT_IP or {env_default_host}).",
    )
    parser.add_argument(
        "--camera",
        default="hand",
        choices=["frontleft", "frontright", "left", "right", "back", "hand"],
        help="Camera source to stream.",
    )
    parser.add_argument(
        "--to-depth",
        action="store_true",
        help="For the hand camera, transform color to the depth frame.",
    )
    parser.add_argument(
        "--auto-rotate",
        action="store_true",
        default=True,
        help="Rotate front/right images to appear upright (default: enabled).",
    )
    options = parser.parse_args()
    if getattr(options, "hostname_opt", None):
        options.hostname = options.hostname_opt
    if not getattr(options, "hostname", None):
        # Fallback to environment default if nothing provided.
        options.hostname = env_default_host

    try:
        depth_source, color_source = select_sources(options.camera, options.to_depth)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    sdk = bosdyn.client.create_standard_sdk("spot_camera_stream")
    robot = sdk.create_robot(options.hostname)
    bosdyn.client.util.authenticate(robot)
    image_client = robot.ensure_client(ImageClient.default_service_name)

    try:
        cv2.namedWindow("Spot Depth + Color", cv2.WINDOW_AUTOSIZE)
    except cv2.error:
        sys.stderr.write(
            "OpenCV was built without GUI support (HighGUI). "
            "Install a GUI-enabled build (e.g., pip install opencv-python) "
            "and system GUI libs (Ubuntu: sudo apt-get install libgtk2.0-dev libgl1). "
            f"DISPLAY={os.environ.get('DISPLAY')!r}\n"
        )
        return 1

    last_print = time.time()
    try:
        while True:
            responses = image_client.get_image_from_sources([depth_source, color_source])
            if len(responses) < 2:
                sys.stderr.write("Failed to get both depth and color images.\n")
                continue

            depth_resp, color_resp = responses

            try:
                depth = decode_depth(depth_resp)
                color = decode_color(color_resp)
            except Exception as exc:  # pylint: disable=broad-except
                sys.stderr.write(f"Decoding error: {exc}\n")
                continue

            depth_8u = cv2.convertScaleAbs(depth, alpha=0.03)
            depth_colormap = cv2.applyColorMap(depth_8u, cv2.COLORMAP_JET)

            color = maybe_rotate(color, options.camera, options.auto_rotate)
            depth_colormap = maybe_rotate(depth_colormap, options.camera, options.auto_rotate)

            if color.shape[:2] != depth_colormap.shape[:2]:
                depth_colormap = cv2.resize(depth_colormap, (color.shape[1], color.shape[0]))

            h, w = depth.shape
            center = (w // 2, h // 2)
            center_depth = int(depth[center[1], center[0]])
            cv2.circle(depth_colormap, center, 4, (0, 0, 0), -1)
            cv2.putText(
                depth_colormap,
                f"{center_depth} depth-units",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            stacked = np.hstack((color, depth_colormap))
            cv2.imshow("Spot Depth + Color", stacked)

            key = cv2.waitKey(1)
            if key == ord("q") or key == 27:
                break

            if time.time() - last_print > 5:
                print("Streaming Spot color + depth... press 'q' or ESC to quit.")
                last_print = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
