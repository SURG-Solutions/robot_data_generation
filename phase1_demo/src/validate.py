"""Validate mesh properties."""

import trimesh


def is_watertight(mesh: trimesh.Trimesh) -> bool:
    return mesh.is_watertight


def mesh_report(mesh: trimesh.Trimesh) -> dict:
    return {
        "watertight": is_watertight(mesh),
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "volume": float(mesh.volume) if mesh.is_watertight else None,
    }
