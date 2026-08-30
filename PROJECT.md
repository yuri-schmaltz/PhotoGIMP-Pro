# Project: GIMP + PhotoGIMP Modernization & Gauntlet Loop

## Architecture & Subsystems
- **Build & Core Engine** (`gimp-source/meson.build`, `app/core/`, `app/config/`):
  - GTK4 & GSK pipeline descriptors (`gtk4 >= 4.14.0`, GLib 2.80, removing deprecated ATK).
  - Central image processing kernel backed by GEGL node graphs and OpenColorIO / LittleCMS 2 color management.
- **Display & Canvas Viewport** (`app/display/`):
  - GPU-accelerated canvas rendering using `GtkSnapshot`, `GskRenderNode` (`GskTextureNode`, `GskTransformNode`) with OpenGL/Vulkan backends and cairo fallback.
  - Multi-touch and input gesture controller architecture (`GtkGestureZoom`, `GtkGestureRotate`, `GtkGestureStylus`, `GtkGestureDrag`, `GtkEventControllerMotion`, `GtkEventControllerKey`).
- **Widgets, Menus & Dockables** (`app/widgets/`, `app/menus/`, `app/dialogs/`, `libgimpwidgets/`):
  - Modernized `GtkPopoverMenuBar` binding `GMenuModel` (`GimpMenuModel`).
  - High-performance `GtkListView` / `GtkColumnView` layer tree with `GtkTreeListModel`.
  - Pill sliders (`GimpSpinScale`), minimalist tabs (`GimpDockbook`), single-column tools palette (`GimpToolPalette`).
  - Global Command Palette (`GimpSearchPopup` / `action-search-dialog` with fuzzy finder).
- **Non-Destructive Graph & Layer Effects** (`app/core/gimpdrawablefilter.*`, `app/operations/`):
  - Live non-destructive Adjustment Layers feeding from stack composition into GEGL nodes (Curves, Levels, Color Balance).
  - Real-time Layer Styles FX engine (Drop Shadow, Stroke, Outer Glow, Bevel & Emboss).
  - Smart Objects container architecture (preserving original SVG, PSD, RAW vector/raster assets).
- **AI Inference & Color Management** (`plug-ins/python/`, `plug-ins/file-psd/`, `modules/`):
  - Offline local AI plug-ins with ONNX Runtime: SAM 2 interactive magic selection, RMBG-1.4 1-click background removal, SDXL/Flux local inpainting.
  - Enhanced Smart PSD engine with layer effects and adjustment layers roundtrip fidelity.
  - Soft-proofing CMYK via LittleCMS 2 and VFX ACES via OpenColorIO v2.
- **Theming & PhotoGIMP Ecosystem** (`themes/`, `photogimp/`, `integrate_photogimp.py`):
  - Dark Pro & OLED high-contrast design system (`gimp.css`, `gimp-dark.css`).
  - Hot-swap Workspace Switcher under *Window > Workspaces* (`_Workspaces`) swapping dock layouts and Photoshop shortcut tables (`shortcutsrc`).
  - Bidirectional integration script `integrate_photogimp.py` / `integrate.sh`.
- **E2E Testing & Gauntlet Infrastructure** (`app/tests/`, `tools/run_test_env.sh`, `tests/`):
  - Headless test execution via `xvfb-run` and `dbus-run-session`.
  - 5-Tier comprehensive test suite (Feature, Boundary/Corner, Pairwise Combinations, Real-World Scenarios, Adversarial White-Box Hardening).
  - Memory leak verification (`G_DEBUG=gc-friendly`, Valgrind/ASan), viewport FPS stability benchmarking, and shortcut integrity validation.

