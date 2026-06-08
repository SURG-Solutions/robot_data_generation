"""STL augmentation for validated, already-scaled sources: 5 rot + 3 mirror + z_stretch + z_shrink."""

import argparse, struct, shutil, time
from pathlib import Path
import numpy as np

ENVELOPE_MAX = 1000.0
ENVELOPE_MID = 500.0
Z_STRETCH    = 1.3
Z_SHRINK     = 0.8

ROTATIONS = [("rot_x_90","x",90), ("rot_y_90","y",90),
             ("rot_z_90","z",90), ("rot_z_180","z",180), ("rot_z_270","z",270)]
MIRRORS = ["x", "y", "z"]


def read_stl(path):
    with open(path, "rb") as f:
        head = f.read(80)
        try: n = struct.unpack("<I", f.read(4))[0]
        except: n = 0
        size = path.stat().st_size
        if size == 80 + 4 + n*50 and n > 0:
            data = f.read(n*50)
            arr = np.frombuffer(data, dtype=np.uint8).reshape(n, 50)
            verts = arr[:, 12:48].copy().view(np.float32).reshape(n, 3, 3)
            return verts, head
    verts = []
    with open(path, "r", errors="ignore") as f:
        tri = []
        for line in f:
            s = line.strip()
            if s.startswith("vertex"):
                p = s.split()
                tri.append([float(p[1]), float(p[2]), float(p[3])])
                if len(tri) == 3: verts.append(tri); tri = []
    return np.array(verts, dtype=np.float32), b"\0"*80


def write_stl_binary(path, v, header=b"\0"*80):
    v = v.astype(np.float32)
    e1 = v[:,1]-v[:,0]; e2 = v[:,2]-v[:,0]
    n = np.cross(e1, e2)
    norms = np.linalg.norm(n, axis=1, keepdims=True); norms[norms==0] = 1
    n = (n / norms).astype(np.float32)
    with open(path, "wb") as f:
        f.write(header); f.write(struct.pack("<I", len(v)))
        for i in range(len(v)):
            f.write(n[i].tobytes()); f.write(v[i].tobytes()); f.write(b"\0\0")


def bbox(v):
    flat = v.reshape(-1, 3)
    return [float(flat[:,i].max()-flat[:,i].min()) for i in range(3)]


def rotate(v, axis, deg):
    r = np.deg2rad(deg); c, s = np.cos(r), np.sin(r)
    if axis == "x":   m = np.array([[1,0,0],[0,c,-s],[0,s,c]], dtype=np.float32)
    elif axis == "y": m = np.array([[c,0,s],[0,1,0],[-s,0,c]], dtype=np.float32)
    else:             m = np.array([[c,-s,0],[s,c,0],[0,0,1]], dtype=np.float32)
    return v @ m.T


def mirror(v, axis):
    flip = np.ones(3, dtype=np.float32)
    flip[{"x":0,"y":1,"z":2}[axis]] = -1.0
    out = v * flip
    out = out[:, [0, 2, 1], :]
    return out


def scale_z(v, factor):
    return v * np.array([1.0, 1.0, factor], dtype=np.float32)


def within_envelope(v):
    dims = sorted(bbox(v))
    return dims[-1] <= ENVELOPE_MAX + 1 and dims[-2] <= ENVELOPE_MID + 1


def process(name, src_path, out_root):
    v, header = read_stl(src_path)
    if len(v) == 0:
        return {"name": name, "status": "empty_source"}

    rec = {"name": name, "ops": {}}

    shutil.copy2(src_path, out_root / "original_scaled" / f"{name}.stl")
    rec["ops"]["original_scaled"] = "ok"

    for vname, axis, deg in ROTATIONS:
        write_stl_binary(out_root / "rotation" / f"{name}__{vname}.stl",
                         rotate(v, axis, deg), header)
        rec["ops"][vname] = "ok"

    for ax in MIRRORS:
        write_stl_binary(out_root / "mirror" / f"{name}__mirror_{ax}.stl",
                         mirror(v, ax), header)
        rec["ops"][f"mirror_{ax}"] = "ok"

    write_stl_binary(out_root / "z_shrink" / f"{name}.stl",
                     scale_z(v, Z_SHRINK), header)
    rec["ops"]["z_shrink"] = "ok"

    v_stretch = scale_z(v, Z_STRETCH)
    if within_envelope(v_stretch):
        write_stl_binary(out_root / "z_stretch" / f"{name}.stl", v_stretch, header)
        rec["ops"]["z_stretch"] = "ok"
    else:
        rec["ops"]["z_stretch"] = "skipped_envelope"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scaled-dir",   required=True, help="folder of envelope-scaled STLs")
    ap.add_argument("--original-dir", required=True, help="fallback folder for sources already ≥ envelope")
    ap.add_argument("--names-file",   required=True, help="file with one source stem per line")
    ap.add_argument("--output-dir",   required=True)
    args = ap.parse_args()

    scaled_dir   = Path(args.scaled_dir).resolve()
    original_dir = Path(args.original_dir).resolve()
    out_root     = Path(args.output_dir).resolve()

    for sub in ("original_scaled", "rotation", "mirror", "z_stretch", "z_shrink"):
        (out_root / sub).mkdir(parents=True, exist_ok=True)

    names = [l.strip() for l in open(args.names_file) if l.strip()]
    print(f"Sources: {len(names)}")
    t0 = time.time()

    n_ok = n_miss = n_z_skip = 0
    for name in names:
        src = scaled_dir / f"{name}.stl"
        if not src.exists(): src = original_dir / f"{name}.stl"
        if not src.exists():
            n_miss += 1
            print(f"  MISSING: {name}")
            continue
        rec = process(name, src, out_root)
        n_ok += 1
        if rec["ops"].get("z_stretch") == "skipped_envelope":
            n_z_skip += 1

    elapsed = time.time() - t0
    print(f"\nSources processed: {n_ok}")
    print(f"Missing          : {n_miss}")
    print(f"z_stretch skipped (envelope-unsafe): {n_z_skip}")
    print(f"Elapsed: {elapsed:.1f}s")

    print("\nOutput counts:")
    total = 0
    for sub in ("original_scaled","rotation","mirror","z_stretch","z_shrink"):
        c = sum(1 for _ in (out_root/sub).glob("*.stl"))
        total += c
        print(f"  {sub:16s}: {c}")
    print(f"  TOTAL           : {total}")


if __name__ == "__main__":
    main()
