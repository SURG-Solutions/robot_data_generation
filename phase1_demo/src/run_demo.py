"""
Phase 1 CAD/STL Augmentation Pipeline — Demo Runner

Usage:
    python src/run_demo.py [--input PATH]

If data/input_stl/sample.stl is missing, the script auto-generates one.
"""

import argparse
import json
import os
import sys

# Allow imports from src/ when run as a script
sys.path.insert(0, os.path.dirname(__file__))

import trimesh

from load_mesh import load_mesh, bounding_box
from validate import mesh_report
from augment import scale_proportional, scale_non_proportional, rotate_z

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
INPUT_DIR = os.path.join(BASE_DIR, "data", "input_stl")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output_stl")
METADATA_DIR = os.path.join(BASE_DIR, "data", "metadata")
DEFAULT_INPUT = os.path.join(INPUT_DIR, "sample.stl")

# ---------------------------------------------------------------------------
# Augmentation spec
# ---------------------------------------------------------------------------
AUGMENTATIONS = [
    {
        "name": "scale_proportional_1.2",
        "fn": lambda m: scale_proportional(m, 1.2),
        "description": "Proportional scale ×1.2",
    },
    {
        "name": "scale_non_proportional_x1.1_y0.9_z1.3",
        "fn": lambda m: scale_non_proportional(m, 1.1, 0.9, 1.3),
        "description": "Non-proportional scale x=1.1 y=0.9 z=1.3",
    },
    {
        "name": "rotate_z_45deg",
        "fn": lambda m: rotate_z(m, 45),
        "description": "Rotation around Z-axis by 45°",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ensure_sample(path: str):
    """Auto-generate sample.stl if it doesn't exist."""
    if os.path.exists(path):
        return
    print("[INFO] sample.stl not found — generating fallback bracket mesh …")
    from generate_sample import make_bracket
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bracket = make_bracket()
    bracket.export(path)
    print(f"[INFO] Saved generated sample to {path}\n")


def fmt_bbox(bb: dict) -> str:
    return f"x={bb['x']:.2f}  y={bb['y']:.2f}  z={bb['z']:.2f}"


def separator(char="─", width=62):
    return char * width


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Phase 1 STL Augmentation Demo")
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Path to input STL file (default: data/input_stl/sample.stl)",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(METADATA_DIR, exist_ok=True)

    ensure_sample(args.input)

    # ------------------------------------------------------------------
    # Load + inspect source mesh
    # ------------------------------------------------------------------
    print(separator("═"))
    print("  Phase 1 CAD/STL Augmentation Pipeline")
    print(separator("═"))
    print(f"  Input : {os.path.abspath(args.input)}")

    mesh = load_mesh(args.input)
    src_bbox = bounding_box(mesh)
    src_report = mesh_report(mesh)

    print(f"\n  Source mesh")
    print(f"    Bounding box : {fmt_bbox(src_bbox)} mm")
    print(f"    Watertight   : {src_report['watertight']}")
    print(f"    Vertices     : {src_report['vertices']}")
    print(f"    Faces        : {src_report['faces']}")
    if src_report["volume"] is not None:
        print(f"    Volume       : {src_report['volume']:.2f} mm³")

    # ------------------------------------------------------------------
    # Run augmentations
    # ------------------------------------------------------------------
    print(f"\n{separator()}")
    print("  Augmented outputs")
    print(separator())

    metadata = {
        "source": {
            "path": os.path.abspath(args.input),
            "bounding_box_mm": src_bbox,
            **src_report,
        },
        "augmentations": [],
    }

    for aug in AUGMENTATIONS:
        out_name = aug["name"] + ".stl"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        augmented = aug["fn"](mesh)
        augmented.export(out_path)

        aug_bbox = bounding_box(augmented)
        aug_report = mesh_report(augmented)

        entry = {
            "name": aug["name"],
            "description": aug["description"],
            "output_file": os.path.abspath(out_path),
            "bounding_box_mm": aug_bbox,
            **aug_report,
        }
        metadata["augmentations"].append(entry)

        print(f"\n  [{aug['name']}]")
        print(f"    {aug['description']}")
        print(f"    Bounding box : {fmt_bbox(aug_bbox)} mm")
        print(f"    Watertight   : {aug_report['watertight']}")
        print(f"    Saved to     : {out_path}")

    # ------------------------------------------------------------------
    # Save metadata JSON
    # ------------------------------------------------------------------
    meta_path = os.path.join(METADATA_DIR, "run_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n{separator()}")
    print(f"  Metadata saved : {os.path.abspath(meta_path)}")
    print(separator("═"))
    print("  Done.")
    print(separator("═"))


if __name__ == "__main__":
    main()
