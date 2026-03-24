"""
generate_part.py — Build a parametric sheet-metal bracket using CadQuery.

The bracket is an L-profile:
  - a horizontal base plate with optional through-holes and slots
  - a vertical wall rising from one short edge with optional wall-holes
  - optional edge fillets on vertical corners

All dimensions are in millimetres.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import cadquery as cq


@dataclass
class BracketParams:
    # ── Outer envelope ────────────────────────────────────────────────────────
    length: float = 80.0      # X — total length of base plate
    width: float = 40.0       # Y — depth of base plate
    height: float = 50.0      # Z — height of vertical wall (above base plate top)
    thickness: float = 4.0    # uniform wall / plate thickness

    # ── Base-plate holes  (x, y, diameter) ───────────────────────────────────
    hole_diameter: float = 8.0
    holes: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (-25.0, 0.0, 8.0),
        ( 25.0, 0.0, 8.0),
    ])

    # ── Base-plate slots  (cx, cy, slot_length, slot_width) ──────────────────
    # slot_length = total length of the oblong; slot_width = narrow dimension
    slots: List[Tuple[float, float, float, float]] = field(default_factory=list)

    # ── Vertical wall holes  (y, z, diameter) ────────────────────────────────
    # z is measured from the ground; must be > thickness to land on the wall
    wall_holes: List[Tuple[float, float, float]] = field(default_factory=list)

    # ── Edge fillets on vertical corners (0 = off) ───────────────────────────
    fillet_radius: float = 0.0


# ── Geometry validation ───────────────────────────────────────────────────────

def validate_params(p: BracketParams) -> List[str]:
    """
    Return a list of human-readable warnings for geometric issues.
    An empty list means the params look valid.
    """
    warnings: List[str] = []

    # Positive dimensions
    for name, val in [
        ("length", p.length), ("width", p.width),
        ("height", p.height), ("thickness", p.thickness),
    ]:
        if val <= 0:
            warnings.append(f"{name} must be > 0 (got {val})")

    if p.thickness >= p.length / 2:
        warnings.append(
            f"thickness {p.thickness} >= length/2 {p.length/2:.1f} — wall may not fit"
        )
    if p.thickness >= p.width / 2:
        warnings.append(
            f"thickness {p.thickness} >= width/2 {p.width/2:.1f}"
        )

    # Base-plate holes
    for i, (hx, hy, hd) in enumerate(p.holes):
        if hd <= 0:
            warnings.append(f"Base hole {i}: diameter must be > 0 (got {hd})")
        if abs(hx) + hd / 2 > p.length / 2:
            warnings.append(
                f"Base hole {i} at x={hx:+.1f} (⌀{hd}) extends outside plate length"
            )
        if abs(hy) + hd / 2 > p.width / 2:
            warnings.append(
                f"Base hole {i} at y={hy:+.1f} (⌀{hd}) extends outside plate width"
            )

    # Base-plate slots
    for i, (sx, sy, sl, sw) in enumerate(p.slots):
        if sl <= 0 or sw <= 0:
            warnings.append(f"Slot {i}: dimensions must be > 0")
        if abs(sx) + sl / 2 > p.length / 2:
            warnings.append(f"Slot {i} extends outside plate in X")
        if abs(sy) + sw / 2 > p.width / 2:
            warnings.append(f"Slot {i} extends outside plate in Y")

    # Wall holes
    for i, (wy, wz, wd) in enumerate(p.wall_holes):
        if wd <= 0:
            warnings.append(f"Wall hole {i}: diameter must be > 0 (got {wd})")
        if abs(wy) + wd / 2 > p.width / 2:
            warnings.append(f"Wall hole {i} at y={wy:+.1f} extends outside wall width")
        if wz - wd / 2 < p.thickness:
            warnings.append(
                f"Wall hole {i} at z={wz:.1f} may intersect base plate (thickness={p.thickness})"
            )
        if wz + wd / 2 > p.thickness + p.height:
            warnings.append(
                f"Wall hole {i} at z={wz:.1f} extends above wall top "
                f"(max z={p.thickness + p.height:.1f})"
            )

    # Fillet
    if p.fillet_radius > 0 and p.fillet_radius >= p.thickness / 2:
        warnings.append(
            f"fillet_radius {p.fillet_radius} >= thickness/2 {p.thickness/2:.1f} — may fail"
        )

    return warnings


# ── Builder ───────────────────────────────────────────────────────────────────

def build_bracket(p: BracketParams) -> cq.Workplane:
    """
    Construct the bracket solid from BracketParams.

    Steps:
      1. Base plate  — box(length × width × thickness), centred X/Y, bottom at Z=0.
      2. Vertical wall — box(thickness × width × height), flush to -X edge,
                         sitting on top of the base plate.
      3. Union the two boxes.
      4. Cut circular holes through the base plate.
      5. Cut rectangular slots through the base plate.
      6. Cut circular holes through the vertical wall.
      7. Optionally fillet the four vertical corner edges.
    """
    t = p.thickness

    # ── 1. Base plate ─────────────────────────────────────────────────────────
    base = (
        cq.Workplane("XY")
        .box(p.length, p.width, t, centered=(True, True, False))
    )

    # ── 2. Vertical wall ──────────────────────────────────────────────────────
    wall_x = -(p.length / 2 - t / 2)
    wall = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(wall_x, 0, t))
        .box(t, p.width, p.height, centered=(True, True, False))
    )

    # ── 3. Union ──────────────────────────────────────────────────────────────
    part = base.union(wall)

    # ── 4. Base-plate circular holes ──────────────────────────────────────────
    for (hx, hy, hd) in p.holes:
        cutter = (
            cq.Workplane("XY")
            .transformed(offset=cq.Vector(hx, hy, -1))
            .circle(hd / 2)
            .extrude(t + 2)
        )
        part = part.cut(cutter)

    # ── 5. Base-plate slots ───────────────────────────────────────────────────
    for (sx, sy, sl, sw) in p.slots:
        cutter = (
            cq.Workplane("XY")
            .transformed(offset=cq.Vector(sx, sy, -1))
            .rect(sl, sw)
            .extrude(t + 2)
        )
        part = part.cut(cutter)

    # ── 6. Wall holes (drilled in +X direction through the wall) ──────────────
    # Workplane "YZ": normal = +X, local-x = world-Y, local-y = world-Z.
    # workplane(offset=v) shifts origin to world x = v.
    wall_x_start = -(p.length / 2) - 1   # 1 mm before the outer wall face
    for (wy, wz, wd) in p.wall_holes:
        cutter = (
            cq.Workplane("YZ")
            .workplane(offset=wall_x_start)
            .center(wy, wz)
            .circle(wd / 2)
            .extrude(t + 2)
        )
        part = part.cut(cutter)

    # ── 7. Edge fillets on vertical corners ───────────────────────────────────
    if p.fillet_radius > 0:
        try:
            part = part.edges("|Z").fillet(p.fillet_radius)
        except Exception:
            pass  # fillet is cosmetic — skip silently if geometry is tricky

    return part
