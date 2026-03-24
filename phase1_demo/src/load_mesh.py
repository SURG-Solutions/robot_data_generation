"""Load and inspect an STL mesh."""

import trimesh
import numpy as np


def load_mesh(path: str) -> trimesh.Trimesh:
    mesh = trimesh.load_mesh(path)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.dump())
    return mesh


def bounding_box(mesh: trimesh.Trimesh) -> dict:
    extents = mesh.bounding_box.extents
    return {
        "x": float(extents[0]),
        "y": float(extents[1]),
        "z": float(extents[2]),
    }
