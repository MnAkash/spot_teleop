#!/usr/bin/env python3

'''
This script inspects and prints the structure of an HDF5 file in a tree-like format.
It displays groups and datasets along with their shapes and data types.

Usage:
    python h5_tree_analyzer.py <file.h5>
'''
import sys
import h5py

def print_h5_tree(group, indent="", names=None):
    """
    Recursively print the contents of an HDF5 group/dataset
    using an ASCII-tree style with '|' and '-'.
    """
    if names is None:
        items = group.items()
    else:
        items = ((name, group[name]) for name in names if name in group)
    for name, item in items:
        if isinstance(item, h5py.Group):
            # print group name with trailing '/'
            print(f"{indent}|-- {name}/")
            # increase indent for children
            print_h5_tree(item, indent + "|   ")
        elif isinstance(item, h5py.Dataset):
            # print dataset name, shape, and dtype
            print(f"{indent}|-- {name}  (shape={item.shape}, dtype={item.dtype})")
        else:
            # other HDF5 object types
            print(f"{indent}|-- {name}  ({type(item)})")

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file.h5>")
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with h5py.File(filename, 'r') as f:
            print(f"Inspecting HDF5 file: {filename}")
            if "data" in f:
                data_grp = f["data"]
                demo_keys = [k for k in data_grp.keys() if k.startswith("demo_") and k[5:].isdigit()]
                demo_keys.sort(key=lambda x: int(x[5:]))
                if demo_keys:
                    min_id = int(demo_keys[0][5:])
                    max_id = int(demo_keys[-1][5:])
                    print(f"Demo count: {len(demo_keys)} (range {min_id}-{max_id})")

                else:
                    print("Demo count: 0")
            print("/")
            if "data" not in f:
                print_h5_tree(f)
                return

            data_grp = f["data"]
            top_level = [k for k in f.keys() if k != "data"]
            if top_level:
                print_h5_tree(f, names=top_level)

            print("|-- data/")
            demo_keys = [k for k in data_grp.keys() if k.startswith("demo_") and k[5:].isdigit()]
            demo_keys.sort(key=lambda x: int(x[5:]))
            other_keys = [k for k in data_grp.keys() if k not in set(demo_keys)]
            if other_keys:
                print_h5_tree(data_grp, indent="|   ", names=other_keys)

            if demo_keys:
                print_h5_tree(data_grp, indent="|   ", names=[demo_keys[0]])
                if len(demo_keys) > 1:
                    print("Print remaining demos? [y/n]: ", end="", flush=True)
                    ans = input().strip().lower()
                    if ans in {"y", "yes"}:
                        print_h5_tree(data_grp, indent="|   ", names=demo_keys[1:])
    except (OSError, IOError) as e:
        print(f"Error opening '{filename}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
