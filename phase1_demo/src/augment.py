"""Augmentation transforms for trimesh meshes."""

import numpy as np
import trimesh


def scale_proportional(mesh: trimesh.Trimesh, factor: float) -> trimesh.Trimesh:
    """Uniform scale by a single factor."""
    m = mesh.copy()
    m.apply_scale(factor)
    return m


def scale_non_proportional(
    mesh: trimesh.Trimesh, sx: float, sy: float, sz: float
) -> trimesh.Trimesh:
    """Non-uniform scale along each axis."""
    m = mesh.copy()
    matrix = np.diag([sx, sy, sz, 1.0])
    m.apply_transform(matrix)
    return m


def rotate_z(mesh: trimesh.Trimesh, degrees: float) -> trimesh.Trimesh:
    """Rotate around the Z-axis by the given degrees."""
    m = mesh.copy()
    radians = np.deg2rad(degrees)
    rot = trimesh.transformations.rotation_matrix(radians, [0, 0, 1])
    m.apply_transform(rot)
    return m
