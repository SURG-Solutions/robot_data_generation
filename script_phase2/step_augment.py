"""STEP-source augmentation pipeline (CadQuery): proportional/non-prop scale, rotate, mirror."""

import argparse, json, time
from pathlib import Path

import cadquery as cq
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_GTrsf, gp_Mat
from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform, BRepBuilderAPI_Transform

ROOT       = Path(__file__).resolve().parent
INPUT_DIR  = ROOT / "inputs"
OUTPUT_DIR = ROOT / "outputs"
STL_DIR    = OUTPUT_DIR / "stl"
STEP_DIR   = OUTPUT_DIR / "step"
LINEAGE    = OUTPUT_DIR / "lineage.jsonl"
SUMMARY    = OUTPUT_DIR / "summary.json"
PROTECTED_LIST_PATH = ROOT / "protected_no_upscale.json"

STL_TOLERANCE         = 0.5
STL_ANGULAR_TOL       = 1.0
PROP_SCALES           = [0.7, 0.85, 1.15, 1.3]
LARGE_PROP_SCALES     = [2.0, 4.0, 6.0, 8.0, 10.0]
UPSCALE_THRESHOLD     = 300.0
UPSCALE_MAX_OUTPUT_MM = 2000.0
BBOX_MIN, BBOX_MAX    = 30.0, 3000.0

NONPROP_SCALES = [(1.2, 0.9, 1.0), (0.9, 1.2, 1.0),
                  (1.0, 1.0, 1.3), (1.1, 1.1, 0.8)]
ROTATIONS = [("rot_x_90", (1,0,0), 90), ("rot_y_90", (0,1,0), 90),
             ("rot_z_45", (0,0,1), 45), ("rot_z_90", (0,0,1), 90),
             ("rot_z_135", (0,0,1), 135)]
MIRRORS = ["x", "y", "z"]


def load_protected():
    if not PROTECTED_LIST_PATH.exists(): return set()
    return {x["stem"].lower() for x in json.loads(PROTECTED_LIST_PATH.read_text())}
PROTECTED_STEMS = load_protected()


def shape_bbox(s):
    bb = s.BoundingBox()
    return [round(bb.xmax-bb.xmin, 3), round(bb.ymax-bb.ymin, 3), round(bb.zmax-bb.zmin, 3)]

def scale_uniform(s, f): return s.scale(f)
def scale_nonuniform(s, sx, sy, sz):
    g = gp_GTrsf(); g.SetVectorialPart(gp_Mat(sx,0,0, 0,sy,0, 0,0,sz))
    return cq.Shape.cast(BRepBuilderAPI_GTransform(s.wrapped, g, True).Shape())
def rotate(s, a, d): return s.rotate((0,0,0), a, d)
def mirror(s, axis):
    plane = {"x":(1,0,0),"y":(0,1,0),"z":(0,0,1)}[axis]
    t = gp_Trsf(); t.SetMirror(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(*plane)))
    return cq.Shape.cast(BRepBuilderAPI_Transform(s.wrapped, t, True).Shape())
def bbox_in_spec(e): return min(e) >= BBOX_MIN and max(e) <= BBOX_MAX


def build_variants(src_bb=None, is_protected=False):
    v = []
    for f in PROP_SCALES:
        v.append((f"prop_{f}x", lambda s, f=f: scale_uniform(s, f),
                  {"transform":"scale_proportional","factor":f,"scaling_tier":"standard"}))
    if (not is_protected) and src_bb is not None and min(src_bb) < UPSCALE_THRESHOLD:
        m = max(src_bb)
        for f in LARGE_PROP_SCALES:
            if m * f > UPSCALE_MAX_OUTPUT_MM: continue
            v.append((f"prop_large_{f}x", lambda s, f=f: scale_uniform(s, f),
                      {"transform":"scale_proportional","factor":f,"scaling_tier":"large"}))
    for sx, sy, sz in NONPROP_SCALES:
        v.append((f"nonprop_x{sx}_y{sy}_z{sz}",
                  lambda s, sx=sx, sy=sy, sz=sz: scale_nonuniform(s, sx, sy, sz),
                  {"transform":"scale_non_proportional","sx":sx,"sy":sy,"sz":sz}))
    for n, axis, deg in ROTATIONS:
        v.append((n, lambda s, a=axis, d=deg: rotate(s, a, d),
                  {"transform":"rotate","axis":axis,"degrees":deg}))
    for ax in MIRRORS:
        v.append((f"mirror_{ax}", lambda s, a=ax: mirror(s, a),
                  {"transform":"mirror","axis":ax}))
    return v


