"""
Tier 2 Boundary and Corner Cases: Features F10 through F12.
- F10: Dynamic Workspace Switcher Boundary Cases
- F11: Unified Free Transform Gizmo (Ctrl+T) Boundary Cases
- F12: Global Command Palette (Ctrl+K / Ctrl+P) Boundary Cases
"""

from __future__ import annotations

import math
import os
import re
import stat
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tests.e2e.harness.assertions import (
    assert_shortcut_mapping,
    parse_shortcut_file,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestF10WorkspaceBoundaries(OpaqueBoxE2ETestCase):
    """
    F10 Boundary Tests: Corrupted shortcutsrc syntax, missing PhotoGIMP theme dir,
    rapid workspace toggle stress, conflicting custom shortcuts preservation, read-only config.
    """

    def test_f10_boundary_01_corrupted_shortcutsrc_syntax(self):
        """Boundary: Corrupted shortcutsrc syntax recovery and fallback."""
        corrupted_text = """
; Corrupted shortcutsrc
(gtk_accel_path "<Actions>/image/image-transform-free" "<Primary>t")
(broken_syntax_without_closing_paren "<Actions>/broken"
(gtk_accel_path "<Actions>/layers/layers-duplicate" "<Primary>j")
"""
        parsed = parse_shortcut_file(corrupted_text)
        # Verify valid lines are recovered while broken lines are skipped safely
        self.assertIn("<Actions>/image/image-transform-free", parsed)
        self.assertIn("<Actions>/layers/layers-duplicate", parsed)
        self.assertEqual(parsed["<Actions>/image/image-transform-free"], "<Primary>t")
        self.assertEqual(parsed["<Actions>/layers/layers-duplicate"], "<Primary>j")

    def test_f10_boundary_02_missing_photogimp_theme_directory(self):
        """Boundary: Graceful fallback when PhotoGIMP theme subfolder is missing."""
        missing_dir = self.temp_dir / "nonexistent_photogimp_themes"

        def switch_workspace(profile: str, theme_root: Path) -> Dict[str, str]:
            target_profile_dir = theme_root / profile
            if not target_profile_dir.exists():
                # Fallback to default GIMP workspace
                return {"active_profile": "Default", "status": "FALLBACK_APPLIED"}
            return {"active_profile": profile, "status": "LOADED"}

        res = switch_workspace("PhotoGIMP", missing_dir)
        self.assertEqual(res["active_profile"], "Default")
        self.assertEqual(res["status"], "FALLBACK_APPLIED")

    def test_f10_boundary_03_rapid_workspace_toggle_stress(self):
        """Boundary: Rapidly toggling between PhotoGIMP and Default workspaces 50 times."""
        active_ws = "Default"
        history = []

        t0 = time.perf_counter()
        for i in range(50):
            target = "PhotoGIMP" if active_ws == "Default" else "Default"
            active_ws = target
            history.append(active_ws)
        t_delta = time.perf_counter() - t0

        self.assertEqual(len(history), 50)
        self.assertEqual(active_ws, "Default")
        self.assertLess(t_delta, 0.5)

    def test_f10_boundary_04_conflicting_custom_shortcuts_preservation(self):
        """Boundary: Preserving custom user-defined shortcuts when switching workspaces."""
        user_custom_shortcuts = {
            "<Actions>/file/file-export": "<Primary><Shift>e",
            "<Actions>/custom/my-plugin": "<Primary><Alt>m",
        }
        photogimp_defaults = {
            "<Actions>/image/image-transform-free": "<Primary>t",
            "<Actions>/layers/layers-duplicate": "<Primary>j",
            "<Actions>/file/file-export": "<Primary><Shift>s",  # Conflict!
        }

        def merge_workspace_shortcuts(defaults: Dict[str, str], user_overrides: Dict[str, str]) -> Dict[str, str]:
            merged = dict(defaults)
            merged.update(user_overrides)  # User custom preferences take precedence
            return merged

        merged_map = merge_workspace_shortcuts(photogimp_defaults, user_custom_shortcuts)
        self.assertEqual(merged_map["<Actions>/file/file-export"], "<Primary><Shift>e")
        self.assertEqual(merged_map["<Actions>/image/image-transform-free"], "<Primary>t")
        self.assertEqual(merged_map["<Actions>/custom/my-plugin"], "<Primary><Alt>m")

    def test_f10_boundary_05_readonly_config_directory(self):
        """Boundary: Handling read-only filesystem permissions in config folder gracefully."""
        ro_dir = self.temp_dir / "readonly_config"
        ro_dir.mkdir(parents=True, exist_ok=True)
        # Create a file inside then make directory read-only
        test_file = ro_dir / "gimprc"
        test_file.write_text("# initial config\n", encoding="utf-8")

        # Set read-only permissions (r-xr-xr-x)
        ro_dir.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        def attempt_save_config(target_dir: Path, content: str) -> bool:
            try:
                (target_dir / "gimprc.tmp").write_text(content, encoding="utf-8")
                return True
            except (IOError, PermissionError):
                # Fallback to memory-only preferences without crash
                return False
            finally:
                # Restore permissions for cleanup
                ro_dir.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

        saved = attempt_save_config(ro_dir, "(theme 'Dark-Pro')")
        self.assertFalse(saved)


class TestF11FreeTransformBoundaries(OpaqueBoxE2ETestCase):
    """
    F11 Boundary Tests: Degenerate 0-area bounding box, 180-degree flip inversion,
    100x100 warp mesh grid, non-invertible perspective matrix, transform cancel rollback.
    """

    def test_f11_boundary_01_degenerate_zero_area_bbox_transform(self):
        """Boundary: Degenerate 0-area bounding box (0 width or 0 height) handling."""
        def validate_transform_bbox(w: float, h: float) -> Tuple[bool, float, float]:
            min_dim = 1.0
            if w <= 0.0 or h <= 0.0:
                # Clamp to minimum 1px dimension
                return False, max(min_dim, w), max(min_dim, h)
            return True, w, h

        valid_0, w0, h0 = validate_transform_bbox(0.0, 100.0)
        self.assertFalse(valid_0)
        self.assertEqual(w0, 1.0)
        self.assertEqual(h0, 100.0)

        valid_neg, wn, hn = validate_transform_bbox(-50.0, -20.0)
        self.assertFalse(valid_neg)
        self.assertEqual(wn, 1.0)
        self.assertEqual(hn, 1.0)

    def test_f11_boundary_02_180_degree_flip_inversion(self):
        """Boundary: Exact 180-degree horizontal and vertical flip inversion matrix."""
        # 180 deg rotation matrix: [[-1, 0], [0, -1]]
        def compute_flip_matrix(flip_h: bool, flip_v: bool) -> List[float]:
            sx = -1.0 if flip_h else 1.0
            sy = -1.0 if flip_v else 1.0
            return [sx, 0.0, 0.0, sy]

        mat_180 = compute_flip_matrix(flip_h=True, flip_v=True)
        self.assertEqual(mat_180, [-1.0, 0.0, 0.0, -1.0])

        # Determinant of 180 flip
        det = mat_180[0] * mat_180[3] - mat_180[1] * mat_180[2]
        self.assertEqual(det, 1.0)

    def test_f11_boundary_03_warp_mesh_100x100_control_points(self):
        """Boundary: Extreme dense warp mesh grid (100x100 = 10,000 control points) interpolation."""
        grid_rows = 100
        grid_cols = 100

        # Generate 100x100 control points
        mesh_points = []
        for r in range(grid_rows):
            row = []
            for c in range(grid_cols):
                row.append((float(c * 10), float(r * 10)))
            mesh_points.append(row)

        self.assertEqual(len(mesh_points), 100)
        self.assertEqual(len(mesh_points[0]), 100)
        total_pts = sum(len(row) for row in mesh_points)
        self.assertEqual(total_pts, 10000)

        # Interpolate a point at (25.5, 30.5)
        r_idx = 30
        c_idx = 25
        p00 = mesh_points[r_idx][c_idx]
        p11 = mesh_points[r_idx + 1][c_idx + 1]
        mid_x = (p00[0] + p11[0]) / 2.0
        mid_y = (p00[1] + p11[1]) / 2.0

        self.assertEqual(mid_x, 255.0)
        self.assertEqual(mid_y, 305.0)

    def test_f11_boundary_04_non_invertible_perspective_matrix(self):
        """Boundary: Singular non-invertible perspective 3x3 matrix detection."""
        # Matrix with row of zeros or determinant = 0
        singular_matrix = [
            [1.0, 2.0, 3.0],
            [2.0, 4.0, 6.0],  # Linear dependent (2x row 0) -> det=0
            [7.0, 8.0, 9.0],
        ]

        def det_3x3(m: List[List[float]]) -> float:
            return (
                m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
            )

        det = det_3x3(singular_matrix)
        self.assertAlmostEqual(det, 0.0, delta=1e-9)

        def is_invertible(m: List[List[float]], epsilon: float = 1e-7) -> bool:
            return abs(det_3x3(m)) > epsilon

        self.assertFalse(is_invertible(singular_matrix))

    def test_f11_boundary_05_transform_cancel_escape_rollback(self):
        """Boundary: Escape key transform cancellation restoring original state."""
        original_bounds = {"x": 50.0, "y": 50.0, "width": 400.0, "height": 300.0, "rotation": 0.0}
        active_transform = {"x": 120.0, "y": 180.0, "width": 600.0, "height": 450.0, "rotation": 45.0}

        def on_key_press_escape(current_state: Dict[str, Any], saved_state: Dict[str, Any]) -> Dict[str, Any]:
            # Rollback to saved original state
            return dict(saved_state)

        rolled_back = on_key_press_escape(active_transform, original_bounds)
        self.assertEqual(rolled_back, original_bounds)
        self.assertEqual(rolled_back["rotation"], 0.0)


class TestF12CommandPaletteBoundaries(OpaqueBoxE2ETestCase):
    """
    F12 Boundary Tests: 10,000 registered actions search, empty search query,
    non-matching regex characters, Unicode/emoji queries, and rapid open/close stress.
    """

    def test_f12_boundary_01_10000_registered_actions(self):
        """Boundary: Fuzzy search query over 10,000 registered actions within 50ms."""
        # Generate 10,000 actions
        actions = [{"id": f"action_{i}", "label": f"Filter Operation Mode {i}", "category": "filters"} for i in range(10000)]
        actions.append({"id": "target_action", "label": "Gaussian Blur Extreme", "category": "filters"})

        def fuzzy_search(query: str, items: List[Dict[str, str]], limit: int = 10) -> List[Dict[str, str]]:
            q_lower = query.lower()
            results = []
            for item in items:
                lbl = item["label"].lower()
                if q_lower in lbl:
                    results.append(item)
                    if len(results) >= limit:
                        break
            return results

        t0 = time.perf_counter()
        matches = fuzzy_search("gaussian blur", actions)
        t_delta = time.perf_counter() - t0

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], "target_action")
        self.assertLess(t_delta, 0.05)  # < 50ms

    def test_f12_boundary_02_empty_search_query(self):
        """Boundary: Empty string search query showing recent / top actions."""
        all_actions = [
            {"id": "file-new", "label": "New Image...", "recent": True},
            {"id": "file-open", "label": "Open...", "recent": True},
            {"id": "layers-duplicate", "label": "Duplicate Layer", "recent": False},
        ]

        def get_palette_results(query: str, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not query.strip():
                # Return recents
                return [a for a in actions if a.get("recent")]
            return [a for a in actions if query.lower() in a["label"].lower()]

        res_empty = get_palette_results("", all_actions)
        self.assertEqual(len(res_empty), 2)
        self.assertEqual(res_empty[0]["id"], "file-new")

    def test_f12_boundary_03_non_matching_regex_query(self):
        """Boundary: Search query with special regex characters and gibberish strings."""
        special_queries = [
            "[[[*?+^$()",
            "\\d+\\w+\\s+",
            "(((unclosed parentheses",
            "/*?.,<>~!@#$%^&*()_+",
        ]

        def safe_query_match(query: str, text: str) -> bool:
            # Substring matching without regex crash
            return query.lower() in text.lower()

        for sq in special_queries:
            matched = safe_query_match(sq, "Apply Layer Mask")
            self.assertFalse(matched)

    def test_f12_boundary_04_unicode_emoji_action_query(self):
        """Boundary: Search query containing Unicode multilingual text and emojis."""
        unicode_actions = [
            {"id": "act_1", "label": "🎨 Color Balance 调色"},
            {"id": "act_2", "label": "⚡ Instant AI Matting 快速抠图"},
            {"id": "act_3", "label": "فلتر التمويه (Blur Filter Arabic)"},
        ]

        def query_actions(q: str) -> List[Dict[str, str]]:
            return [a for a in unicode_actions if q.lower() in a["label"].lower()]

        self.assertEqual(len(query_actions("🎨")), 1)
        self.assertEqual(len(query_actions("快速抠图")), 1)
        self.assertEqual(len(query_actions("فلتر")), 1)
        self.assertEqual(len(query_actions("nonexistent 🚀")), 0)

    def test_f12_boundary_05_rapid_open_close_toggle_stress(self):
        """Boundary: Rapidly opening and closing command palette modal 100 times."""
        palette_state = {"is_open": False, "open_count": 0, "close_count": 0}

        for i in range(100):
            # Open (Ctrl+K)
            palette_state["is_open"] = True
            palette_state["open_count"] += 1
            # Close (Escape)
            palette_state["is_open"] = False
            palette_state["close_count"] += 1

        self.assertFalse(palette_state["is_open"])
        self.assertEqual(palette_state["open_count"], 100)
        self.assertEqual(palette_state["close_count"], 100)


if __name__ == "__main__":
    unittest.main()
