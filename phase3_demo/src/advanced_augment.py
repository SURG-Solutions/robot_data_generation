"""
advanced_augment.py — Parametric geometry edits on a CadQuery bracket.

Each function takes a BracketParams, returns (modified_params, description).
The caller re-builds the solid from the new params so every variant is
generated from a clean parametric model — no boolean hacks on existing solids.

Available transforms
────────────────────
  add_hole        add a circular hole to the base plate
  remove_hole     remove a hole from the base plate by index
  resize          change any scalar dimension (length/width/height/thickness)
  add_wall_hole   add a hole on the vertical wall face
  add_slot        add a rectangular slot on the base plate
  set_fillet      set the vertical corner fillet radius
"""

from copy import deepcopy
from typing import Optional, Tuple
from generate_part import BracketParams


# ── Base-plate holes ──────────────────────────────────────────────────────────

def add_hole(
    params: BracketParams,
    x: float = 0.0,
    y: float = 0.0,
    diameter: Optional[float] = None,
) -> Tuple[BracketParams, str]:
    """Add one circular hole to the base plate."""
    p = deepcopy(params)
    d = diameter if diameter is not None else p.hole_diameter
    p.holes = list(p.holes) + [(x, y, d)]
    desc = (
        f"Added base hole ⌀{d:.1f} mm at ({x:+.1f}, {y:+.1f}) — "
        f"total base holes: {len(p.holes)}"
    )
    return p, desc


def remove_hole(
    params: BracketParams,
    index: int = -1,
) -> Tuple[BracketParams, str]:
    """Remove one hole from the base plate by list index (default: last)."""
    p = deepcopy(params)
    if not p.holes:
        return p, "No base holes to remove — unchanged"
    idx = index % len(p.holes)
    removed = p.holes[idx]
    p.holes = [h for i, h in enumerate(p.holes) if i != idx]
    desc = (
        f"Removed base hole ⌀{removed[2]:.1f} mm at "
        f"({removed[0]:+.1f}, {removed[1]:+.1f}) — "
        f"remaining: {len(p.holes)}"
    )
    return p, desc


# ── Dimensional resize ────────────────────────────────────────────────────────

def resize(
    params: BracketParams,
    **kwargs,
) -> Tuple[BracketParams, str]:
    """
    Change any scalar field on BracketParams.
    Unknown keys are silently ignored.

    Example:
        resize(p, length=100, thickness=6)
    """
    p = deepcopy(params)
    changes = []
    for key, val in kwargs.items():
        if hasattr(p, key) and not callable(getattr(p, key)):
            old = getattr(p, key)
            setattr(p, key, val)
            changes.append(f"{key}: {old} → {val}")
    desc = ("Resized — " + ", ".join(changes)) if changes else "Resize: no recognised fields changed"
    return p, desc


# ── Wall holes ────────────────────────────────────────────────────────────────

def add_wall_hole(
    params: BracketParams,
    y: float = 0.0,
    z: Optional[float] = None,
    diameter: Optional[float] = None,
) -> Tuple[BracketParams, str]:
    """
    Add a circular hole on the vertical wall face.

    y       — lateral offset from wall centre (world Y)
    z       — height from ground; defaults to mid-wall
    diameter — hole ⌀; defaults to params.hole_diameter
    """
    p = deepcopy(params)
    d = diameter if diameter is not None else p.hole_diameter
    z_val = z if z is not None else p.thickness + p.height / 2
    p.wall_holes = list(p.wall_holes) + [(y, z_val, d)]
    desc = (
        f"Added wall hole ⌀{d:.1f} mm at (y={y:+.1f}, z={z_val:.1f}) — "
        f"total wall holes: {len(p.wall_holes)}"
    )
    return p, desc


# ── Slots ─────────────────────────────────────────────────────────────────────

def add_slot(
    params: BracketParams,
    x: float = 0.0,
    y: float = 0.0,
    slot_length: float = 20.0,
    slot_width: Optional[float] = None,
) -> Tuple[BracketParams, str]:
    """
    Add a rectangular slot through the base plate.

    slot_length — long dimension (along X by default)
    slot_width  — short dimension; defaults to params.hole_diameter
    """
    p = deepcopy(params)
    sw = slot_width if slot_width is not None else p.hole_diameter
    p.slots = list(p.slots) + [(x, y, slot_length, sw)]
    desc = (
        f"Added slot {slot_length:.1f}×{sw:.1f} mm at ({x:+.1f}, {y:+.1f}) on base plate — "
        f"total slots: {len(p.slots)}"
    )
    return p, desc


# ── Fillets ───────────────────────────────────────────────────────────────────

def set_fillet(
    params: BracketParams,
    radius: float,
) -> Tuple[BracketParams, str]:
    """Set the fillet radius on vertical corner edges (0 = off)."""
    p = deepcopy(params)
    p.fillet_radius = radius
    desc = f"Set vertical corner fillet radius to {radius:.1f} mm"
    return p, desc