---

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | GTK4 Meson Build & Dependencies | Migrate `meson.build` from `gtk+-3.0`/`atk` to `gtk4 >= 4.14.0` | M1 | ORIGINAL_REQUEST §R1 |
| 2 | GSK GPU Canvas Rendering | Replace Cairo canvas blitting with `GtkSnapshot`/`GskRenderNode` GPU pipeline | M1 | ORIGINAL_REQUEST §R1 |
| 3 | GtkEventController & Input Gestures | Modernize canvas tool events with `GtkEventController`, `GtkGestureStylus`, `GtkGestureDrag`, `GtkGestureClick` | M1 | ORIGINAL_REQUEST §R1 |
| 4 | GMenuModel & GtkPopoverMenuBar | Migrate top menu bar to `GtkPopoverMenuBar` bound to `GimpMenuModel` | M1 | ORIGINAL_REQUEST §R1 |
| 5 | GtkListView Layer Tree | Upgrade layer/channel/path trees from `GtkTreeView` to high-performance `GtkListView` | M1 | ORIGINAL_REQUEST §R1 |
| 6 | Dark Pro / OLED Design System | Contemporary high-contrast OLED theme and `gimp.css` stylesheets | M2 | ORIGINAL_REQUEST §R2 |
| 7 | Modernized Ergonomic Controls | Pill sliders (`GimpSpinScale`), minimalist tabs with focus indicators, single-column tool palette, ultra-discrete scrollbars | M2 | ORIGINAL_REQUEST §R2 |
| 8 | Multi-Touch Canvas Navigation | Fluid multi-touch pinch-to-zoom, continuous canvas rotation, and smooth inertial pan | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Smart Snapping Guides | Magnetic snapping to bounding boxes (`snap_to_bbox`), equidistance, and dynamic pixel distance measurement labels | M2 | ORIGINAL_REQUEST §R2 |
| 10 | Dynamic Workspace Switcher | *Window > Workspaces* menu with hot-swap switching to PhotoGIMP layout, shortcuts, and preferences | M3 | ORIGINAL_REQUEST §R3.1 |
| 11 | Unified Free Transform Gizmo (Ctrl+T) | Single bounding box gizmo for proportional scale, rotate, perspective, and modal warp | M3 | ORIGINAL_REQUEST §R3.2 |
| 12 | Global Command Palette (Ctrl+K / Ctrl+P) | Floating modal fuzzy finder for actions, filters, menus, and layer selection | M3 | ORIGINAL_REQUEST §R3.3 |
| 13 | Non-Destructive Adjustment Layers | Virtual stack layers for Curves, Levels, Color Balance over live GEGL node graph | M3 | ORIGINAL_REQUEST §R3.4 |
| 14 | Real-Time Layer Styles FX | Live GPU/GEGL effects: Drop Shadow, Stroke, Outer Glow, Bevel & Emboss | M3 | ORIGINAL_REQUEST §R3.5 |
| 15 | Smart Objects & Linked Assets | High-resolution containers preserving original SVG, PSD, RAW vector/raster content | M3 | ORIGINAL_REQUEST §R3.6 |
| 16 | Local SAM 2 Magic Selection | Offline 1-click object segmentation via local ONNX GPU inference | M3 | ORIGINAL_REQUEST §R3.7 |
| 17 | 1-Click Local RMBG-1.4 Background Removal | Instant offline neural background matting and alpha separation | M3 | ORIGINAL_REQUEST §R3.8 |
| 18 | Local Generative Inpainting (SDXL / Flux) | Local neural inpainting and object removal without cloud telemetry | M3 | ORIGINAL_REQUEST §R3.9 |
| 19 | Smart PSD Engine & CMYK / OpenColorIO | High-fidelity PSD load/save roundtrip, LittleCMS 2 CMYK soft-proofing, and OCIO v2 color pipeline | M3 | ORIGINAL_REQUEST §R3.10 |
| 20 | E2E Test Suite (Tiers 1-4) | Opaque-box requirement-driven test cases covering features, boundaries, combinations, and real-world workloads | E2E | ORIGINAL_REQUEST §R4 |
| 21 | Adversarial Gauntlet Hardening (Tier 5) | White-box stress tests, memory leak auditing, 60 FPS viewport benchmarking, shortcut validation, versioned patches | M4 | ORIGINAL_REQUEST §R4 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | GTK4 & GSK Pipeline Technological Port | Features #1, #2, #3, #4, #5 | none | DONE |
| M2 | UI/UX Modernization & Design System | Features #6, #7, #8, #9 | M1 | DONE |
| M3 | Top 10 High-Return Integrated Features | Features #10, #11, #12, #13, #14, #15, #16, #17, #18, #19 | M1, M2 | DONE |
| E2E | Opaque-Box E2E Testing Track | Feature #20: 4-Tier test suite, test harness, `TEST_READY.md` | none | DONE |
| M4 | Final Integration & Adversarial Gauntlet Loop | Feature #21: Phase 1 (100% E2E Pass Tiers 1-4) + Phase 2 (Tier 5 Adversarial Hardening, Leaks, FPS, Patches) | M1, M2, M3, E2E | DONE |

---

## Interface Contracts

### 1. GSK Canvas Rendering (`app/display/`)
- Function: `gimp_display_shell_snapshot(GtkWidget *widget, GtkSnapshot *snapshot)`
- Types: `GskRenderNode`, `GskTextureNode`, `GskTransformNode`, `GdkTexture`, `GdkGLTexture`
- Behavior: Pulls tiles from GEGL projection and generates GPU texture nodes with hardware bilinear interpolation and clipping.

### 2. Gesture Controllers (`app/display/gimpdisplayshell-tool-events.c`)
- Event Controllers:
  - `GtkGestureClick` for button presses/releases.
  - `GtkGestureDrag` for tool interaction coordinates.
  - `GtkGestureStylus` for pressure, tilt, and eraser detection.
  - `GtkGestureZoom` & `GtkGestureRotate` for canvas transformations.
  - `GtkEventControllerMotion` & `GtkEventControllerKey` for pointer motion and hotkeys.

### 3. Non-Destructive Adjustment Layers & FX (`app/core/`, `app/operations/`)
- Classes: `GimpAdjustmentLayer` (subclass of `GimpLayer`), `GimpDrawableFilter`
- Signal: `"filter-changed"` -> invalidates GEGL graph cache and emits region update.
- Serialization: Serialized into XCF format via `xcf-save.c` / `xcf-load.c` with properties `FILTER_PROP_CONFIG`.

### 4. Workspace Switcher (`app/menus/`, `app/gui/`)
- Action: `"windows-workspace-photogimp"` / `"windows-workspace-default"`
- Behavior: Invokes `menus_remove()`, loads designated `shortcutsrc`, re-configures docks via `GimpDialogFactory`, and triggers `themes_theme_change_notify()`.

---

## Code Layout

- `gimp-source/` — Primary GIMP C/GObject codebase.
  - `gimp-source/meson.build` — Root build definition.
  - `gimp-source/app/` — Application binary, display, core, tools, widgets, menus.
  - `gimp-source/libgimp/` — Public C & Python plugin API.
  - `gimp-source/libgimpwidgets/` — Reusable GTK widgets (pill sliders, color selectors).
  - `gimp-source/plug-ins/` — Python 3 and C plug-ins (AI, PSD engine, file filters).
  - `gimp-source/themes/` — Dark Pro / OLED / Default GTK CSS themes.
  - `gimp-source/app/tests/` — Core and UI headless test suites.
- `photogimp/` — PhotoGIMP patchset and configuration tree (`.config/GIMP/3.0/`).
- `integrate_photogimp.py` / `integrate.sh` — Synchronization and profile deployment tool.
- `.agents/` — Subagent coordination workspace, handoffs, and audit logs.
