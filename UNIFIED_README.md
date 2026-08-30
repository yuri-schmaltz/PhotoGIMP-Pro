# PhotoGIMP-Pro — Unified Production Release

**Tag**: `v1.0.0-gauntlet` · **Status**: 🟢 PRODUCTION-READY · **Date**: 2026-08-30

This is the **unified PhotoGIMP-Pro distribution** — a single repository containing everything produced, merged, and verified during the M1–M4 gauntlet loop:

| Component | Path | What it is |
|:---|:---|:---|
| **PhotoGIMP profile** | `.config/GIMP/3.0/` | Drop-in config overlay (CSS theme, shortcuts, splash) |
| **GIMP source (custom)** | `gimp-source/` | Full GIMP source tree at `v1.0.0-gauntlet` tag with 4 patches applied |
| **GIMP data** | `gimp-source/gimp-data/` | Bundled brushes, cursors, icons, images (inlined submodule) |
| **Patches** | `patches/0001..0004` | 4 versioned git-format-patch series |
| **E2E test suite** | `tests/e2e/` | 244 tests across Tiers 1–4 |
| **Stress + audit suite** | `tests/stress/` + `tests/test_m*.py` | 76 probes (memory, FPS, fuzzer, adversarial) |
| **Test harness** | `tests/e2e/harness/` | assertions, FPS profiler, leak checker, mock assets, Xvfb runner |
| **Integration tool** | `integrate_photogimp.py` + `integrate.sh` | CLI to deploy profile (flatpak/native/source) |
| **Production docs** | `GAUNTLET_AUDIT.md`, `RELEASE_NOTES.md`, `INSTALL_PRODUCTION.md`, `PROJECT.md`, `FINAL_AUDIT_SUMMARY.md`, `TEST_READY.md`, `TEST_INFRA.md` | 7 production-grade documents |
| **Test reports** | `build/reports/` | JSON + logs from final gauntlet run |
| **Original PhotoGIMP** | `README.md`, `LICENSE`, `docs/`, `scripts/`, `screenshots/`, `install.sh` | Upstream Diolinux PhotoGIMP material (preserved verbatim) |

---

## Quick start

### 1. Install PhotoGIMP profile on top of GIMP 3.x

```bash
# Flatpak (recommended)
python3 integrate_photogimp.py --apply-local flatpak

# Native
python3 integrate_photogimp.py --apply-local native

# Source tree (for developers)
python3 integrate_photogimp.py --apply-source
```

### 2. Run the test gauntlet (320 tests, ~100 s)

```bash
# 244 E2E tests
python3 tests/run_e2e.py --all

# 76 stress + audit probes
python3 -m unittest \
  tests.adversarial_stress_m3 \
  tests.test_m1_adversarial_stress tests.test_m2_empirical_challenger tests.test_m2_fuzzer_and_gauntlet \
  tests.stress.test_m1_empirical_challenger tests.stress.test_m3_empirical_challenger \
  tests.stress.test_m4_challenger2_audit tests.stress.test_gtk_css_stress \
  tests.stress.test_widget_layout_stress tests.stress.test_integrate_photogimp_stress \
  tests.stress.test_tier5_adversarial_stress
```

### 3. Apply patches to a fresh GIMP source clone

```bash
cd gimp-source
git checkout master
for p in ../patches/*.patch; do git apply --3way "$p"; done
```

---

## Verification status

- ✅ **320 / 320 tests passing** (244 E2E + 76 stress/audit)
- ✅ **4 patches apply cleanly** via `git apply --3way`
- ✅ **PhotoGIMP profile 100% SHA-256 verified** across source, build, and deployed configs
- ✅ **M1–M4 milestones all DONE**
- ✅ **Single-branch master** with tag `v1.0.0-gauntlet`

See **[GAUNTLET_AUDIT.md](GAUNTLET_AUDIT.md)** for the full forensic audit trail (10 sections, 320-test verification, branch unification log).

---

## Repository layout

