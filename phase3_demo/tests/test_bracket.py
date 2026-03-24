"""
tests/test_bracket.py — pytest suite for the Phase 3 bracket pipeline.

Run from phase3_demo/:
    pytest tests/ -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import cadquery as cq
from generate_part import BracketParams, build_bracket, validate_params
from advanced_augment import (
    add_hole, remove_hole, resize,
    add_wall_hole, add_slot, set_fillet,
)


@pytest.fixture
def base():
    return BracketParams()


@pytest.fixture
def minimal():
    """Smallest valid bracket — no holes, no extras."""
    return BracketParams(
        length=60, width=30, height=40, thickness=3, holes=[]
    )


class TestBracketParams:
    def test_default_dimensions(self, base):
        assert base.length == 80.0
        assert base.width == 40.0
        assert base.height == 50.0
        assert base.thickness == 4.0

    def test_default_holes(self, base):
        assert len(base.holes) == 2
        xs = [h[0] for h in base.holes]
        assert -25.0 in xs and 25.0 in xs

    def test_default_no_wall_holes(self, base):
        assert base.wall_holes == []

    def test_default_no_slots(self, base):
        assert base.slots == []

    def test_default_no_fillet(self, base):
        assert base.fillet_radius == 0.0

    def test_custom_init(self):
        p = BracketParams(length=120, width=60, height=80, thickness=6)
        assert p.length == 120
        assert p.width == 60
        assert p.height == 80
        assert p.thickness == 6


class TestValidateParams:
    def test_clean_defaults(self, base):
        assert validate_params(base) == []

    def test_clean_minimal(self, minimal):
        assert validate_params(minimal) == []

    def test_zero_length(self):
        p = BracketParams(length=0)
        warns = validate_params(p)
        assert any("length" in w for w in warns)

    def test_negative_height(self):
        p = BracketParams(height=-5)
        warns = validate_params(p)
        assert any("height" in w for w in warns)

    def test_thickness_too_large_vs_length(self):
        p = BracketParams(length=10, thickness=6)
        warns = validate_params(p)
        assert any("thickness" in w for w in warns)

    def test_base_hole_outside_plate_x(self):
        p = BracketParams(holes=[(100.0, 0.0, 8.0)])
        warns = validate_params(p)
        assert any("outside plate length" in w for w in warns)

    def test_base_hole_outside_plate_y(self):
        p = BracketParams(holes=[(0.0, 30.0, 8.0)])
        warns = validate_params(p)
        assert any("outside plate width" in w for w in warns)

    def test_zero_diameter_hole(self):
        p = BracketParams(holes=[(0.0, 0.0, 0.0)])
        warns = validate_params(p)
        assert any("diameter" in w for w in warns)

    def test_slot_outside_plate(self):
        p = BracketParams(slots=[(0.0, 0.0, 200.0, 8.0)], holes=[])
        warns = validate_params(p)
        assert any("Slot" in w for w in warns)

    def test_wall_hole_above_top(self):
        p = BracketParams(wall_holes=[(0.0, 500.0, 6.0)])
        warns = validate_params(p)
        assert any("above wall top" in w for w in warns)

    def test_wall_hole_intersects_base(self):
        p = BracketParams(wall_holes=[(0.0, 1.0, 6.0)])
        warns = validate_params(p)
        assert any("base plate" in w for w in warns)

    def test_wall_hole_outside_width(self):
        p = BracketParams(wall_holes=[(100.0, 30.0, 6.0)])
        warns = validate_params(p)
        assert any("wall width" in w for w in warns)

    def test_fillet_too_large(self):
        p = BracketParams(fillet_radius=3.0, thickness=4.0)
        warns = validate_params(p)
        assert any("fillet_radius" in w for w in warns)


class TestBuildBracket:
    def test_returns_workplane(self, base):
        solid = build_bracket(base)
        assert isinstance(solid, cq.Workplane)

    def test_solid_is_not_empty(self, base):
        solid = build_bracket(base)
        assert solid.val() is not None

    def test_bbox_baseline(self, base):
        solid = build_bracket(base)
        bb = solid.val().BoundingBox()
        assert abs((bb.xmax - bb.xmin) - base.length) < 0.2
        assert abs((bb.ymax - bb.ymin) - base.width) < 0.2
        assert abs((bb.zmax - bb.zmin) - (base.thickness + base.height)) < 0.2

    def test_bbox_custom_dimensions(self):
        p = BracketParams(length=120, width=60, height=70, thickness=6, holes=[])
        solid = build_bracket(p)
        bb = solid.val().BoundingBox()
        assert abs((bb.xmax - bb.xmin) - 120) < 0.2
        assert abs((bb.ymax - bb.ymin) - 60) < 0.2
        assert abs((bb.zmax - bb.zmin) - 76) < 0.2

    def test_no_holes(self, minimal):
        solid = build_bracket(minimal)
        assert solid.val() is not None

    def test_single_hole(self):
        p = BracketParams(holes=[(0.0, 0.0, 8.0)])
        solid = build_bracket(p)
        assert solid.val() is not None

    def test_multiple_holes(self, base):
        solid = build_bracket(base)
        assert solid.val() is not None

    def test_wall_hole(self):
        p = BracketParams(wall_holes=[(0.0, 30.0, 6.0)])
        solid = build_bracket(p)
        assert solid.val() is not None

    def test_multiple_wall_holes(self):
        p = BracketParams(
            wall_holes=[(0.0, 25.0, 6.0), (10.0, 35.0, 5.0)],
        )
        solid = build_bracket(p)
        assert solid.val() is not None

    def test_slot(self):
        p = BracketParams(slots=[(0.0, 0.0, 20.0, 8.0)], holes=[])
        solid = build_bracket(p)
        assert solid.val() is not None

    def test_fillet(self):
        p = BracketParams(fillet_radius=1.5, holes=[])
        solid = build_bracket(p)
        assert solid.val() is not None

    def test_all_features_combined(self):
        p = BracketParams(
            holes=[(-20.0, 0.0, 7.0), (20.0, 0.0, 7.0)],
            wall_holes=[(0.0, 28.0, 6.0)],
            slots=[(5.0, 0.0, 18.0, 7.0)],
            fillet_radius=1.0,
        )
        solid = build_bracket(p)
        assert solid.val() is not None

    def test_wall_bbox_unchanged_by_base_holes(self):
        """Punching holes should not change the outer bounding box."""
        p_no_holes = BracketParams(holes=[])
        p_holes = BracketParams(holes=[(-25.0, 0.0, 8.0), (25.0, 0.0, 8.0)])
        bb_no = build_bracket(p_no_holes).val().BoundingBox()
        bb_h  = build_bracket(p_holes).val().BoundingBox()
        assert abs((bb_no.xmax - bb_no.xmin) - (bb_h.xmax - bb_h.xmin)) < 0.2
        assert abs((bb_no.ymax - bb_no.ymin) - (bb_h.ymax - bb_h.ymin)) < 0.2
        assert abs((bb_no.zmax - bb_no.zmin) - (bb_h.zmax - bb_h.zmin)) < 0.2


class TestAddHole:
    def test_increases_count(self, base):
        p, _ = add_hole(base, x=0.0, y=0.0)
        assert len(p.holes) == len(base.holes) + 1

    def test_uses_custom_diameter(self, base):
        p, _ = add_hole(base, x=0.0, y=0.0, diameter=12.0)
        assert p.holes[-1][2] == 12.0

    def test_uses_default_diameter(self, base):
        p, _ = add_hole(base, x=0.0, y=0.0)
        assert p.holes[-1][2] == base.hole_diameter

    def test_description_mentions_added(self, base):
        _, desc = add_hole(base, x=5.0, y=5.0)
        assert "Added" in desc

    def test_does_not_mutate_original(self, base):
        original_count = len(base.holes)
        add_hole(base, x=0.0, y=0.0)
        assert len(base.holes) == original_count


class TestRemoveHole:
    def test_decreases_count(self, base):
        p, _ = remove_hole(base)
        assert len(p.holes) == len(base.holes) - 1

    def test_remove_by_index(self, base):
        first = base.holes[0]
        p, _ = remove_hole(base, index=0)
        assert first not in p.holes

    def test_remove_from_empty(self):
        p = BracketParams(holes=[])
        result, desc = remove_hole(p)
        assert len(result.holes) == 0
        assert "No" in desc

    def test_does_not_mutate_original(self, base):
        original_count = len(base.holes)
        remove_hole(base)
        assert len(base.holes) == original_count


class TestResize:
    def test_changes_length(self, base):
        p, _ = resize(base, length=120.0)
        assert p.length == 120.0

    def test_changes_multiple(self, base):
        p, desc = resize(base, length=100.0, width=60.0, height=70.0)
        assert p.length == 100.0
        assert p.width == 60.0
        assert p.height == 70.0
        assert "length" in desc

    def test_unknown_key_ignored(self, base):
        p, desc = resize(base, totally_fake_param=999)
        assert p.length == base.length
        assert "no recognised" in desc.lower()

    def test_does_not_mutate_original(self, base):
        resize(base, length=200.0)
        assert base.length == 80.0

    def test_resized_bracket_builds(self, base):
        p, _ = resize(base, length=120.0, width=60.0, holes=[])
        solid = build_bracket(p)
        bb = solid.val().BoundingBox()
        assert abs((bb.xmax - bb.xmin) - 120) < 0.2


class TestAddWallHole:
    def test_increases_wall_hole_count(self, base):
        p, _ = add_wall_hole(base, y=0.0, z=30.0)
        assert len(p.wall_holes) == 1

    def test_default_z_is_mid_wall(self, base):
        p, _ = add_wall_hole(base, y=0.0)
        _, z_stored, _ = p.wall_holes[0]
        expected_z = base.thickness + base.height / 2
        assert abs(z_stored - expected_z) < 0.1

    def test_custom_diameter(self, base):
        p, _ = add_wall_hole(base, diameter=10.0)
        assert p.wall_holes[0][2] == 10.0

    def test_description_mentions_wall(self, base):
        _, desc = add_wall_hole(base)
        assert "wall" in desc.lower()

    def test_does_not_mutate_original(self, base):
        add_wall_hole(base)
        assert base.wall_holes == []


class TestAddSlot:
    def test_increases_slot_count(self, base):
        p, _ = add_slot(base)
        assert len(p.slots) == 1

    def test_stores_correct_dimensions(self, base):
        p, _ = add_slot(base, x=5.0, y=-5.0, slot_length=24.0, slot_width=9.0)
        assert p.slots[0] == (5.0, -5.0, 24.0, 9.0)

    def test_default_slot_width(self, base):
        p, _ = add_slot(base)
        assert p.slots[0][3] == base.hole_diameter

    def test_description_mentions_slot(self, base):
        _, desc = add_slot(base)
        assert "slot" in desc.lower()

    def test_does_not_mutate_original(self, base):
        add_slot(base)
        assert base.slots == []


class TestSetFillet:
    def test_sets_radius(self, base):
        p, _ = set_fillet(base, radius=2.0)
        assert p.fillet_radius == 2.0

    def test_zero_disables_fillet(self, base):
        p, _ = set_fillet(base, radius=0.0)
        assert p.fillet_radius == 0.0

    def test_description_mentions_fillet(self, base):
        _, desc = set_fillet(base, radius=1.5)
        assert "fillet" in desc.lower()

    def test_does_not_mutate_original(self, base):
        set_fillet(base, radius=3.0)
        assert base.fillet_radius == 0.0


class TestImmutability:
    def test_all_augmentations_leave_base_unchanged(self, base):
        original_holes = list(base.holes)
        original_wall_holes = list(base.wall_holes)
        original_slots = list(base.slots)
        original_length = base.length
        original_fillet = base.fillet_radius

        add_hole(base, 10, 10)
        remove_hole(base)
        resize(base, length=200, width=80)
        add_wall_hole(base, y=5, z=30)
        add_slot(base, x=5, y=5, slot_length=20)
        set_fillet(base, radius=3.0)

        assert list(base.holes) == original_holes
        assert list(base.wall_holes) == original_wall_holes
        assert list(base.slots) == original_slots
        assert base.length == original_length
        assert base.fillet_radius == original_fillet


class TestRoundTrip:
    """Build each augmentation variant end-to-end."""

    def _assert_solid(self, params: BracketParams):
        solid = build_bracket(params)
        assert solid.val() is not None, f"build_bracket returned empty solid for {params}"

    def test_baseline(self, base):
        self._assert_solid(base)

    def test_add_hole(self, base):
        p, _ = add_hole(base, x=0.0, y=0.0)
        self._assert_solid(p)

    def test_remove_hole(self, base):
        p, _ = remove_hole(base)
        self._assert_solid(p)

    def test_resize(self, base):
        p, _ = resize(base, length=120.0, width=60.0, holes=[])
        self._assert_solid(p)

    def test_wall_hole(self, base):
        p, _ = add_wall_hole(base, y=0.0, z=30.0)
        self._assert_solid(p)

    def test_slot(self, base):
        p, _ = add_slot(base, x=0.0, y=0.0, slot_length=20.0)
        self._assert_solid(p)

    def test_fillet(self, base):
        p, _ = set_fillet(base, radius=1.5)
        self._assert_solid(p)

    def test_chained_augmentations(self, base):
        p, _ = add_hole(base, x=0.0, y=0.0)
        p, _ = add_wall_hole(p, y=5.0, z=28.0)
        p, _ = add_slot(p, x=10.0, y=0.0, slot_length=18.0)
        p, _ = set_fillet(p, radius=1.0)
        self._assert_solid(p)
