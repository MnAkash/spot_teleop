"""
Display RealSense color and depth frames side by side in real time.
If you have a RealSense camera connected via USB, this example will show the color and depth streams stacked horizontally in a single window. The depth stream is colorized for better visualization, and the distance at the center pixel is displayed on the depth image.
Requirements:
- A RealSense camera connected via USB.
- The pyrealsense2 Python package (install via pip).
Usage:
    python examples/show_realsense.py

"""

import os
import sys
import time

import cv2
import numpy as np

try:
    import pyrealsense2 as rscontext
except ImportError:
    sys.stderr.write("pyrealsense2 is required (pip install pyrealsense2)\n")
    raise


def main() -> int:
    """Stream depth + color, align depth to color, and show them stacked horizontally."""
    context = rs.context()
    if not context.devices:
        sys.stderr.write("No RealSense device found. Please connect a camera via USB.\n")
        return 1

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    try:
        pipeline.start(config)
    except Exception as exc:  # pylint: disable=broad-except
        sys.stderr.write(f"Failed to start RealSense pipeline: {exc}\n")
        return 1

    try:
        cv2.namedWindow("RealSense Depth + Color", cv2.WINDOW_AUTOSIZE)
    except cv2.error:
        sys.stderr.write(
            "OpenCV was built without GUI support (HighGUI). "
            "Install a GUI-enabled build (e.g., pip install opencv-python) "
            "and system GUI libs (Ubuntu: sudo apt-get install libgtk2.0-dev libgl1). "
            f"DISPLAY={os.environ.get('DISPLAY')!r}\n"
        )
        pipeline.stop()
        return 1

    align = rs.align(rs.stream.color)
    last_print = time.time()

    try:
        while True:
            frames = pipeline.wait_for_frames()
            aligned_frames = align.process(frames)

            depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()
            if not depth_frame or not color_frame:
                continue

            depth_image = np.asanyarray(depth_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())

            depth_image_8u = cv2.convertScaleAbs(depth_image, alpha=0.03)
            depth_colormap = cv2.applyColorMap(depth_image_8u, cv2.COLORMAP_JET)

            # Draw distance at the center pixel to give a quick depth reading.
            h, w = depth_image.shape
            center = (w // 2, h // 2)
            center_distance = depth_frame.get_distance(*center)
            cv2.circle(depth_colormap, center, 4, (0, 0, 0), -1)
            cv2.putText(
                depth_colormap,
                f"{center_distance:.3f} m",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            stacked = np.hstack((color_image, depth_colormap))
            cv2.imshow("RealSense Depth + Color", stacked)

            key = cv2.waitKey(1)
            if key == ord("q") or key == 27:
                break

            if time.time() - last_print > 5:
                print("Streaming color + depth... press 'q' or ESC to quit.")
                last_print = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
