'''
This script is used to create hf datasets from recorded npz files.

Usage:
python3 create_dataset.py --output my_dataset.h5 [--input_dir data/]

Author: Moniruzzaman Akash
'''

import numpy as np
import h5py
from pathlib import Path
import sys, os
import argparse


# ---------- helpers ----------------------------------------------------------
def quat_to_matrix(q):
    """q: (...,4) with (x,y,z,w). Return (...,3,3)."""
    x, y, z, w = [q[..., i] for i in range(4)]
    tx, ty, tz = 2*x, 2*y, 2*z
    R = np.empty(q.shape[:-1] + (3, 3), dtype=q.dtype)
    R[..., 0, 0] = 1 - ty*y - tz*z
    R[..., 0, 1] = tx*y - tz*w
    R[..., 0, 2] = tx*z + ty*w
    R[..., 1, 0] = tx*y + tz*w
    R[..., 1, 1] = 1 - tx*x - tz*z
    R[..., 1, 2] = ty*z - tx*w
    R[..., 2, 0] = tx*z - ty*w
    R[..., 2, 1] = ty*z + tx*w
    R[..., 2, 2] = 1 - tx*x - ty*y
    return R

def mat_to_rot6d(R):
    """
    Convert a rotation matrix to Zhou et al.'s 6-D representation
    by *column-wise* stacking of the first two columns.
    R : (...,3,3)  →  (...,6)
    """
    return np.concatenate([R[..., :, 0],   # first column  (R00,R10,R20)
                           R[..., :, 1]],  # second column (R01,R11,R21)
                          axis=-1)


def _demo_index_key(name: str):
    if name.startswith("demo_"):
        tail = name[5:]
        if tail.isdigit():
            return int(tail)
    return float("inf")


def print_first_demo_tree(h5_path: Path):
    with h5py.File(h5_path, "r") as hf:
        if "data" not in hf or len(hf["data"].keys()) == 0:
            print("[INFO] No demos found in H5.")
            return

        demo_names = sorted(hf["data"].keys(), key=_demo_index_key)
        demo_name = demo_names[0]
        demo_grp = hf["data"][demo_name]

        print("\n[H5 Tree] First demo")
        print("data/")
        print(f"└── {demo_name}/")

        def _print_group(group, prefix):
            keys = list(group.keys())
            for i, key in enumerate(keys):
                is_last = i == len(keys) - 1
                branch = "└── " if is_last else "├── "
                child = group[key]
                if isinstance(child, h5py.Dataset):
                    print(f"{prefix}{branch}{key} (shape={child.shape}, dtype={child.dtype})")
                else:
                    print(f"{prefix}{branch}{key}/")
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    _print_group(child, next_prefix)

        _print_group(demo_grp, "    ")

