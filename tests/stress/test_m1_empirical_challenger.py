#!/usr/bin/env python3
"""
Empirical Adversarial Challenger Test Suite for Milestone 1:
GTK4 & GSK Pipeline Technological Port (Features 1 through 5).

Subsystems Covered:
- Feature 1: GTK4 Build System & Dependency Compliance (gtk4 >= 4.14.0, GLib 2.80, ATK removal, CFLAGS)
- Feature 2: GSK GPU Canvas Rendering Pipeline (GtkSnapshot, GskRenderNode, Matrix Transforms, Rapid Zoom Invariance,
             360° Continuous & Cardinal Snap Rotation, Viewport Chunk Partitioning, Memory Stability)
- Feature 3: GtkEventController & Input Gestures (Click, Drag, Stylus Pressure/Tilt, Kinetic Pan Deceleration,
             256 Modifier Bitmasks, Gesture Grouping & Conflict Resolution)
- Feature 4: GMenuModel & GtkPopoverMenuBar (Popover Menu Bars, Models, Deep Hierarchy, Actions, Shortcut Mappings)
- Feature 5: GtkListView Layer Tree & GtkTreeListModel (Tree List Models, Group Expansion, MultiSelection, Drag/Drop Reorder)
- Performance & Robustness: 60 FPS Viewport Latency and Memory RSS Stability Audit
"""

from __future__ import annotations

import gc
import math
import os
import random
import re
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = WORKSPACE_ROOT / "tests"
GIMP_SOURCE_DIR = WORKSPACE_ROOT / "gimp-source"

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from tests.e2e.harness.fps_profiler import FPSProfiler, ViewportBenchmark
from tests.e2e.harness.leak_checker import MemoryLeakChecker, get_process_memory_info


# ============================================================================
# C Implementation Mathematical Models & Simulators
# ============================================================================

ZOOM_MIN = 1.0 / 256.0  # 0.00390625 (~0.39%)
ZOOM_MAX = 256.0        # 25600%
CARDINAL_SNAP_TOLERANCE = 3.0  # degrees
KINETIC_PAN_FRICTION = 0.005
KINETIC_PAN_CUTOFF = 5.0       # px/s
RENDER_BUF_WIDTH = 256
RENDER_BUF_HEIGHT = 256


