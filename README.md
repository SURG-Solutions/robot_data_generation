
# RoboTwin 

## About the Project

**Client:** RoboTwin (Prague) — building an ML model on 3D data for manufacturing / paint shop automation.

**Domain:** Industrial metal-sheet parts — machine components, car parts, welded/bent/laser-cut pieces. Each part has a unique, irregular shape, but parts cluster into families of similar geometries.

**The Problem:** RoboTwin has limited real-world industrial data. They need hundreds to thousands of 3D models (.stl) to train their ML pipeline. Only the object geometry matters — background, scene, and lighting are irrelevant.

**What We Deliver:**
1. Cleaned, validated source parts sourced from public CAD libraries
2. Augmented variants of those parts (thousands of .stl files)
3. A reusable Python pipeline the client can run, maintain, and extend independently

---

## Project Phases

### Phase 1 — Data Sourcing Pipeline
Scrape, download, convert, and validate CAD models from public sources.

- **Sources:** GrabCAD, ShapeNet, ABC Dataset, Fusion 360 Gallery, Mechanical Components Benchmark
- **Output format:** `.stl` (triangle mesh)
- **Validation criteria:**
  - Watertight mesh (no holes in surface)
  - Correct outward-facing normals
  - Real-world scale (millimeters)
  - Bounding box: min dimension > 30 mm, max dimension < 3000 mm
- **Deliverable:** ~100 parts (first batch for client feedback) → scale to 300–500 cleaned parts

### Phase 2 — Basic Augmentation
Generate augmented variants from source parts using geometric transformations.

- **Proportional scaling** — uniform 0.5x–1.5x with bounding box constraints
- **Disproportional scaling** — independent stretch per x/y/z axis
- **Rotation** — around principal axes (configurable)
- **Mirroring** — along x/y/z axes
- **Batch processing** — each source part → N variants based on a parameter matrix
- **Deliverable:** augmented dataset (thousands of parts) + pipeline script

### Phase 3 — Advanced Augmentation *(planned)*
- Boolean operations — programmatic addition/removal of geometric features (holes, cuts, extrusions)
- Assembly manipulation — adding/removing sub-components of multi-part objects
- Approach calibrated based on mesh quality learnings from Phases 1 & 2
