"""STL-source augmentation pipeline (numpy+struct): same transforms as step_augment.py."""

import argparse, json, struct, time
from pathlib import Path
import numpy as np

ROOT       = Path(__file__).resolve().parent
INPUT_DIR  = ROOT / "inputs"
OUTPUT_DIR = ROOT / "outputs"
STL_DIR    = OUTPUT_DIR / "stl"
LINEAGE    = OUTPUT_DIR / "lineage.jsonl"
SUMMARY    = OUTPUT_DIR / "summary.json"
PROTECTED_LIST_PATH = ROOT / "protected_no_upscale.json"

PROP_SCALES        = [0.7, 0.85, 1.15, 1.3]
LARGE_PROP_SCALES  = [2.0, 4.0, 6.0, 8.0, 10.0]
UPSCALE_THRESHOLD  = 300.0
UPSCALE_MAX_OUTPUT_MM = 2000.0
NONPROP_SCALES = [(1.2,0.9,1.0), (0.9,1.2,1.0), (1.0,1.0,1.3), (1.1,1.1,0.8)]
ROTATIONS = [("rot_x_90","x",90),("rot_y_90","y",90),("rot_z_45","z",45),
             ("rot_z_90","z",90),("rot_z_135","z",135)]
MIRRORS = ["x", "y", "z"]
BBOX_MIN, BBOX_MAX = 30.0, 3000.0


def load_protected():
    if not PROTECTED_LIST_PATH.exists(): return set()
    return {x["stem"].lower() for x in json.loads(PROTECTED_LIST_PATH.read_text())}
PROTECTED_STEMS = load_protected()


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
            return verts, head, "binary"
    verts = []
    with open(path, "r") as f:
        tri = []
        for line in f:
            s = line.strip()
            if s.startswith("vertex"):
                parts = s.split()
                tri.append([float(parts[1]), float(parts[2]), float(parts[3])])
                if len(tri) == 3: verts.append(tri); tri = []
    return np.array(verts, dtype=np.float32), b"ASCII".ljust(80, b"\0"), "ascii"


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
    mn = flat.min(axis=0); mx = flat.max(axis=0)
    return [round(float(mx[i]-mn[i]),3) for i in range(3)]
def bbox_in_spec(e): return min(e) >= BBOX_MIN and max(e) <= BBOX_MAX
def scale_uniform(v, f): return v * f
def scale_nonuniform(v, sx, sy, sz): return v * np.array([sx,sy,sz], dtype=np.float32)
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


def build_variants(src_bb=None, is_protected=False):
    vs = []
    for f in PROP_SCALES:
        vs.append((f"prop_{f}x", lambda vv, f=f: scale_uniform(vv, f),
                   {"transform":"scale_proportional","factor":f,"scaling_tier":"standard"}))
    if (not is_protected) and src_bb is not None and min(src_bb) < UPSCALE_THRESHOLD:
        m = max(src_bb)
        for f in LARGE_PROP_SCALES:
            if m * f > UPSCALE_MAX_OUTPUT_MM: continue
            vs.append((f"prop_large_{f}x", lambda vv, f=f: scale_uniform(vv, f),
                       {"transform":"scale_proportional","factor":f,"scaling_tier":"large"}))
    for sx, sy, sz in NONPROP_SCALES:
        vs.append((f"nonprop_x{sx}_y{sy}_z{sz}",
                   lambda vv, sx=sx,sy=sy,sz=sz: scale_nonuniform(vv,sx,sy,sz),
                   {"transform":"scale_non_proportional","sx":sx,"sy":sy,"sz":sz}))
    for name, axis, deg in ROTATIONS:
        vs.append((name, lambda vv, a=axis, d=deg: rotate(vv, a, d),
                   {"transform":"rotate","axis":axis,"degrees":deg}))
    for ax in MIRRORS:
        vs.append((f"mirror_{ax}", lambda vv, a=ax: mirror(vv, a),
                   {"transform":"mirror","axis":ax}))
    return vs


def process_part(stl_path):
    rel = stl_path.relative_to(INPUT_DIR)
    cat = rel.parts[0] if len(rel.parts) > 1 else "uncategorized"
    base = stl_path.stem
    out_dir = STL_DIR / cat
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        verts, header, fmt = read_stl(stl_path)
        if len(verts) == 0: raise ValueError("empty")
    except Exception as e:
        return [{"source":str(rel),"status":"load_error","error":str(e)[:200]}]
    src_bb = bbox(verts)
    is_prot = base.lower() in PROTECTED_STEMS
    for vname, fn, params in build_variants(src_bb=src_bb, is_protected=is_prot):
        rec = {"source":str(rel),"category":cat,"variant":vname,"params":params,
               "src_bbox":src_bb,"is_protected":is_prot,"src_triangles":len(verts)}
        try:
            new_v = fn(verts); ext = bbox(new_v)
            rec["out_bbox"] = ext; rec["bbox_ok"] = bbox_in_spec(ext)
            out_path = out_dir / f"{base}__{vname}.stl"
            write_stl_binary(out_path, new_v, header)
            rec["output_stl"] = str(out_path.relative_to(STL_DIR))
            rec["status"] = "ok"
        except Exception as e:
            rec["status"] = "transform_error"; rec["error"] = str(e)[:200]
        records.append(rec)
    return records


def main():
    global INPUT_DIR, OUTPUT_DIR, STL_DIR, LINEAGE, SUMMARY
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir",  default=None)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.input_dir:  INPUT_DIR  = Path(args.input_dir).resolve()
    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir).resolve()
        STL_DIR  = OUTPUT_DIR/"stl"
        LINEAGE  = OUTPUT_DIR/"lineage.jsonl"
        SUMMARY  = OUTPUT_DIR/"summary.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STL_DIR.mkdir(parents=True, exist_ok=True)
    parts = sorted(INPUT_DIR.glob("*/*.stl")) + sorted(INPUT_DIR.glob("*/*.STL"))
    if args.limit: parts = parts[:args.limit]
    print(f"Processing {len(parts)} STL files from {INPUT_DIR}")
    print(f"Protected stems: {len(PROTECTED_STEMS)}")
    t0 = time.time(); all_recs = []; n_ok = n_err = 0
    for i, p in enumerate(parts, 1):
        recs = process_part(p)
        all_recs.extend(recs)
        ok = sum(1 for r in recs if r.get("status")=="ok")
        err = sum(1 for r in recs if r.get("status") in ("transform_error","load_error"))
        n_ok += ok; n_err += err
        if i % 10 == 0 or err > 0:
            print(f"  [{i:3d}/{len(parts)}] {p.stem[:50]:50s} → {ok}/{len(recs)} ok" + (f"  ({err} errs)" if err else ""))
    with open(LINEAGE,"w") as f:
        for r in all_recs: f.write(json.dumps(r, default=str) + "\n")
    summary = {"parts":len(parts),"variants_ok":n_ok,"variants_err":n_err,"elapsed_sec":round(time.time()-t0,1)}
    Path(SUMMARY).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__": main()
