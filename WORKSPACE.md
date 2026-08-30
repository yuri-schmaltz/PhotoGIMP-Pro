# Workspace Layout & Repo Migration Note

**Repository**: `yuri-schmaltz/PhotoGIMP-Pro` (single source of truth)

## Overview

This repository (`/home/yuri/Documentos/PhotoGIMP-Pro/`) is the **single GitHub repo** containing all GIMP + PhotoGIMP modernization work. It was assembled from three legacy repos and supersedes them.

## Legacy repos (DO NOT push to GitHub)

If you opened VS Code on the **original** workspace folder `/home/yuri/Documentos/gimp/`, you would see three nested Git repositories in the Source Control panel:

| Folder | Repo | Branch | Status |
|:---|:---|:---|:---|
| `gimp-source/` | fork of GNOME/gimp | `master` (with our patches) | kept local, NOT on GitHub |
| `photogimp/` | fork of Diolinux/PhotoGIMP | `feat/modern-design-system` | kept local, NOT on GitHub |
| `gimp-data/` | git submodule of GIMP | (HEAD `fe4ecc0b`) | kept local, NOT on GitHub |

These were the **development repos**. Their content has been **copied and unified** into this repo, with all customizations applied (4 versioned patches + new AI plugins + tests + docs + profile + icons + splash).

## This repo — what's here

```
PhotoGIMP-Pro/                          ← single git repo (branch main)
├── README.md                          ← upstream Diolinux README (preserved)
├── UNIFIED_README.md                  ← distribution overview
├── icon.png                           ← master app icon (240x240)
├── splash.jpeg                        ← master splash (1376x768)
├── LICENSE                            ← GPL v3
├── .config/GIMP/3.0/                  ← PhotoGIMP profile
├── .local/share/icons/hicolor/        ← app icons (7 sizes + root)
├── docs/, scripts/, screenshots/, install.sh
├── integrate_photogimp.py, integrate.sh
├── gimp-source/                       ← GIMP source with patches applied
├── patches/                           ← 4 git-format-patches (0001-0004)
├── tests/                             ← 244 E2E + 76 stress/audit
├── build/                             ← test reports
├── 7 docs de produção (*.md)
└── WORKSPACE.md                       ← this file
```

## Migration timeline

1. **2026-08-29** — Gauntlet loop completed; M1–M4 all DONE; 244 E2E + 71 stress/audit tests passing
2. **2026-08-30** — Branch unification in `gimp-source/`: `feat/modern-design-system` → `release/v1.0.0-gauntlet` → master @ tag `v1.0.0-gauntlet`
3. **2026-08-30** — Unified repo `PhotoGIMP-Pro/` created, force-pushed to GitHub (commit `8304f5c`)
4. **2026-08-30** — Splash + icon replaced (commit `a153b5a`)

## How to open this repo in VS Code

```bash
# From terminal
code /home/yuri/Documentos/PhotoGIMP-Pro

# Or from VS Code: Ctrl+K Ctrl+O → navigate to /home/yuri/Documentos/PhotoGIMP-Pro
```

You will see a **single** Source Control entry (this repo's master branch), not three.

## How to keep working in this repo

```bash
cd /home/yuri/Documentos/PhotoGIMP-Pro
git status                          # see local changes
git log --oneline                    # see history
git diff                            # see unstaged changes
git add <files> && git commit -m "..."
git push origin main                 # push to yuri-schmaltz/PhotoGIMP-Pro
```

## Should I delete the legacy `/home/yuri/Documentos/gimp/` workspace?

**No, not yet.** The legacy workspace is still useful as:
- A reference for the original git history of `gimp-source/` and `photogimp/`
- A source for `patches/` if you need to rebase or regenerate
- A working dev environment (you can run `cd gimp-source && git apply --3way ../patches/*.patch`)

You can safely delete it once you're confident everything you need is in this repo. If you decide to delete:

```bash
# BACKUP FIRST
cp -r /home/yuri/Documentos/gimp /tmp/gimp-backup-$(date +%Y%m%d)
# Then delete (irreversible)
rm -rf /home/yuri/Documentos/gimp
```

---

**TL;DR**: Work in `/home/yuri/Documentos/PhotoGIMP-Pro/`. Push to `yuri-schmaltz/PhotoGIMP-Pro`. The 3 repos in the legacy `/home/yuri/Documentos/gimp/` workspace are kept locally for reference; they are NOT on GitHub and don't need to be.