# ---------- main conversion --------------------------------------------------
def build_hdf5_from_npz(demos_dir: Path, h5_path: Path):
    with h5py.File(h5_path, "w") as hf:
        data_grp = hf.create_group("data")
        for npz_path in sorted(demos_dir.glob("*.npz")):
            demo_id = npz_path.stem
            
            grp     = data_grp.create_group(f"demo_{demo_id}")

            data    = np.load(npz_path, allow_pickle=True)

            # ------------------------------------------------------------------
            # OBSERVATIONS
            # ------------------------------------------------------------------
            obs_grp   = grp.create_group("obs")

            # images -----------------------------------------------------------
            frames = [img.astype(np.uint8) for img in data["images_0"]]
            frames = np.stack(frames, axis=0)                # (N,H,W,3)
            obs_grp.create_dataset("images_0", data=frames[:-1], compression="gzip")

            # depth images (raw uint16, no colorization) -----------------------
            if "images_0_depth" in data.files:
                depth_frames = [img.astype(np.uint16) for img in data["images_0_depth"]]
                depth_frames = np.stack(depth_frames, axis=0)  # (N,H,W)
                obs_grp.create_dataset("images_0_depth", data=depth_frames[:-1], compression="gzip")
            else:
                print(f"[WARN] {npz_path.name} missing 'images_0_depth'")

            # external camera images ------------------------------------------
            if "images_1" in data.files:
                ext_frames = [img.astype(np.uint8) for img in data["images_1"]]
                ext_frames = np.stack(ext_frames, axis=0)  # (N,H,W,3)
                obs_grp.create_dataset("images_1", data=ext_frames[:-1], compression="gzip")
            else:
                print(f"[WARN] {npz_path.name} missing 'images_1'")

            if "images_1_depth" in data.files:
                ext_depth_frames = [img.astype(np.uint16) for img in data["images_1_depth"]]
                ext_depth_frames = np.stack(ext_depth_frames, axis=0)  # (N,H,W)
                obs_grp.create_dataset("images_1_depth", data=ext_depth_frames[:-1], compression="gzip")
            else:
                print(f"[WARN] {npz_path.name} missing 'images_1_depth'")

            # split pose -------------------------------------------------------
            eef_pose   = data["ee_pose"].astype(np.float32)  # (N,7)
            eef_pos    = eef_pose[:, :3]                     # (N,3)
            eef_quat   = eef_pose[:, 3:]                     # (N,4)

            obs_grp.create_dataset("eef_pos",  data=eef_pos[:-1],  compression="gzip")
            obs_grp.create_dataset("eef_quat", data=eef_quat[:-1], compression="gzip")

            # copy other arrays (keep T‑1 length) ------------------------------
            for key in ("arm_q", "arm_dq", "vision_in_body",
                        "body_vel", "gripper", "gripper_load", "ee_force", "t"):
                if key in data.files:
                    if key == "t":
                        arr = data[key].astype(np.float64)
                    else:   # other arrays are float32
                        arr = data[key].astype(np.float32)
                    obs_grp.create_dataset(key, data=arr[:-1], compression="gzip")
                else:
                    print(f"[WARN] {npz_path.name} missing '{key}'")

            # ------------------------------------------------------------------
            # ACTIONS      Δp  (3) + rot6d  (6) + Δgripper (1)  →  (N‑1,10)
            # ------------------------------------------------------------------
            pos_next     = eef_pos[1:]                      # (N-1,3)
            pos_curr     = eef_pos[:-1]
            delta_pos    = pos_next - pos_curr              # (N-1,3)

            R_curr       = quat_to_matrix(eef_quat[:-1])    # (N-1,3,3)
            R_next       = quat_to_matrix(eef_quat[1:])
            R_rel        = np.einsum("...ji,...jk->...ik", R_curr, R_next)
            rot6d        = mat_to_rot6d(R_rel).astype(np.float32)  # (N-1,6)

            # ----------- ABSOLUTE gripper command (take the *next* value) -----
            if "gripper" in data.files:
                g_target = data["gripper"][1:].astype(np.float32).reshape(-1, 1)  # (N‑1,1)
            else:
                g_target = np.zeros((delta_pos.shape[0], 1), dtype=np.float32)

            actions      = np.concatenate([delta_pos, rot6d, g_target], axis=-1)
            grp.create_dataset("actions", data=actions, compression="gzip")

            print(f"Packed demo_{demo_id}: obs {actions.shape[0]} steps, "
                  f"action shape {actions.shape}")

        # ----------------------------------------------------------------------
        # GLOBAL METADATA (optional)
        # ----------------------------------------------------------------------
        if "arm_joint_names" in data.files:
            names = np.array(data["arm_joint_names"].tolist(), dtype="S")
            hf.create_dataset("arm_joint_names", data=names, compression="gzip")

# ----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert NPZ demonstrations to HDF5 dataset.")
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path to the output HDF5 file (e.g., my_dataset.h5). Automatically appends '.h5' if missing."
    )
    parser.add_argument(
        "--input_dir", "-i",
        default="data",
        help="Directory containing the recorded .npz files. Default is 'data'."
    )
    args = parser.parse_args()

    output_name = args.output
    if not output_name.endswith(".h5"):
        output_name += ".h5"

    output_h5 = Path(output_name)
    demos_folder = Path(args.input_dir)

    if os.path.exists(output_h5):
        print(f"Output file '{output_h5}' already exists. Please use a different name.")
        sys.exit(1)

    if not os.path.exists(demos_folder):
        print(f"Input directory '{demos_folder}' does not exist.")
        sys.exit(1)

    build_hdf5_from_npz(demos_folder, output_h5)
    print_first_demo_tree(output_h5)
    print(f"\nAll demos written to {output_h5}")
