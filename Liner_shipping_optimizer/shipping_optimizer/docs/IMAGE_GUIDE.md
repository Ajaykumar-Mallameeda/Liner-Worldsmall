# Image Guide

This document specifies where every image belongs, what it should be named, and where it appears.

---

## Dashboard Screenshots

| Expected Filename | Resolution | Aspect | Appears In | Source Tab |
|---|---|---|---|---|
| `landing-dashboard.png` | 1920×1080 | 16:9 | docs/, Release | Landing |
| `overview-dashboard.png` | 1920×1080 | 16:9 | README, Gallery, Release | Overview |
| `fleet-explorer.png` | 1920×1080 | 16:9 | README, Gallery | Fleet Explorer |
| `route-explorer.png` | 1920×1080 | 16:9 | README, Gallery | Route Explorer |
| `port-intelligence.png` | 1920×1080 | 16:9 | Gallery | Port Intelligence |
| `pipeline-visualization.png` | 1920×1080 | 16:9 | README, Gallery | Pipeline |
| `regional-agents.png` | 1920×1080 | 16:9 | README, Gallery | Regional |
| `ga-milp-analytics.png` | 1920×1080 | 16:9 | README, Gallery | Funnel |
| `feedback-loop.png` | 1920×1080 | 16:9 | Gallery | Feedback |
| `conflict-resolution.png` | 1920×1080 | 16:9 | Gallery | Conflict |
| `maritime-map.png` | 1920×1080 | 16:9 | README, Gallery | Map |
| `scenario-workspace.png` | 1920×1080 | 16:9 | Gallery | Scenarios |
| `export-center.png` | 1920×1080 | 16:9 | Gallery | Export |
| `executive-summary.png` | 1920×1080 | 16:9 | README, Gallery, Release | Summary |

**Target directory:** `assets/dashboard/`
**Format:** PNG (lossless)
**Compression:** PNG optimizers (pngcrush, optipng)
**Note:** Take screenshots at 1920×1080 in Chrome DevTools with "Capture full-size screenshot"

---

## Architecture Diagrams

| Expected Filename | Resolution | Aspect | Appears In |
|---|---|---|---|
| `system-architecture.png` | 1600×900 | 16:9 | README, docs/ |
| `optimization-pipeline.png` | 1600×900 | 16:9 | README |
| `multi-agent-architecture.png` | 1600×900 | 16:9 | README |
| `runtime-data-flow.png` | 1200×675 | 16:9 | README, docs/ |

**Target directory:** `assets/architecture/`
**Format:** SVG preferred (scalable), PNG fallback
**Recommended tool:** draw.io, Excalidraw, or Mermaid → SVG export

---

## Benchmark Visualizations

| Expected Filename | Resolution | Aspect | Appears In |
|---|---|---|---|
| `benchmark-summary.png` | 1200×675 | 16:9 | README |
| `runtime-metrics.png` | 1200×675 | 16:9 | docs/ |

**Target directory:** `assets/benchmarks/`
**Format:** PNG or SVG
**Source:** Data from `docs/BENCHMARKS.md`

---

## Runtime Truth Diagrams

| Expected Filename | Resolution | Aspect | Appears In |
|---|---|---|---|
| `runtime-truth.png` | 1200×500 | 2.4:1 | README |
| `pipeline-output.png` | 1200×800 | 3:2 | docs/ |

**Target directory:** `assets/runtime/`
**Format:** SVG preferred

---

## Demo Assets

| Expected Filename | Resolution | Duration | Appears In |
|---|---|---|---|
| `demo.gif` | 960×540 | 15-30s | README, Release |
| `demo.mp4` | 1920×1080 | 30-60s | Release (optional) |

**Target directory:** `assets/demo/`
**Format:** GIF (≤5MB) or H.264 MP4 (≤10MB)
**Content:** Dashboard auto-cycling through tabs in presentation mode

---

## README Image Placement

The README uses images in this order:

1. `assets/dashboard/overview-dashboard.png` — Hero image under Executive Summary
2. `assets/dashboard/fleet-explorer.png` — Gallery row 1, column 2
3. `assets/dashboard/route-explorer.png` — Gallery row 2, column 1
4. `assets/dashboard/regional-agents.png` — Gallery row 2, column 2
5. `assets/dashboard/pipeline-visualization.png` — Gallery row 3, column 1
6. `assets/dashboard/ga-milp-analytics.png` — Gallery row 3, column 2
7. `assets/dashboard/maritime-map.png` — Gallery row 4, column 1
8. `assets/dashboard/executive-summary.png` — Gallery row 4, column 2
9. `assets/architecture/system-architecture.png` — Architecture section
10. `assets/architecture/optimization-pipeline.png` — Pipeline section
11. `assets/architecture/multi-agent-architecture.png` — AI section

---

## Documentation Image Placement

| Document | Images Used |
|---|---|
| `docs/PROJECT_GALLERY.md` | All 14 dashboard screenshots |
| `docs/SCREENSHOTS.md` | (text only — references filenames) |
| `docs/BENCHMARKS.md` | (text only — data tables) |
| `docs/RELEASE_NOTES.md` | overview-dashboard.png |
| `docs/IMAGE_GUIDE.md` | (this file — reference only) |

---

## GitHub Release Image Placement

| Section | Images |
|---|---|
| Release body | overview-dashboard.png, fleet-explorer.png, executive-summary.png |
| Release assets | demo.gif or demo.mp4 |

---

## Summary Table

| Location | # Images | Types |
|---|---|---|
| README.md | 11 | dashboard (8), architecture (3) |
| docs/PROJECT_GALLERY.md | 14 | all dashboard tabs |
| docs/RELEASE_NOTES.md | 1 | overview |
| GitHub Release | 4 | dashboard (3), demo (1) |
| **Total unique** | **14** dashboard + 4 architecture + 2 benchmark + 2 runtime + 2 demo = **24 images** |