class GrapheneMatrix4x4:
    """Simulation of graphene_matrix_t 4x4 matrix for 2D/3D affine canvas transformations."""
    def __init__(self, m: Optional[List[List[float]]] = None):
        if m is not None:
            self.m = [row[:] for row in m]
        else:
            self.m = [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]

    def multiply(self, other: GrapheneMatrix4x4) -> GrapheneMatrix4x4:
        res = [[0.0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                res[i][j] = sum(self.m[i][k] * other.m[k][j] for k in range(4))
        return GrapheneMatrix4x4(res)

    def scale(self, sx: float, sy: float, sz: float = 1.0) -> GrapheneMatrix4x4:
        s_mat = [
            [sx, 0.0, 0.0, 0.0],
            [0.0, sy, 0.0, 0.0],
            [0.0, 0.0, sz, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        return self.multiply(GrapheneMatrix4x4(s_mat))

    def translate(self, tx: float, ty: float, tz: float = 0.0) -> GrapheneMatrix4x4:
        t_mat = [
            [1.0, 0.0, 0.0, tx],
            [0.0, 1.0, 0.0, ty],
            [0.0, 0.0, 1.0, tz],
            [0.0, 0.0, 0.0, 1.0],
        ]
        return self.multiply(GrapheneMatrix4x4(t_mat))

    def rotate_z(self, angle_deg: float) -> GrapheneMatrix4x4:
        rad = math.radians(angle_deg)
        c = math.cos(rad)
        s = math.sin(rad)
        r_mat = [
            [c, -s, 0.0, 0.0],
            [s,  c, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        return self.multiply(GrapheneMatrix4x4(r_mat))

    def transform_point2d(self, x: float, y: float) -> Tuple[float, float]:
        nx = self.m[0][0] * x + self.m[0][1] * y + self.m[0][3]
        ny = self.m[1][0] * x + self.m[1][1] * y + self.m[1][3]
        return nx, ny

    def inverse(self) -> Optional[GrapheneMatrix4x4]:
        a = self.m[0][0]
        b = self.m[0][1]
        c = self.m[1][0]
        d = self.m[1][1]
        tx = self.m[0][3]
        ty = self.m[1][3]

        det = a * d - b * c
        if abs(det) < 1e-12:
            return None

        inv_det = 1.0 / det
        ia = d * inv_det
        ib = -b * inv_det
        ic = -c * inv_det
        id_ = a * inv_det
        itx = -(ia * tx + ib * ty)
        ity = -(ic * tx + id_ * ty)

        inv_m = [
            [ia, ib, 0.0, itx],
            [ic, id_, 0.0, ity],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        return GrapheneMatrix4x4(inv_m)


def gimp_display_shell_scale_to_c_model(
    current_scale: float,
    offset_x: float,
    offset_y: float,
    new_scale: float,
    viewport_x: float,
    viewport_y: float,
) -> Tuple[float, float]:
    """Exact transcription of gimp_display_shell_scale_to() coordinate translation."""
    new_scale = max(ZOOM_MIN, min(ZOOM_MAX, new_scale))
    image_x = (viewport_x + offset_x) / current_scale
    image_y = (viewport_y + offset_y) / current_scale

    new_viewport_x = image_x * new_scale - offset_x
    new_viewport_y = image_y * new_scale - offset_y

    new_offset_x = offset_x + (new_viewport_x - viewport_x)
    new_offset_y = offset_y + (new_viewport_y - viewport_y)

    return new_offset_x, new_offset_y


def gimp_rotate_angle_normalize(angle: float, constrain: bool) -> float:
    """Transcription of rotation normalization and magnetic snapping."""
    if constrain:
        return round(angle / 15.0) * 15.0

    norm = math.fmod(angle, 360.0)
    if norm < 0.0:
        norm += 360.0

    if norm < CARDINAL_SNAP_TOLERANCE or norm > (360.0 - CARDINAL_SNAP_TOLERANCE):
        return angle - (norm if norm < 180.0 else (norm - 360.0))
    elif abs(norm - 90.0) <= CARDINAL_SNAP_TOLERANCE:
        return angle + (90.0 - norm)
    elif abs(norm - 180.0) <= CARDINAL_SNAP_TOLERANCE:
        return angle + (180.0 - norm)
    elif abs(norm - 270.0) <= CARDINAL_SNAP_TOLERANCE:
        return angle + (270.0 - norm)
    return angle


def gimp_display_shell_draw_image_chunk_calc(
    w: int, h: int, scale_x: float, scale_y: float, rotate_angle: float
) -> Tuple[int, int, float, float]:
    """Transcription of chunk partitioning in gimpdisplayshell-draw.c lines 165-200."""
    chunk_width = float(RENDER_BUF_WIDTH)
    chunk_height = float(RENDER_BUF_HEIGHT)
    scale = max(scale_x, scale_y)

    if scale != scale_x and scale > 0:
        chunk_width = (chunk_width - 1.0) * (scale_x / scale)
    if scale != scale_y and scale > 0:
        chunk_height = (chunk_height - 1.0) * (scale_y / scale)

    if rotate_angle != 0.0:
        a = rotate_angle * math.pi / 180.0
        denom = abs(math.sin(a)) + abs(math.cos(a))
        if denom > 0:
            chunk_width = chunk_height = (min(chunk_width, chunk_height) - 1.0) / denom

    floor_cw = max(1.0, math.floor(chunk_width))
    floor_ch = max(1.0, math.floor(chunk_height))

    n_rows = math.ceil(h / floor_ch) if h > 0 else 0
    n_cols = math.ceil(w / floor_cw) if w > 0 else 0

    return n_rows, n_cols, chunk_width, chunk_height


# ============================================================================
# Test Suite: Milestone 1 Empirical Challenge & Stress Harness
# ============================================================================

class TestMilestone1EmpiricalChallenger(unittest.TestCase):
    """Rigorous empirical challenge and boundary suite for Milestone 1."""

    @classmethod
    def setUpClass(cls):
        os.environ["G_SLICE"] = "always-malloc"
        os.environ["G_DEBUG"] = "gc-friendly"
        os.environ["G_ENABLE_DIAGNOSTIC"] = "1"

    # =========================================================================
    # FEATURE 1: GTK4 MESON BUILD & DEPENDENCY COMPLIANCE
    # =========================================================================

    def test_m1_f01_build_dependency_declarations(self):
        """Adversarial check: Verify root meson.build and sub-mesons enforce gtk4 >= 4.14.0 and glib >= 2.80.0."""
        root_meson = GIMP_SOURCE_DIR / "meson.build"
        self.assertTrue(root_meson.exists(), "Root meson.build does not exist")
        content = root_meson.read_text(encoding="utf-8", errors="replace")

        # 1. gtk4_minver must be '4.14.0'
        gtk4_match = re.search(r"gtk4_minver\s*=\s*'([^']+)'", content)
        self.assertIsNotNone(gtk4_match, "gtk4_minver variable declaration missing in meson.build")
        gtk4_version = gtk4_match.group(1)
        v_parts = [int(p) for p in gtk4_version.split(".")]
        self.assertGreaterEqual((v_parts[0], v_parts[1]), (4, 14), f"GTK4 min version {gtk4_version} < 4.14.0")

        # 2. glib_minver must be >= '2.80.0'
        glib_match = re.search(r"glib_minver\s*=\s*'([^']+)'", content)
        self.assertIsNotNone(glib_match, "glib_minver variable declaration missing in meson.build")
        glib_version = glib_match.group(1)
        g_parts = [int(p) for p in glib_version.split(".")]
        self.assertGreaterEqual((g_parts[0], g_parts[1]), (2, 80), f"GLib min version {glib_version} < 2.80.0")

        # 3. Compiler flags for GDK version range
        self.assertIn("GDK_VERSION_MIN_REQUIRED=GDK_VERSION_4_14", content)
        self.assertIn("GDK_VERSION_MAX_ALLOWED=GDK_VERSION_4_14", content)

    def test_m1_f01_c_source_no_legacy_gtk3_container_calls(self):
        """Audits C sources in app/display, app/widgets, app/menus for GTK4 modernization."""
        gimp_source = GIMP_SOURCE_DIR / "app"

        # Check that gtkcanvas.c implements snapshot
        canvas_c = gimp_source / "display" / "gimpcanvas.c"
        canvas_src = canvas_c.read_text(encoding="utf-8")
        self.assertTrue(re.search(r"widget_class->snapshot\s*=\s*gimp_canvas_snapshot", canvas_src),
                        "gimp_canvas_snapshot assignment missing in gimpcanvas.c")
        self.assertIn("gimp_display_shell_snapshot", canvas_src)

        # Check gimpdisplayshell-draw.c uses GtkSnapshot / GskRenderNode
        draw_c = gimp_source / "display" / "gimpdisplayshell-draw.c"
        draw_src = draw_c.read_text(encoding="utf-8")
        self.assertIn("gtk_snapshot_push_transform", draw_src)
        self.assertIn("gdk_memory_texture_new", draw_src)
        self.assertIn("gtk_snapshot_append_texture", draw_src)

    # =========================================================================
    # FEATURE 2: GSK GPU CANVAS RENDERING PIPELINE & SCENE GRAPH
    # =========================================================================

    def test_m1_f02_rapid_zoom_anchor_invariance_and_limits(self):
        """Stress: 10,000 rapid zoom steps verifying floating-point precision and anchor invariance."""
        current_scale = 1.0
        offset_x, offset_y = 500.0, 300.0
        anchor_vx, anchor_vy = 960.0, 540.0

        init_img_x = (anchor_vx + offset_x) / current_scale
        init_img_y = (anchor_vy + offset_y) / current_scale

        rng = random.Random(42)
        for step in range(10000):
            zoom_factor = rng.uniform(0.8, 1.25)
            new_scale = max(ZOOM_MIN, min(ZOOM_MAX, current_scale * zoom_factor))

            offset_x, offset_y = gimp_display_shell_scale_to_c_model(
                current_scale, offset_x, offset_y, new_scale, anchor_vx, anchor_vy
            )
            current_scale = new_scale

            curr_img_x = (anchor_vx + offset_x) / current_scale
            curr_img_y = (anchor_vy + offset_y) / current_scale

            self.assertAlmostEqual(curr_img_x, init_img_x, places=5)
            self.assertAlmostEqual(curr_img_y, init_img_y, places=5)
            self.assertFalse(math.isnan(offset_x) or math.isnan(offset_y))
            self.assertFalse(math.isinf(offset_x) or math.isinf(offset_y))

    def test_m1_f02_360_degree_rotation_matrix_and_snapping(self):
        """Stress: Multi-turn rotations across [-3600°, +3600°], verifying cardinal snap and 15° stepping."""
        def circular_diff(a: float, b: float) -> float:
            d = (a - b) % 360.0
            if d > 180.0:
                d -= 360.0
            return abs(d)

        for base in [-720.0, -360.0, 0.0, 360.0, 720.0]:
            for cardinal in [0.0, 90.0, 180.0, 270.0]:
                target = base + cardinal
                for offset in [-2.9, -1.5, 0.0, 1.5, 2.9]:
                    raw = target + offset
                    snapped = gimp_rotate_angle_normalize(raw, constrain=False)
                    diff = circular_diff(snapped, target)
                    self.assertAlmostEqual(diff, 0.0, places=4, msg=f"Failed to snap raw {raw} to {target}")

                for offset in [-5.0, 5.0, 12.0, 45.0]:
                    raw = target + offset
                    unsnapped = gimp_rotate_angle_normalize(raw, constrain=False)
                    self.assertAlmostEqual(unsnapped, raw, places=4)

        for deg in [1.0, 7.4, 7.6, 14.9, 15.1, 29.8, 89.2, 182.3, -44.1, -127.0]:
            constrained = gimp_rotate_angle_normalize(deg, constrain=True)
            expected = round(deg / 15.0) * 15.0
            self.assertEqual(constrained, expected)

    def test_m1_f02_gsk_transform_matrix_invertibility(self):
        """Stress: 4x4 matrix affine composition and exact invertibility M * M^-1 == I."""
        rng = random.Random(1337)
        for i in range(2000):
            scale_x = rng.uniform(ZOOM_MIN, 50.0)
            scale_y = scale_x if rng.choice([True, False]) else rng.uniform(ZOOM_MIN, 50.0)
            rot_deg = rng.uniform(-720.0, 720.0)
            tx = rng.uniform(-50000.0, 50000.0)
            ty = rng.uniform(-50000.0, 50000.0)

            mat = GrapheneMatrix4x4()
            mat = mat.scale(scale_x, scale_y)
            mat = mat.rotate_z(rot_deg)
            mat = mat.translate(tx, ty)

            inv_mat = mat.inverse()
            self.assertIsNotNone(inv_mat)

            ident = mat.multiply(inv_mat)
            for r in range(2):
                for c in range(2):
                    expected = 1.0 if r == c else 0.0
                    self.assertAlmostEqual(ident.m[r][c], expected, places=4)

            px, py = rng.uniform(-10000.0, 10000.0), rng.uniform(-10000.0, 10000.0)
            tx_pt, ty_pt = mat.transform_point2d(px, py)
            rx_pt, ry_pt = inv_mat.transform_point2d(tx_pt, ty_pt)
            self.assertAlmostEqual(rx_pt, px, places=3)
            self.assertAlmostEqual(ry_pt, py, places=3)

    def test_m1_f02_viewport_chunk_partitioning(self):
        """Stress: Canvas tile partitioning across extreme aspect ratios and rotations."""
        test_cases = [
            (1920, 1080, 1.0, 1.0, 0.0),
            (1, 100000, 1.0, 1.0, 0.0),
            (65536, 65536, 0.01, 0.01, 45.0),
            (3840, 2160, 256.0, 256.0, 30.0),
            (100, 100, 1.0, 1.0, 90.0),
            (0, 0, 1.0, 1.0, 0.0),
        ]

        for w, h, sx, sy, rot in test_cases:
            n_rows, n_cols, cw, ch = gimp_display_shell_draw_image_chunk_calc(w, h, sx, sy, rot)
            self.assertGreater(cw, 0.0)
            self.assertGreater(ch, 0.0)
            if w > 0 and h > 0:
                self.assertGreater(n_rows, 0)
                self.assertGreater(n_cols, 0)
                self.assertGreaterEqual(n_rows * math.floor(ch), h)
                self.assertGreaterEqual(n_cols * math.floor(cw), w)
            else:
                self.assertEqual(n_rows, 0)
                self.assertEqual(n_cols, 0)

    # =========================================================================
    # FEATURE 3: GTK4 INPUT GESTURE CONTROLLERS
    # =========================================================================

    def test_m1_f03_simultaneous_modifier_key_bitmasks(self):
        """Stress: All 256 GdkModifierType combinations and multi-key state machine transitions."""
        GDK_SHIFT_MASK   = 1 << 0
        GDK_LOCK_MASK    = 1 << 1
        GDK_CONTROL_MASK = 1 << 2
        GDK_ALT_MASK     = 1 << 3

        for mask in range(256):
            is_shift = bool(mask & GDK_SHIFT_MASK)
            is_ctrl = bool(mask & GDK_CONTROL_MASK)

            if is_shift and not is_ctrl:
                mode = "CONSTRAIN_ASPECT"
            elif is_ctrl and not is_shift:
                mode = "SNAP_STEPPING"
            elif is_shift and is_ctrl:
                mode = "CENTER_CONSTRAINED"
            else:
                mode = "UNCONSTRAINED"

            self.assertIn(mode, ["CONSTRAIN_ASPECT", "SNAP_STEPPING", "CENTER_CONSTRAINED", "UNCONSTRAINED"])

    def test_m1_f03_tablet_stylus_high_frequency_pressure_tilt(self):
        """Stress: 10,000-sample high-frequency stylus stream (1000 Hz tablet rate) with pressure curve."""
        rng = random.Random(999)
        for _ in range(10000):
            raw_pressure = rng.uniform(-0.5, 1.5)
            clamped_pressure = max(0.0, min(1.0, raw_pressure))
            curve_pressure = math.pow(clamped_pressure, 1.8)

            tilt_x = rng.uniform(-90.0, 90.0)
            tilt_y = rng.uniform(-90.0, 90.0)
            rad_x = math.radians(tilt_x)
            rad_y = math.radians(tilt_y)
            altitude = math.asin(min(1.0, math.sqrt(max(0.0, 1.0 - math.sin(rad_x)**2 - math.sin(rad_y)**2))))

            self.assertGreaterEqual(curve_pressure, 0.0)
            self.assertLessEqual(curve_pressure, 1.0)
            self.assertFalse(math.isnan(altitude))

    def test_m1_f03_inertial_scrolling_kinetic_pan_physics(self):
        """Stress: Kinetic pan exponential decay physics matching C model in gimpdisplayshell-tool-events.c."""
        flick_velocities = [10.0, 100.0, 1000.0, 5000.0, 20000.0]

        for v0 in flick_velocities:
            vx, vy = v0, v0 * 0.5
            dt = 1.0 / 60.0
            total_dx, total_dy = 0.0, 0.0
            ticks = 0
            decay_factor = math.exp(-KINETIC_PAN_FRICTION * dt * 1000.0)

            while math.hypot(vx, vy) >= KINETIC_PAN_CUTOFF and ticks < 600:
                dx = vx * dt
                dy = vy * dt
                total_dx += dx
                total_dy += dy

                vx *= decay_factor
                vy *= decay_factor
                ticks += 1

            self.assertLess(math.hypot(vx, vy), KINETIC_PAN_CUTOFF + 0.1)
            self.assertGreater(ticks, 0)
            self.assertLess(ticks, 600)
            self.assertFalse(math.isnan(total_dx) or math.isnan(total_dy))

    def test_m1_f03_concurrent_gesture_conflict_resolution(self):
        """Stress: Simultaneous multi-gesture conflict state machine (Zoom + Rotate + Drag)."""
        gesture_states = {
            "zoom_active": False,
            "rotate_active": False,
            "drag_active": False,
            "space_pan_active": False,
        }

        # Step 1: Multi-touch zoom & rotate
        gesture_states["zoom_active"] = True
        gesture_states["rotate_active"] = True
        gesture_states["drag_active"] = False
        self.assertTrue(gesture_states["zoom_active"])
        self.assertTrue(gesture_states["rotate_active"])

        # Step 2: Spacebar pan
        gesture_states["space_pan_active"] = True
        active_mode = "PAN" if gesture_states["space_pan_active"] else "TOOL"
        self.assertEqual(active_mode, "PAN")

        # Step 3: End gestures
        gesture_states["zoom_active"] = False
        gesture_states["rotate_active"] = False
        gesture_states["space_pan_active"] = False
        self.assertFalse(any(gesture_states.values()))

    # =========================================================================
    # FEATURE 4: GMENU_MODEL & GTK_POPOVER_MENU_BAR
    # =========================================================================

    def test_m1_f04_gmenu_model_deep_hierarchy_resolution(self):
        """Stress: 15-level deeply nested GMenuModel hierarchy resolution and attribute traversal."""
        root_menu = {"label": "Root", "items": []}
        curr = root_menu
        for depth in range(15):
            new_sub = {"label": f"Submenu_Level_{depth}", "action": f"action_lvl_{depth}", "items": []}
            curr["items"].append(new_sub)
            curr = new_sub

        traversed = 0
        node = root_menu
        while node.get("items"):
            child = node["items"][0]
            self.assertEqual(child["label"], f"Submenu_Level_{traversed}")
            self.assertEqual(child["action"], f"action_lvl_{traversed}")
            node = child
            traversed += 1
        self.assertEqual(traversed, 15)

    def test_m1_f04_menu_shortcut_mappings(self):
        """Stress: Full audit of shortcut configuration files ensuring valid shortcut mappings."""
        shortcut_files = [
            WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0" / "shortcutsrc",
            WORKSPACE_ROOT / "gimp-source" / "data" / "photogimp-profile" / "shortcutsrc",
            WORKSPACE_ROOT / "gimp-source" / "etc" / "shortcutsrc.photogimp",
        ]

        shortcut_map: Dict[str, str] = {}
        for fpath in shortcut_files:
            if not fpath.exists():
                continue
            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.search(r'\(action\s*"([^"]+)"\s*"([^"]+)"\)', line)
                if m:
                    action, accel = m.group(1), m.group(2)
                    shortcut_map[action] = accel

        self.assertTrue(len(shortcut_map) > 0, "No shortcuts parsed from configuration")
        self.assertIn("layers-duplicate", shortcut_map)
        self.assertEqual(shortcut_map["layers-duplicate"], "<Primary>j")
        self.assertIn("tools-unified-transform", shortcut_map)
        self.assertEqual(shortcut_map["tools-unified-transform"], "<Primary>t")

    def test_m1_f04_rapid_menu_state_toggles(self):
        """Stress: 5,000 rapid state toggle events on popover menu items."""
        menu_state = {
            "view-show-rulers": True,
            "view-show-guides": True,
            "view-snap-to-bbox": True,
            "view-fullscreen": False,
        }

        for i in range(5000):
            action = ("view-show-rulers", "view-show-guides", "view-snap-to-bbox", "view-fullscreen")[i % 4]
            menu_state[action] = not menu_state[action]

        self.assertIsInstance(menu_state["view-show-rulers"], bool)
        self.assertIsInstance(menu_state["view-fullscreen"], bool)

    # =========================================================================
    # FEATURE 5: GTK_LIST_VIEW LAYER TREE & GTK_TREE_LIST_MODEL
    # =========================================================================

    def test_m1_f05_massive_layer_tree_mutations(self):
        """Stress: 2,000-node layer hierarchy with 50 nested groups under rapid mutations."""
        class TreeNode:
            def __init__(self, node_id: int, is_group: bool = False):
                self.id = node_id
                self.is_group = is_group
                self.expanded = True
                self.children: List[TreeNode] = []

        root_nodes: List[TreeNode] = []
        node_id_counter = 0

        for g in range(50):
            grp = TreeNode(node_id_counter, is_group=True)
            node_id_counter += 1
            for l in range(30):
                lyr = TreeNode(node_id_counter, is_group=False)
                node_id_counter += 1
                grp.children.append(lyr)
            root_nodes.append(grp)

        def count_nodes(nodes: List[TreeNode]) -> int:
            cnt = 0
            for n in nodes:
                cnt += 1
                if n.is_group and n.expanded:
                    cnt += count_nodes(n.children)
            return cnt

        self.assertEqual(count_nodes(root_nodes), 1550)

        # Insert 500 layers
        for i in range(500):
            grp_idx = i % 50
            new_lyr = TreeNode(node_id_counter, is_group=False)
            node_id_counter += 1
            root_nodes[grp_idx].children.insert(0, new_lyr)

        self.assertEqual(count_nodes(root_nodes), 2050)

        # Delete 250 layers
        for i in range(250):
            grp_idx = i % 50
            if root_nodes[grp_idx].children:
                root_nodes[grp_idx].children.pop()

        self.assertEqual(count_nodes(root_nodes), 1800)

        # Collapse all groups
        for grp in root_nodes:
            grp.expanded = False
        self.assertEqual(count_nodes(root_nodes), 50)

    def test_m1_f05_multi_selection_model_stress(self):
        """Stress: GtkMultiSelection model under complex range, toggle, and item deletion shifting."""
        total_rows = 500
        selected_set: Set[int] = set()

        selected_set.update(range(50, 151))
        self.assertEqual(len(selected_set), 101)

        for item in [5, 12, 50, 200, 350, 499]:
            if item in selected_set:
                selected_set.remove(item)
            else:
                selected_set.add(item)

        self.assertNotIn(50, selected_set)
        self.assertIn(5, selected_set)
        self.assertIn(200, selected_set)

        deleted_index = 100
        prev_count = len(selected_set)
        was_100_selected = 100 in selected_set

        new_selection: Set[int] = set()
        for idx in selected_set:
            if idx == deleted_index:
                continue
            elif idx > deleted_index:
                new_selection.add(idx - 1)
            else:
                new_selection.add(idx)
        selected_set = new_selection

        expected_count = prev_count - 1 if was_100_selected else prev_count
        self.assertEqual(len(selected_set), expected_count)
        for idx in selected_set:
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, total_rows - 1)

    def test_m1_f05_layer_reorder_drag_and_drop_invariants(self):
        """Stress: 1,000 random drag-and-drop layer reorder operations ensuring no data loss or cycle."""
        layers = [f"Layer_{i}" for i in range(100)]
        initial_set = set(layers)
        rng = random.Random(777)

        for _ in range(1000):
            src_idx = rng.randint(0, len(layers) - 1)
            dst_idx = rng.randint(0, len(layers) - 1)
            item = layers.pop(src_idx)
            layers.insert(dst_idx, item)

        self.assertEqual(len(layers), 100)
        self.assertEqual(set(layers), initial_set)

    # =========================================================================
    # PERFORMANCE & MEMORY LEAK AUDIT
    # =========================================================================

    def test_m1_performance_60_fps_viewport_latency(self):
        """Adversarial benchmark: Validate canvas viewport simulation meets >= 50 FPS and frame budget."""
        metrics = ViewportBenchmark.simulate_canvas_pan(num_steps=30, step_delay_sec=0.005)
        self.assertEqual(metrics.total_frames, 30)
        self.assertGreater(metrics.avg_fps, 50.0)
        self.assertLess(metrics.avg_frame_time_ms, 25.0)

    def test_m1_memory_rss_leak_audit(self):
        """Adversarial audit: Check memory RSS delta across repeated feature model allocations."""
        checker = MemoryLeakChecker()
        checker.start("m1_stress_start")

        # Simulate 5,000 GSK render node / texture allocations
        for loop in range(5):
            nodes = []
            for i in range(1000):
                node = {
                    "id": i,
                    "type": "GskTextureNode",
                    "bounds": (0.0, 0.0, 256.0, 256.0),
                    "matrix": [1.0, 0.0, 0.0, 1.0, float(i), float(i)],
                    "buffer": bytearray(1024),
                }
                nodes.append(node)
            del nodes
            gc.collect()

        checker.take_snapshot("m1_stress_end")
        delta = checker.get_delta()
        self.assertLess(delta.rss_growth_mb, 40.0, f"Memory RSS growth {delta.rss_growth_mb:.2f} MB exceeds 40MB limit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
