#!/usr/bin/env python3
"""
This script converts RGB image datasets stored in an HDF5 (.h5) file into MP4 video files.
It automatically locates all RGB video datasets (shape: N x H x W x 3) within each demo
and exports them to a folder with the same name as the HDF5 file.

Usage:
    python3 h5_to_video.py <path_to_hdf5_file.h5>
"""

import sys
from pathlib import Path

# Provide a helpful error message if dependencies are missing
try:
    import cv2
    import h5py
    import numpy as np
except ImportError as e:
    print(f"\n[ERROR] Missing required library: {e}")
    print("Please make sure you have activated the correct environment (e.g., 'spot' or 'teleop'):")
    print("    conda activate spot")
    print("Or install the dependencies:")
    print("    pip install h5py opencv-python numpy\n")
    sys.exit(1)


def compute_fps(demo_grp, default_fps: float = 10.0) -> float:
    """
    Attempt to compute the actual FPS of the demo using timestamps.
    Looks for 't' or 'timestamps' dataset in standard locations.
    """
    t_ds = None
    if "obs" in demo_grp and "t" in demo_grp["obs"]:
        t_ds = demo_grp["obs/t"]
    elif "t" in demo_grp:
        t_ds = demo_grp["t"]
    elif "obs" in demo_grp and "timestamps" in demo_grp["obs"]:
        t_ds = demo_grp["obs/timestamps"]
    elif "timestamps" in demo_grp:
        t_ds = demo_grp["timestamps"]

    if t_ds is None:
        return default_fps

    try:
        t = np.asarray(t_ds).reshape(-1)
        if t.size <= 1:
            return default_fps
        dt = np.diff(t)
        dt = dt[dt > 0]
        if dt.size == 0:
            return default_fps
        return float(1.0 / np.mean(dt))
    except Exception:
        return default_fps


def find_rgb_datasets(group) -> list[tuple[str, h5py.Dataset]]:
    """
    Recursively find all datasets in a group that represent RGB images.
    An RGB dataset is defined as having shape (N, H, W, 3) and dtype uint8.
    """
    datasets = []

    def visitor(name, obj):
        if isinstance(obj, h5py.Dataset):
            # Check shape: length 4, and last dimension is 3
            if len(obj.shape) == 4 and obj.shape[3] == 3:
                datasets.append((name, obj))

    group.visititems(visitor)
    return datasets


def main():
    if len(sys.argv) < 2:
        print("[ERROR] HDF5 file path is required.")
        print("Usage: python3 h5_to_video.py <path_to_file.h5>")
        return 1

    h5_path = Path(sys.argv[1])
    if not h5_path.exists():
        print(f"[ERROR] HDF5 file not found: {h5_path}")
        return 1

    # Output to folder with same name as h5 file (excluding the extension)
    out_dir = h5_path.parent / h5_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Reading: {h5_path.name}")
    print(f"Output directory: {out_dir.resolve()}\n")

    with h5py.File(h5_path, "r") as hf:
        # Check standard root structures
        if "data" in hf:
            root_grp = hf["data"]
        else:
            root_grp = hf

        # Find all demo groups
        demo_keys = sorted(
            [k for k in root_grp.keys() if k.startswith("demo_")],
            key=lambda x: int(x[5:]) if x[5:].isdigit() else x
        )

        if not demo_keys:
            # If no demo_ keys, maybe the file contains datasets directly at root
            # or in a single group. Let's treat the root as a single demo.
            print("[INFO] No 'demo_' groups found. Scanning entire file for RGB datasets...")
            rgb_datasets = find_rgb_datasets(root_grp)
            if not rgb_datasets:
                print("[ERROR] No RGB datasets found in the HDF5 file.")
                return 1
            
            fps = compute_fps(root_grp, default_fps=10.0)
            for rel_name, dataset in rgb_datasets:
                clean_name = rel_name.replace("/", "_")
                video_name = f"{clean_name}.mp4"
                video_path = out_dir / video_name
                write_video(dataset, video_path, fps)
            return 0

        print(f"Found {len(demo_keys)} demo(s) to process.")
        
        for demo_key in demo_keys:
            demo_grp = root_grp[demo_key]
            rgb_datasets = find_rgb_datasets(demo_grp)
            
            if not rgb_datasets:
                print(f"  [-] {demo_key}: No RGB datasets found.")
                continue

            fps = compute_fps(demo_grp, default_fps=10.0)
            
            for rel_name, dataset in rgb_datasets:
                # Clean name: convert slashes to underscores (e.g. obs/images_0 -> obs_images_0)
                clean_name = rel_name.replace("/", "_")
                # Filename: demo_X_obs_images_0.mp4
                video_name = f"{demo_key}_{clean_name}.mp4"
                video_path = out_dir / video_name
                write_video(dataset, video_path, fps, prefix=f"  [+] {demo_key}/{rel_name}")

    print("\n[SUCCESS] Video generation completed.")
    return 0


def write_video(dataset, video_path: Path, fps: float, prefix: str = "Writing") -> None:
    """Writes an HDF5 dataset of frames to an MP4 video file."""
    frames = dataset[...]
    total_frames = frames.shape[0]
    
    if total_frames == 0:
        print(f"{prefix}: dataset is empty, skipping.")
        return

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

    bar_length = 30
    for i in range(total_frames):
        frame = frames[i]
        
        # Ensure 3-channel image (e.g. convert grayscale to BGR if necessary)
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
            
        out.write(frame)
        
        # Update progress bar
        percent = (i + 1) / total_frames
        filled = int(bar_length * percent)
        bar = "=" * filled + " " * (bar_length - filled)
        sys.stdout.write(f"\r{prefix}: [{bar}] {int(percent * 100):3d}% ({i+1}/{total_frames})")
        sys.stdout.flush()

    out.release()
    sys.stdout.write(f"\r{prefix}: [{'=' * bar_length}] 100% - Saved to {video_path.name} ({fps:.1f} fps)\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Cancelled by user.")
        sys.exit(1)
