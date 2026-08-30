# E2E Test Infra: GIMP + PhotoGIMP Modernization

## Test Philosophy
- **Requirement-Driven & Opaque-Box**: Tests are derived strictly from `ORIGINAL_REQUEST.md` and user-facing requirements.
- **Independence**: The E2E test harness operates independently of internal module design.
- **Methodology**: 4-Tier Systematic Testing (Category-Partition, Boundary Value Analysis, Pairwise Combinatorial Testing, Real-World Workload Testing) + Tier 5 Adversarial Coverage Hardening.

---

## Feature Inventory & Test Coverage Mapping

| # | Feature | Requirement Source | Tier 1 (Min 5) | Tier 2 (Min 5) | Tier 3 (Pairwise) | Tier 4 (Workload) |
|---|---------|-------------------|:--------------:|:--------------:|:-----------------:|:-----------------:|
| 1 | GTK4 Meson Build & Dependencies | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | GSK GPU Canvas Rendering | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | GtkEventController & Input Gestures | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 4 | GMenuModel & GtkPopoverMenuBar | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 5 | GtkListView Layer Tree | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 6 | Dark Pro / OLED Design System | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 7 | Modernized Ergonomic Controls | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 8 | Multi-Touch Canvas Navigation | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 9 | Smart Snapping Guides | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 10 | Dynamic Workspace Switcher | ORIGINAL_REQUEST §R3.1 | 5 | 5 | ✓ | ✓ |
| 11 | Unified Free Transform Gizmo (Ctrl+T) | ORIGINAL_REQUEST §R3.2 | 5 | 5 | ✓ | ✓ |
| 12 | Global Command Palette (Ctrl+K/Ctrl+P) | ORIGINAL_REQUEST §R3.3 | 5 | 5 | ✓ | ✓ |
| 13 | Non-Destructive Adjustment Layers | ORIGINAL_REQUEST §R3.4 | 5 | 5 | ✓ | ✓ |
| 14 | Real-Time Layer Styles FX | ORIGINAL_REQUEST §R3.5 | 5 | 5 | ✓ | ✓ |
| 15 | Smart Objects & Linked Assets | ORIGINAL_REQUEST §R3.6 | 5 | 5 | ✓ | ✓ |
| 16 | Local SAM 2 Magic Selection | ORIGINAL_REQUEST §R3.7 | 5 | 5 | ✓ | ✓ |
| 17 | 1-Click Local RMBG-1.4 Background Removal | ORIGINAL_REQUEST §R3.8 | 5 | 5 | ✓ | ✓ |
| 18 | Local Generative Inpainting (SDXL/Flux) | ORIGINAL_REQUEST §R3.9 | 5 | 5 | ✓ | ✓ |
| 19 | Smart PSD Engine & CMYK / OpenColorIO | ORIGINAL_REQUEST §R3.10 | 5 | 5 | ✓ | ✓ |

---

## Test Architecture & Execution

- **Headless Runner**: Executed under `xvfb-run -a dbus-run-session meson test` or standalone Python/C test runners.
- **Pass/Fail Semantics**: Exit code 0 indicates full pass; non-zero exit code or assertion failure marks failure.
- **Memory & Leak Auditing**: Runs with `G_SLICE=always-malloc G_DEBUG=gc-friendly` to catch GObject leaks and dangling references.
- **Directory Layout**:
  - `tests/e2e/tier1_features/` — Feature coverage tests.
  - `tests/e2e/tier2_boundaries/` — Edge case and limit tests.
  - `tests/e2e/tier3_pairwise/` — Cross-feature combination tests.
  - `tests/e2e/tier4_realworld/` — End-to-end multi-step artistic workflows.

---

## Real-World Application Scenarios (Tier 4)

| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Photo Retouching & Isolation Pipeline | SAM 2 / RMBG-1.4 background removal + Adjustment Layers (Levels/Curves) + Drop Shadow FX | High |
| 2 | Complex PSD Graphic Design Import & Export | Smart PSD Engine + Adjustment Layers + Layer FX + CMYK soft-proofing | High |
| 3 | Concept Art Rapid Ideation | SDXL Inpainting + Unified Free Transform (Ctrl+T) + Smart Objects (SVG/RAW) + Dark Pro UI | High |
| 4 | Print Production & Color Management | OpenColorIO ACES display filter + CMYK LittleCMS 2 profile proofing + Snapping Guides | High |
| 5 | PhotoGIMP Hot-Swap & Shortcut Workflow | Workspace Switcher + Photoshop shortcut validation (Ctrl+T, Ctrl+J, Ctrl+D) + Command Palette (Ctrl+K) | High |

---

## Coverage Thresholds

- **Tier 1 (Feature Coverage)**: ≥ 95 test cases (5 × 19 features)
- **Tier 2 (Boundary & Corner)**: ≥ 95 test cases (5 × 19 features)
- **Tier 3 (Pairwise Combinations)**: ≥ 25 interaction test cases
- **Tier 4 (Real-World Scenarios)**: ≥ 10 end-to-end composite scenarios
- **Total Minimum Target**: ≥ 225 test cases across Tiers 1-4
