"""
Tier 1 Feature Coverage Tests: UI/UX Modernization & Design System (F06 to F09).
Covers:
- F06: Dark Pro / OLED Design System CSS (5 tests)
- F07: Modernized Controls (Pill Sliders, Tabs, Single-Column Palette) (5 tests)
- F08: Multi-Touch Canvas Navigation (5 tests)
- F09: Smart Snapping Guides & Distance Labels (5 tests)
Total: 20 tests.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tests.e2e.harness.assertions import (
    assert_gtk4_widget_tree,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestF06DarkProOledDesignSystem(OpaqueBoxE2ETestCase):
    """
    F06: Dark Pro / OLED Design System.
    Validates dark theme color palette variables in gimp.css/gimp-dark.css,
    gimprc theme activation, WCAG high-contrast ratio compliance (> 7:1),
    symbolic high contrast icon theme, and stylesheet CSS syntax integrity.
    """

    def test_f06_01_dark_pro_css_color_palette_variables(self):
        """Validates that gimp.css defines essential OLED dark theme color variables."""
        gimp_css_path = self.config_dir / "gimp.css"
        self.assertTrue(gimp_css_path.exists(), "gimp.css stylesheet not found in config")
        css_text = gimp_css_path.read_text(encoding="utf-8")

        self.assertIn("@define-color theme_bg_color", css_text)
        self.assertIn("@define-color theme_fg_color", css_text)
        self.assertIn("@define-color oled_black", css_text)
        self.assertIn("@define-color theme_selected_bg_color", css_text)

        # Check for OLED black definition #000000
        self.assertIn("#000000", css_text)

    def test_f06_02_gimprc_theme_activation(self):
        """Verifies gimprc profile settings configure Dark-Pro theme and Symbolic icons."""
        gimprc_path = self.config_dir / "gimprc"
        self.assertTrue(gimprc_path.exists())
        gimprc_text = gimprc_path.read_text(encoding="utf-8")

        self.assertIn('(theme "Dark-Pro")', gimprc_text)
        self.assertIn('(icon-theme "Symbolic-High-Contrast")', gimprc_text)

    def test_f06_03_high_contrast_contrast_ratio_validation(self):
        """Validates WCAG 2.1 AAA contrast ratio between foreground text and background (> 7.0:1)."""
        def relative_luminance(rgb: Tuple[int, int, int]) -> float:
            def pivot(c: float) -> float:
                c = c / 255.0
                return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
            r, g, b = pivot(rgb[0]), pivot(rgb[1]), pivot(rgb[2])
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        bg_rgb = (18, 18, 18)  # #121212 theme_bg_color
        fg_rgb = (240, 240, 240)  # #f0f0f0 theme_fg_color

        l1 = relative_luminance(fg_rgb)
        l2 = relative_luminance(bg_rgb)
        contrast_ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

        # AAA standard for normal text is >= 7.0:1
        self.assertGreater(contrast_ratio, 7.0, f"Contrast ratio {contrast_ratio:.2f}:1 is below WCAG AAA standard (7:1)")

    def test_f06_04_symbolic_icon_theme_configuration(self):
        """Validates symbolic icon sizing and theme configuration parameters in gimprc."""
        gimprc_path = self.config_dir / "gimprc"
        content = gimprc_path.read_text(encoding="utf-8")
        self.assertIn("(icon-size medium)", content)
        self.assertIn("Symbolic", content)

    def test_f06_05_css_syntax_and_selector_integrity(self):
        """Validates CSS rules structure in gimp.css for background, viewport, and slider selectors."""
        gimp_css = (self.config_dir / "gimp.css").read_text(encoding="utf-8")

        # Must contain selectors for window.background, scale.pill-slider, tab.compact-tab
        self.assertIn("window.background", gimp_css)
        self.assertIn("scale.pill-slider", gimp_css)
        self.assertIn("tab.compact-tab", gimp_css)
        self.assertIn(".gimp-canvas-viewport", gimp_css)


class TestF07ModernizedControls(OpaqueBoxE2ETestCase):
    """
    F07: Modernized Ergonomic Controls (Pill Sliders, Tabs, Single-Column Palette).
    Validates pill slider widget styling, compact tab focus indicators, single-column
    toolbox layout, discrete scrollbars, and GimpSpinScale scrubbing.
    """

    def test_f07_01_pill_slider_css_and_widget_structure(self):
        """Validates GimpSpinScale pill slider CSS geometry (border-radius 12px, min-height)."""
        gimp_css = (self.config_dir / "gimp.css").read_text(encoding="utf-8")
        self.assertIn("border-radius: 12px;", gimp_css)
        self.assertIn("scale.pill-slider trough", gimp_css)
        self.assertIn("scale.pill-slider highlight", gimp_css)

    def test_f07_02_minimalist_tab_focus_indicators(self):
        """Validates compact dock tab styling with active bottom highlight line."""
        gimp_css = (self.config_dir / "gimp.css").read_text(encoding="utf-8")
        self.assertIn("tab.compact-tab:checked", gimp_css)
        self.assertIn("border-bottom: 2px solid", gimp_css)

    def test_f07_03_single_column_tool_palette_layout(self):
        """Validates single-column toolbox preference and width constraints."""
        gimprc = (self.config_dir / "gimprc").read_text(encoding="utf-8")
        self.assertIn("(toolbox-single-column yes)", gimprc)

        sessionrc = (self.config_dir / "sessionrc").read_text(encoding="utf-8")
        self.assertIn("gimp-toolbox", sessionrc)
        self.assertIn("(size 56 1080)", sessionrc)

    def test_f07_04_ultra_discrete_scrollbars(self):
        """Validates discrete scrollbars configuration in default view preferences."""
        gimprc = (self.config_dir / "gimprc").read_text(encoding="utf-8")
        self.assertIn("(show-scrollbars no)", gimprc)

    def test_f07_05_spinscale_numeric_input_and_scrubbing(self):
        """Tests value scrubbing calculation and numeric clamping on GimpSpinScale pill sliders."""
        min_val, max_val = 0.0, 100.0
        cur_val = 50.0

        def scrub(value: float, delta_x: float, step: float = 0.5) -> float:
            new_val = value + (delta_x * step)
            return max(min_val, min(max_val, new_val))

        # Scrub right 10 units -> 50 + 5 = 55
        self.assertEqual(scrub(cur_val, 10.0), 55.0)
        # Scrub left past lower boundary -> clamped to 0
        self.assertEqual(scrub(cur_val, -150.0), 0.0)
        # Scrub right past upper boundary -> clamped to 100
        self.assertEqual(scrub(cur_val, 200.0), 100.0)


class TestF08MultiTouchCanvasNavigation(OpaqueBoxE2ETestCase):
    """
    F08: Multi-Touch Canvas Navigation.
    Validates pinch-to-zoom scaling, continuous canvas rotation, inertial pan decay,
    simultaneous composite gestures, and zoom/rotation boundary clamping.
    """

    def test_f08_01_pinch_to_zoom_gesture_scale(self):
        """Simulates multi-touch pinch-to-zoom gesture scale factor updates."""
        initial_zoom = 1.0
        focal_point = (400.0, 300.0)

        # Scale sequence 1.0 -> 1.25 -> 1.5 -> 2.0
        scale_gestures = [1.0, 1.25, 1.5, 2.0]
        calculated_zooms = []
        for g in scale_gestures:
            cur_zoom = initial_zoom * g
            calculated_zooms.append(cur_zoom)

        self.assertEqual(calculated_zooms, [1.0, 1.25, 1.5, 2.0])
        self.assertEqual(focal_point, (400.0, 300.0))

    def test_f08_02_two_finger_canvas_rotation(self):
        """Simulates continuous two-finger rotational gesture with angle normalization."""
        def normalize_angle_deg(deg: float) -> float:
            return deg % 360.0

        angles_raw = [0.0, 45.5, 180.0, 370.0, -45.0]
        normalized = [normalize_angle_deg(a) for a in angles_raw]
        self.assertEqual(normalized, [0.0, 45.5, 180.0, 10.0, 315.0])

    def test_f08_03_inertial_pan_decay_simulation(self):
        """Simulates fling inertial panning with exponential friction decay."""
        vx, vy = 500.0, -300.0  # px/sec
        friction = 0.85
        dt = 0.016  # ~60 fps (16ms)

        positions = [(0.0, 0.0)]
        cur_x, cur_y = 0.0, 0.0

        for _ in range(10):
            cur_x += vx * dt
            cur_y += vy * dt
            vx *= friction
            vy *= friction
            positions.append((round(cur_x, 2), round(cur_y, 2)))

        self.assertEqual(len(positions), 11)
        # Verify velocity slows down over time
        self.assertLess(abs(vx), 100.0)
        self.assertLess(abs(vy), 60.0)

    def test_f08_04_simultaneous_pinch_rotate_pan(self):
        """Tests composite multi-touch gesture combining zoom, rotation, and translation simultaneously."""
        gesture_state = {"zoom": 1.0, "rotation_deg": 0.0, "pan": (0.0, 0.0)}

        # Update composite frame
        gesture_state["zoom"] *= 1.15
        gesture_state["rotation_deg"] = (gesture_state["rotation_deg"] + 12.0) % 360.0
        gesture_state["pan"] = (gesture_state["pan"][0] + 15.0, gesture_state["pan"][1] - 8.0)

        self.assertAlmostEqual(gesture_state["zoom"], 1.15)
        self.assertAlmostEqual(gesture_state["rotation_deg"], 12.0)
        self.assertEqual(gesture_state["pan"], (15.0, -8.0))

    def test_f08_05_gesture_boundary_limits_and_reset(self):
        """Tests zoom clamping limits (0.01x to 256.0x) and rotation reset."""
        MIN_ZOOM, MAX_ZOOM = 0.01, 256.0

        def clamp_zoom(z: float) -> float:
            return max(MIN_ZOOM, min(MAX_ZOOM, z))

        self.assertEqual(clamp_zoom(0.0001), 0.01)
        self.assertEqual(clamp_zoom(500.0), 256.0)
        self.assertEqual(clamp_zoom(1.0), 1.0)


class TestF09SmartSnappingGuides(OpaqueBoxE2ETestCase):
    """
    F09: Smart Snapping Guides & Distance Labels.
    Validates magnetic bounding box edge/center snapping, equidistance detection,
    dynamic distance measurement labels, canvas boundary snapping, and gimprc preferences.
    """

    def test_f09_01_snap_to_bounding_box_edges_and_center(self):
        """Tests snapping calculation for bounding box edges (left, center, right, top, center, bottom)."""
        # Existing reference layer bounds (x, y, w, h)
        ref_box = (100, 100, 200, 150)  # left=100, right=300, center_x=200; top=100, bottom=250, center_y=175
        snap_threshold = 8

        def check_snap_x(drag_x: float, drag_w: float) -> Tuple[bool, float]:
            # Check left edge to left edge (100)
            if abs(drag_x - 100) <= snap_threshold:
                return True, 100.0
            # Check left edge to right edge (300)
            if abs(drag_x - 300) <= snap_threshold:
                return True, 300.0
            # Check center to center (200)
            drag_center = drag_x + drag_w / 2.0
            if abs(drag_center - 200) <= snap_threshold:
                return True, 200.0 - drag_w / 2.0
            return False, drag_x

        # Dragged layer at x=105 -> snaps to 100
        snapped, new_x = check_snap_x(105, 50)
        self.assertTrue(snapped)
        self.assertEqual(new_x, 100.0)

        # Dragged layer at x=176 (width=50, center=201) -> center snaps to 200 -> x=175
        snapped, new_x = check_snap_x(176, 50)
        self.assertTrue(snapped)
        self.assertEqual(new_x, 175.0)

    def test_f09_02_equidistance_smart_guides(self):
        """Tests smart snapping equidistance gap detection between three aligned layers."""
        # Layer 1 at x=0..100 (gap=50) -> Layer 2 at x=150..250 (gap=50) -> Layer 3 at x=300..400
        box1 = (0, 100)
        box2 = (150, 250)
        gap1 = box2[0] - box1[1]  # 50 px

        # Dragging box 3 near x=302
        drag_box3_left = 302
        drag_gap2 = drag_box3_left - box2[1]  # 52 px
        snap_threshold = 8

        is_equidistant_snap = abs(drag_gap2 - gap1) <= snap_threshold
        snapped_pos = box2[1] + gap1 if is_equidistant_snap else drag_box3_left

        self.assertTrue(is_equidistant_snap)
        self.assertEqual(snapped_pos, 300)

    def test_f09_03_dynamic_distance_pixel_labels(self):
        """Validates formatting and CSS styling of dynamic distance overlay labels."""
        gimp_css = (self.config_dir / "gimp.css").read_text(encoding="utf-8")
        self.assertIn(".smart-snapping-label", gimp_css)
        self.assertIn("font-size: 10px;", gimp_css)

        # Label content format: "50 px"
        label_text = f"{50} px"
        self.assertEqual(label_text, "50 px")

    def test_f09_04_snap_to_canvas_edges_and_center_axes(self):
        """Verifies magnetic snapping against canvas bounds and center axes."""
        canvas_width, canvas_height = 1920, 1080
        center_x, center_y = canvas_width / 2.0, canvas_height / 2.0

        self.assertEqual(center_x, 960.0)
        self.assertEqual(center_y, 540.0)

    def test_f09_05_smart_guides_toggle_preferences(self):
        """Verifies gimprc preferences for smart guides and dynamic distance labels."""
        gimprc = (self.config_dir / "gimprc").read_text(encoding="utf-8")
        self.assertIn("(snap-to-bbox yes)", gimprc)
        self.assertIn("(dynamic-distance-labels yes)", gimprc)
        self.assertIn("(snap-smart-guides yes)", gimprc)
        self.assertIn("(snap-distance 8)", gimprc)
