#!/usr/bin/env python3
import numpy as np
import cv2
from pathlib import Path

def npz_to_video(npz_path: Path, video_path: Path, default_fps: float = 10.0):
    # --- Load session ---
    data = np.load(npz_path, allow_pickle=True)
    images_obj = data["images_0"]   # object‐dtype array of ndarrays

    # --- Unpack to list of real uint8 arrays ---
    frames = []
    for img in images_obj:
        # if stored as object‐dtype ndarray, cast it
        if isinstance(img, np.ndarray) and img.dtype == object:
            img = img.astype(np.uint8)
        frames.append(img)

    if len(frames) == 0:
        print(f"[WARN] {npz_path.name} has no frames, skipping")
        return

    # --- Determine FPS from timestamps if present ---
    fps = default_fps
    if "t" in data.files:
        t = data["t"].flatten()
        if t.size > 1:
            dt = np.diff(t)
            fps = float(1.0 / np.mean(dt))

    # --- Prepare VideoWriter ---
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

    # --- Write frames ---
    for frame in frames:
        # ensure 3‑channel BGR uint8
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        out.write(frame)
    out.release()
    print(f"Wrote {video_path.name} @ {fps:.1f} fps")

def main():
    demos_dir = Path("demos")
    videos_dir = Path("videos")
    videos_dir.mkdir(exist_ok=True)

    for npz_path in sorted(demos_dir.glob("*.npz")):
        video_path = videos_dir / f"{npz_path.stem}.mp4"
        npz_to_video(npz_path, video_path)

if __name__ == "__main__":
    main()