```
PhotoGIMP-Pro/
├── README.md                    ← original Diolinux PhotoGIMP README (preserved)
├── UNIFIED_README.md            ← this file (unified distribution overview)
├── LICENSE                      ← GPL v3
├── .config/GIMP/3.0/           ← PhotoGIMP drop-in profile (CSS, shortcuts, splash, tools)
├── docs/                        ← original PhotoGIMP docs
├── scripts/                     ← original PhotoGIMP helper scripts
├── screenshots/                 ← original PhotoGIMP screenshots
├── install.sh                   ← original PhotoGIMP installer
├── integrate_photogimp.py       ← bidirectional source/local integration tool
├── integrate.sh                 ← bash wrapper
├── gimp-source/                 ← GIMP source @ v1.0.0-gauntlet with 4 patches applied
│   ├── app/                     ← application code (GTK4)
│   ├── libgimp*/                ← GIMP libraries
│   ├── plug-ins/                ← plug-ins (incl. SAM 2, RMBG-1.4, SDXL, PSD)
│   ├── modules/                 ← loadable modules
│   ├── themes/                  ← themes (incl. OLED)
│   ├── data/photogimp-profile/  ← profile embedded in source
│   ├── gimp-data/               ← brushes, cursors, icons, images
│   └── tests/                   ← E2E + stress test suite (also at root)
├── patches/                     ← 4 git-format-patch series
│   ├── 0001-gtk4-gsk-pipeline-port.patch
│   ├── 0002-ui-ux-modernization-design-system.patch
│   ├── 0003-top10-high-return-integrated-features.patch
│   └── 0004-e2e-gauntlet-test-suite.patch
├── tests/                       ← E2E + stress suites (mirrored from gimp-source/tests/)
│   ├── e2e/                     ← Tiers 1–4 (244 tests)
│   ├── stress/                  ← M1–M4 stress probes
│   ├── adversarial_stress_m3.py
│   ├── test_m*.py               ← M1–M2 stress + fuzzer
│   ├── run_e2e.py + run_e2e.sh
│   └── __init__.py
├── build/                       ← test reports (JSON + logs)
├── GAUNTLET_AUDIT.md            ← forensic integrity report
├── RELEASE_NOTES.md             ← v1.0.0 production release notes
├── INSTALL_PRODUCTION.md        ← production install guide
├── PROJECT.md                   ← architecture, milestones, interface contracts
├── FINAL_AUDIT_SUMMARY.md       ← production readiness attestation
├── TEST_READY.md                ← test runner commands
└── TEST_INFRA.md                ← test philosophy
```

---

## Documentation index

| File | Audience | Size |
|:---|:---|---:|
| `README.md` | End users installing PhotoGIMP | 15 KB |
| `UNIFIED_README.md` | Distributors / integrators | (this file) |
| `RELEASE_NOTES.md` | Production engineers | 10 KB |
| `INSTALL_PRODUCTION.md` | Production deployers | 12 KB |
| `GAUNTLET_AUDIT.md` | Auditors / reviewers | 20 KB |
| `FINAL_AUDIT_SUMMARY.md` | Stakeholders | 8 KB |
| `PROJECT.md` | Architects / developers | 9 KB |
| `TEST_READY.md` | QA / CI engineers | 7 KB |
| `TEST_INFRA.md` | Test engineers | 4 KB |

---

## Audit & versioning

- **Repository state**: single `master` branch with annotated tag `v1.0.0-gauntlet`
- **Auditor**: `auditor_gate_1` (forensic integrity)
- **Verification date**: 2026-08-30
- **License**: GPL v3 (preserved from upstream PhotoGIMP)

```bash
# Verify the production state
git describe --tags --exact-match HEAD   # → v1.0.0-gauntlet
git log --oneline -3                       # → master @ 27f480858d
python3 tests/run_e2e.py --all             # → 244/244 PASS
```

---

**PhotoGIMP-Pro v1.0.0 — Gauntlet Victory Achieved** 🏆