def process_part(step_path, out_root):
    rel = step_path.relative_to(INPUT_DIR)
    category = rel.parts[0] if len(rel.parts) > 1 else "uncategorized"
    base = step_path.stem
    out_dir = out_root / category
    step_out_dir = STEP_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    step_out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    try: solid = cq.importers.importStep(str(step_path)).val()
    except Exception as e: return [{"source":str(rel),"status":"import_error","error":str(e)[:200]}]
    src_bb = shape_bbox(solid)
    if min(src_bb) < 0.5 or max(src_bb) > 50000:
        return [{"source":str(rel),"status":"source_bbox_unreasonable","src_bbox":src_bb}]
    is_prot = base.lower() in PROTECTED_STEMS
    for vname, fn, params in build_variants(src_bb=src_bb, is_protected=is_prot):
        rec = {"source":str(rel),"category":category,"variant":vname,"params":params,
               "src_bbox":src_bb,"is_protected":is_prot}
        try:
            t = fn(solid); ext = shape_bbox(t)
            rec["out_bbox"] = ext; rec["bbox_ok"] = bbox_in_spec(ext)
            wp = cq.Workplane().add(t)
            stl_p  = out_dir / f"{base}__{vname}.stl"
            step_p = step_out_dir / f"{base}__{vname}.step"
            cq.exporters.export(wp, str(stl_p),  tolerance=STL_TOLERANCE, angularTolerance=STL_ANGULAR_TOL)
            cq.exporters.export(wp, str(step_p), exportType="STEP")
            rec["output_stl"]  = str(stl_p.relative_to(out_root))
            rec["output_step"] = str(step_p.relative_to(STEP_DIR))
            rec["status"] = "ok"
        except Exception as e:
            rec["status"] = "transform_error"; rec["error"] = str(e)[:200]
        records.append(rec)
    return records


def main():
    global INPUT_DIR, OUTPUT_DIR, STL_DIR, STEP_DIR, LINEAGE, SUMMARY
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir",  default=None)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.input_dir:  INPUT_DIR  = Path(args.input_dir).resolve()
    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir).resolve()
        STL_DIR  = OUTPUT_DIR/"stl"; STEP_DIR = OUTPUT_DIR/"step"
        LINEAGE  = OUTPUT_DIR/"lineage.jsonl"; SUMMARY = OUTPUT_DIR/"summary.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STL_DIR.mkdir(parents=True, exist_ok=True); STEP_DIR.mkdir(parents=True, exist_ok=True)
    parts = sorted(INPUT_DIR.glob("*/*.step")) + sorted(INPUT_DIR.glob("*/*.stp"))
    if args.limit: parts = parts[:args.limit]
    print(f"Processing {len(parts)} STEP files from {INPUT_DIR}")
    print(f"Protected stems: {len(PROTECTED_STEMS)}")
    t0 = time.time(); all_recs = []; n_ok = n_err = 0
    for i, p in enumerate(parts, 1):
        recs = process_part(p, STL_DIR)
        all_recs.extend(recs)
        ok = sum(1 for r in recs if r.get("status")=="ok")
        err = sum(1 for r in recs if r.get("status") in ("transform_error","import_error"))
        n_ok += ok; n_err += err
        if i % 10 == 0 or err > 0:
            print(f"  [{i:3d}/{len(parts)}] {p.stem[:50]:50s} → {ok}/{len(recs)} ok" + (f"  ({err} errs)" if err else ""))
    elapsed = time.time()-t0
    with open(LINEAGE,"w") as f:
        for r in all_recs: f.write(json.dumps(r, default=str) + "\n")
    summary = {"input_dir":str(INPUT_DIR), "output_dir":str(OUTPUT_DIR),
               "parts":len(parts), "variants_ok":n_ok, "variants_err":n_err,
               "elapsed_sec":round(elapsed,1)}
    Path(SUMMARY).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__": main()
