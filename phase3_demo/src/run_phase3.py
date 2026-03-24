"""
Phase 3 — Advanced CadQuery Augmentation Demo

Generates 7 STL variants of a parametric sheet-metal bracket:
  v1  baseline          — 2 base mounting holes
  v2  add_hole          — extra centre hole on base plate
  v3  remove_hole       — one base hole removed
  v4  resize            — larger bracket (120 × 60 × 70 mm)
  v5  wall_hole         — mounting hole on vertical wall
  v6  slot              — adjustment slot on base plate
  v7  fillet+wall_hole  — corner fillets + wall hole combined

Usage:
    python src/run_phase3.py [options]

Options:
    --length    F   base plate length mm  (default 80)
    --width     F   base plate width  mm  (default 40)
    --height    F   wall height       mm  (default 50)
    --thickness F   wall/plate thick  mm  (default 4)
    --hole-d    F   default hole ⌀    mm  (default 8)
    --outdir    PATH  output directory (default data/output_stl)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import cadquery as cq
from generate_part import BracketParams, build_bracket, validate_params
from advanced_augment import (
    add_hole, remove_hole, resize,
    add_wall_hole, add_slot, set_fillet,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_OUTDIR = os.path.join(BASE_DIR, "data", "output_stl")


# ── Helpers ───────────────────────────────────────────────────────────────────
def bbox(solid: cq.Workplane) -> dict:
    bb = solid.val().BoundingBox()
    return {
        "x": round(bb.xmax - bb.xmin, 3),
        "y": round(bb.ymax - bb.ymin, 3),
        "z": round(bb.zmax - bb.zmin, 3),
    }


def fmt_bbox(bb: dict) -> str:
    return f"x={bb['x']:.2f}  y={bb['y']:.2f}  z={bb['z']:.2f} mm"


def export_stl(solid: cq.Workplane, path: str):
    cq.exporters.export(solid, path)


def separator(char="─", width=66):
    return char * width


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 3 CadQuery Augmentation Demo")
    parser.add_argument("--length",    type=float, default=80.0)
    parser.add_argument("--width",     type=float, default=40.0)
    parser.add_argument("--height",    type=float, default=50.0)
    parser.add_argument("--thickness", type=float, default=4.0)
    parser.add_argument("--hole-d",    type=float, default=8.0, dest="hole_d")
    parser.add_argument("--outdir",    default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # ── Base parameters ───────────────────────────────────────────────────────
    base = BracketParams(
        length=args.length,
        width=args.width,
        height=args.height,
        thickness=args.thickness,
        hole_diameter=args.hole_d,
        holes=[
            (-25.0, 0.0, args.hole_d),
            ( 25.0, 0.0, args.hole_d),
        ],
    )

    # ── Variant pipeline ──────────────────────────────────────────────────────
    p2, d2 = add_hole(base, x=0.0, y=0.0)
    p3, d3 = remove_hole(base, index=-1)
    p4, d4 = resize(base, length=120.0, width=60.0, height=70.0)
    p5, d5 = add_wall_hole(base, y=0.0, z=base.thickness + base.height * 0.4)
    p6, d6 = add_slot(base, x=0.0, y=0.0, slot_length=24.0, slot_width=args.hole_d)

    p7, d7a = add_wall_hole(base, y=0.0, z=base.thickness + base.height * 0.4)
    p7, d7b = set_fillet(p7, radius=2.0)
    d7 = d7a + "  |  " + d7b

    variants = [
        ("v1_baseline",       base, f"Baseline — {len(base.holes)} base holes (⌀{args.hole_d:.0f} mm at x=±25)"),
        ("v2_add_hole",       p2,   d2),
        ("v3_remove_hole",    p3,   d3),
        ("v4_resize",         p4,   d4),
        ("v5_wall_hole",      p5,   d5),
        ("v6_slot",           p6,   d6),
        ("v7_fillet_wallhole",p7,   d7),
    ]

    # ── Print header ──────────────────────────────────────────────────────────
    print(separator("═"))
    print("  Phase 3 — CadQuery Parametric Augmentation")
    print(separator("═"))
    print(f"  Base params : {args.length}×{args.width}×{args.height} mm  "
          f"t={args.thickness} mm  ⌀hole={args.hole_d} mm")
    print(f"  Output dir  : {os.path.abspath(args.outdir)}")

    # Validate base params
    warns = validate_params(base)
    if warns:
        print(f"\n  [WARNINGS]")
        for w in warns:
            print(f"    ⚠  {w}")

    print(separator())

    # ── Build + export each variant ───────────────────────────────────────────
    for name, params, description in variants:
        out_path = os.path.join(args.outdir, f"{name}.stl")

        v_warns = validate_params(params)
        solid = build_bracket(params)
        export_stl(solid, out_path)
        bb = bbox(solid)

        print(f"\n  [{name}]")
        print(f"    Edit         : {description}")
        print(f"    Base holes   : {len(params.holes)}  "
              f"Wall holes: {len(params.wall_holes)}  "
              f"Slots: {len(params.slots)}  "
              f"Fillet: {params.fillet_radius:.1f} mm")
        print(f"    Bounding box : {fmt_bbox(bb)}")
        if v_warns:
            for w in v_warns:
                print(f"    ⚠  {w}")
        print(f"    Saved        : {out_path}")

    print(f"\n{separator('═')}")
    print(f"  Done — {len(variants)} STL variants exported.")
    print(separator("═"))


if __name__ == "__main__":
    main()
