"""
Fallback script: generates a bracket-like sample mesh using trimesh primitives
and saves it as data/input_stl/sample.stl.

Run directly:
    python src/generate_sample.py
"""

import os
import numpy as np
import trimesh

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "input_stl", "sample.stl"
)


def make_bracket() -> trimesh.Trimesh:
    """
    A simple L-shaped bracket built from two box primitives:
      - Horizontal base plate: 80 x 40 x 8 mm
      - Vertical wall:         8  x 40 x 50 mm (sitting on one end of the base)
    """
    base = trimesh.creation.box(extents=[80, 40, 8])
    # move base so its bottom face sits at z=0
    base.apply_translation([0, 0, 4])

    wall = trimesh.creation.box(extents=[8, 40, 50])
    # align wall to the left edge of the base, standing upright
    wall.apply_translation([-36, 0, 25 + 8])  # z offset = wall_height/2 + base_height

    bracket = trimesh.boolean.union([base, wall], engine="blender") if False else \
              trimesh.util.concatenate([base, wall])

    return bracket


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    bracket = make_bracket()
    bracket.export(OUTPUT_PATH)
    print(f"Sample bracket mesh saved to: {os.path.abspath(OUTPUT_PATH)}")
    print(f"  Vertices : {len(bracket.vertices)}")
    print(f"  Faces    : {len(bracket.faces)}")
    extents = bracket.bounding_box.extents
    print(f"  BBox     : x={extents[0]:.1f}  y={extents[1]:.1f}  z={extents[2]:.1f} mm")


if __name__ == "__main__":
    main()
