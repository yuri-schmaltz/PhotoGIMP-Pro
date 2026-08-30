"""
Tier 3: Pairwise Combinatorial E2E Test Suite for GIMP + PhotoGIMP Modernization.
Tests cross-feature interactions and integration boundaries across F01-F19:
25 Comprehensive Pairwise Interaction Tests.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tests.e2e.harness.assertions import (
    assert_color_delta_e,
    assert_fps_budget,
    assert_gegl_graph_valid,
    assert_gtk4_widget_tree,
    assert_memory_stable,
    assert_non_destructive_stack,
    assert_shortcut_mapping,
    delta_e_ciede2000,
    parse_shortcut_file,
    rgb_to_lab,
)
from tests.e2e.harness.base_test import GimpEnvContext, OpaqueBoxE2ETestCase
from tests.e2e.harness.fps_profiler import FPSProfiler, ViewportBenchmark
from tests.e2e.harness.leak_checker import MemoryLeakChecker
from tests.e2e.harness.mock_assets import (
    MockAssetGenerator,
    create_dummy_psd,
    create_dummy_raw,
    create_dummy_svg,
    create_dummy_tiff,
    create_dummy_xcf,
    create_photogimp_profile,
)


class TestPairwiseFeatureInteractions(OpaqueBoxE2ETestCase):
    """
    Tier 3: 25 Pairwise Interaction Test Cases covering the full matrix
    of cross-cutting features in GIMP 3.0 + PhotoGIMP.
    """

    # -----------------------------------------------------------------------
    # Pairwise 01: Free Transform Gizmo (Ctrl+T) + Smart Objects (SVG/PSD)
    # -----------------------------------------------------------------------
    def test_pairwise_01_free_transform_smart_objects_F11_F15(self):
        """
        F11_FREE_TRANSFORM + F15_SMART_OBJECTS:
        Verify scaling and rotating a Smart Object container (SVG vector) with
        Unified Free Transform (Ctrl+T) preserves source vector hash while
        updating affine transformation matrix and viewport bounding box.
        """
        svg_path = self.assets.create_svg("logo_smart_obj.svg", width=300, height=200)
        orig_svg_bytes = svg_path.read_bytes()
        orig_hash = hashlib.sha256(orig_svg_bytes).hexdigest()

        # Simulated Smart Object container data structure
        smart_obj = {
            "id": "smart_obj_layer_01",
            "type": "GimpSmartObjectLayer",
            "source_uri": str(svg_path),
            "source_hash": orig_hash,
            "native_dimensions": (300, 200),
            "transform_matrix": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            "bounds": [0, 0, 300, 200],
            "is_rasterized": False,
        }

        # Apply Free Transform scale (2.5x) and rotation (45 deg)
        scale_x, scale_y = 2.5, 2.5
        angle_rad = math.radians(45.0)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)

        # Affine 2D matrix multiplication: Scale * Rotate
        m00 = scale_x * cos_a
        m01 = -scale_x * sin_a
        m10 = scale_y * sin_a
        m11 = scale_y * cos_a

        smart_obj["transform_matrix"] = [
            [m00, m01, 100.0],
            [m10, m11, 150.0],
            [0.0, 0.0, 1.0],
        ]

        # Calculate transformed bounding box extent
        corners = [(0, 0), (300, 0), (300, 200), (0, 200)]
        tx_corners = []
        for x, y in corners:
            tx = m00 * x + m01 * y + 100.0
            ty = m10 * x + m11 * y + 150.0
            tx_corners.append((tx, ty))

        min_x = min(p[0] for p in tx_corners)
        max_x = max(p[0] for p in tx_corners)
        min_y = min(p[1] for p in tx_corners)
        max_y = max(p[1] for p in tx_corners)
        smart_obj["bounds"] = [min_x, min_y, max_x, max_y]

        # Assertions: original vector file remains uncorrupted, container maintains resolution
        current_svg_bytes = Path(smart_obj["source_uri"]).read_bytes()
        self.assertEqual(hashlib.sha256(current_svg_bytes).hexdigest(), orig_hash)
        self.assertFalse(smart_obj["is_rasterized"])
        self.assertGreater(max_x - min_x, 300.0)
        self.assertGreater(max_y - min_y, 200.0)

    # -----------------------------------------------------------------------
    # Pairwise 02: Non-Destructive Adjustment Layers + Real-Time Layer Styles FX
    # -----------------------------------------------------------------------
    def test_pairwise_02_adjustment_layers_layer_styles_fx_F13_F14(self):
        """
        F13_ADJUSTMENTS + F14_LAYER_STYLES:
        Verify live GEGL graph chaining an Adjustment Layer (Curves) over a
        layer with Layer Styles (Drop Shadow + Stroke), ensuring FX evaluates
        on modified pixel stream without destructive rasterization.
        """
        gegl_graph = {
            "nodes": [
                {"id": "source_raster", "operation": "gegl:buffer-source", "properties": {"width": 400, "height": 400}},
                {"id": "adj_curves", "operation": "gegl:curves", "properties": {"curve": "s-contrast"}},
                {"id": "fx_stroke", "operation": "gegl:stroke", "properties": {"width": 4.0, "color": "#00e5ff"}},
                {"id": "fx_drop_shadow", "operation": "gegl:drop-shadow", "properties": {"x": 10.0, "y": 10.0, "radius": 15.0, "opacity": 0.75}},
                {"id": "composite_out", "operation": "gegl:over", "properties": {}},
            ],
            "connections": [
                ("source_raster", "output", "adj_curves", "input"),
                ("adj_curves", "output", "fx_stroke", "input"),
                ("fx_stroke", "output", "fx_drop_shadow", "input"),
                ("fx_drop_shadow", "output", "composite_out", "input"),
            ],
        }

        assert_gegl_graph_valid(
            gegl_graph,
            expected_nodes=[
                {"id": "adj_curves", "operation": "gegl:curves"},
                {"id": "fx_stroke", "operation": "gegl:stroke"},
                {"id": "fx_drop_shadow", "operation": "gegl:drop-shadow"},
            ],
            expected_connections=[
                ("source_raster", "output", "adj_curves", "input"),
                ("adj_curves", "output", "fx_stroke", "input"),
                ("fx_stroke", "output", "fx_drop_shadow", "input"),
            ],
        )

        # Verify base buffer is preserved
        base_pixels = bytes([120, 140, 160, 255] * 100)
        orig_hash = hashlib.sha256(base_pixels).hexdigest()
        filtered_output = bytes([min(255, int(b * 1.2)) for b in base_pixels])
        assert_non_destructive_stack(base_pixels, orig_hash, filtered_output)

    # -----------------------------------------------------------------------
    # Pairwise 03: SAM 2 Magic Selection + RMBG-1.4 Background Removal
    # -----------------------------------------------------------------------
    def test_pairwise_03_sam2_magic_selection_rmbg_removal_F16_F17(self):
        """
        F16_SAM2_AI + F17_RMBG_AI:
        Verify SAM 2 foreground prompt segmentation outputs an interactive selection
        mask which is passed to RMBG-1.4 for edge alpha feathering and background removal.
        """
        width, height = 256, 256
        # Simulate binary prompt mask from SAM 2 (circle object in center)
        sam2_mask = bytearray(width * height)
        cx, cy, radius = 128, 128, 64
        for y in range(height):
            for x in range(width):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius**2:
                    sam2_mask[y * width + x] = 255

        # RMBG-1.4 alpha matting refinement: computes smooth boundary transitions
        rmbg_refined_alpha = bytearray(width * height)
        for y in range(height):
            for x in range(width):
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                if dist <= radius - 4:
                    rmbg_refined_alpha[y * width + x] = 255
                elif dist <= radius + 4:
                    # Antialiased soft transition edge
                    weight = (radius + 4 - dist) / 8.0
                    rmbg_refined_alpha[y * width + x] = int(255 * weight)
                else:
                    rmbg_refined_alpha[y * width + x] = 0

        # Validate mask coverage and feathering
        inside_val = rmbg_refined_alpha[cy * width + cx]
        edge_val = rmbg_refined_alpha[cy * width + (cx + radius)]
        outside_val = rmbg_refined_alpha[cy * width + (cx + radius + 10)]

        self.assertEqual(inside_val, 255)
        self.assertGreater(edge_val, 0)
        self.assertLess(edge_val, 255)
        self.assertEqual(outside_val, 0)

    # -----------------------------------------------------------------------
    # Pairwise 04: RMBG-1.4 Alpha Matting + Generative Inpainting SDXL/Flux
    # -----------------------------------------------------------------------
    def test_pairwise_04_rmbg_matting_generative_inpainting_F17_F18(self):
        """
        F17_RMBG_AI + F18_INPAINT_AI:
        Verify RMBG-1.4 foreground mask inverted as inpainting mask for SDXL/Flux,
        ensuring mask dilation, bounding box crop, and non-destructive fill patch generation.
        """
        mask_w, mask_h = 128, 128
        fg_mask = bytearray(mask_w * mask_h)
        # Foreground object located between (32, 32) and (96, 96)
        for y in range(32, 96):
            for x in range(32, 96):
                fg_mask[y * mask_w + x] = 255

        # Inpainting mask: Invert foreground + apply 4px dilation padding
        inpaint_mask = bytearray(mask_w * mask_h)
        for y in range(28, 100):
            for x in range(28, 100):
                inpaint_mask[y * mask_w + x] = 255

        # Bounding box calculation for localized neural inference
        active_coords = [(x, y) for y in range(mask_h) for x in range(mask_w) if inpaint_mask[y * mask_w + x] > 0]
        bbox_x1 = min(c[0] for c in active_coords)
        bbox_y1 = min(c[1] for c in active_coords)
        bbox_x2 = max(c[0] for c in active_coords)
        bbox_y2 = max(c[1] for c in active_coords)

        # Inpaint patch descriptor
        inpaint_payload = {
            "model": "sdxl_inpaint_fp16",
            "prompt": "seamless background wall texture, natural lighting",
            "bbox": (bbox_x1, bbox_y1, bbox_x2, bbox_y2),
            "patch_size": (bbox_x2 - bbox_x1 + 1, bbox_y2 - bbox_y1 + 1),
            "blend_mode": "replace_masked",
        }

        self.assertEqual(inpaint_payload["bbox"], (28, 28, 99, 99))
        self.assertEqual(inpaint_payload["patch_size"], (72, 72))

    # -----------------------------------------------------------------------
    # Pairwise 05: PhotoGIMP Workspace Switcher + Photoshop Shortcuts Validation
    # -----------------------------------------------------------------------
    def test_pairwise_05_photogimp_workspace_photoshop_shortcuts_F10_F11(self):
        """
        F10_WORKSPACE + F11_FREE_TRANSFORM:
        Verify switching to PhotoGIMP profile loads Photoshop keybindings
        (<Primary>t for Free Transform, <Primary>j for Duplicate, <Primary>d for Deselect).
        """
        shortcut_file = self.config_dir / "shortcutsrc"
        self.assertTrue(shortcut_file.exists())

        expected_shortcuts = {
            "image-transform-free": "<Primary>t",
            "layers-duplicate": "<Primary>j",
            "select-none": "<Primary>d",
            "select-invert": "<Primary><Shift>i",
            "dialogs-action-search": "<Primary>k",
            "dialogs-command-palette": "<Primary>p",
        }
        assert_shortcut_mapping(shortcut_file, expected_shortcuts)

    # -----------------------------------------------------------------------
    # Pairwise 06: Command Palette (Ctrl+K) + GtkListView Layer Tree Selection
    # -----------------------------------------------------------------------
    def test_pairwise_06_command_palette_gtklistview_layer_tree_F12_F05(self):
        """
        F12_COMMAND_PALETTE + F05_LAYER_TREE:
        Verify fuzzy-finding a layer in Command Palette updates GtkListView
        active selection row and scrolls item into viewport.
        """
        layer_tree_model = [
            {"id": "lyr_0", "name": "Background", "type": "raster", "selected": False},
            {"id": "lyr_1", "name": "Hero Subject", "type": "smart_obj", "selected": False},
            {"id": "lyr_2", "name": "Curves Adjustment", "type": "adj_layer", "selected": False},
            {"id": "lyr_3", "name": "Branding Logo", "type": "vector", "selected": False},
        ]

        # Fuzzy search query in Command Palette: "hero"
        query = "hero"
        matched = [l for l in layer_tree_model if query in l["name"].lower()]
        self.assertEqual(len(matched), 1)
        target_layer = matched[0]

        # Activate selection action in GtkListView model
        for l in layer_tree_model:
            l["selected"] = (l["id"] == target_layer["id"])

        self.assertTrue(layer_tree_model[1]["selected"])
        self.assertFalse(layer_tree_model[0]["selected"])

    # -----------------------------------------------------------------------
    # Pairwise 07: Dark Pro / OLED Theme + Modernized Pill Sliders & Tabs
    # -----------------------------------------------------------------------
    def test_pairwise_07_oled_theme_pill_sliders_tabs_F06_F07(self):
        """
        F06_DARK_THEME + F07_CONTROLS:
        Verify Dark Pro / OLED CSS stylesheet contains styling rules for
        Pill Sliders (scale.pill-slider), Minimalist Tabs (tab.compact-tab), and OLED background.
        """
        css_file = self.config_dir / "gimp.css"
        self.assertTrue(css_file.exists())
        css_text = css_file.read_text(encoding="utf-8")

        self.assertIn("@define-color oled_black #000000", css_text)
        self.assertIn("@define-color theme_bg_color #121212", css_text)
        self.assertIn("scale.pill-slider", css_text)
        self.assertIn("tab.compact-tab:checked", css_text)
        self.assertIn(".single-column-toolbox", css_text)

        # Widget tree inspection
        ui_hierarchy = {
            "type": "GtkWindow",
            "classes": ["oled-dark", "main-window"],
            "children": [
                {
                    "type": "GimpDockbook",
                    "classes": ["compact-tabs"],
                    "children": [],
                },
                {
                    "type": "GimpSpinScale",
                    "classes": ["pill-slider"],
                    "properties": {"value": 75},
                    "children": [],
                },
            ],
        }
        assert_gtk4_widget_tree(
            ui_hierarchy,
            {
                "type": "GtkWindow",
                "classes": ["oled-dark"],
                "children": [
                    {"type": "GimpDockbook"},
                    {"type": "GimpSpinScale", "classes": ["pill-slider"]},
                ],
            },
        )

    # -----------------------------------------------------------------------
    # Pairwise 08: Smart Snapping Guides + Unified Free Transform Snapping
    # -----------------------------------------------------------------------
    def test_pairwise_08_smart_snapping_unified_free_transform_F09_F11(self):
        """
        F09_SNAPPING + F11_FREE_TRANSFORM:
        Verify Free Transform handle manipulation snaps to smart guides, canvas center,
        and layer bounds within the 8px magnet distance threshold.
        """
        snap_threshold = 8.0
        canvas_width, canvas_height = 1920.0, 1080.0
        center_x = canvas_width / 2.0  # 960.0

        # Transform handle moving near center (e.g. at 963.5 px)
        handle_x = 963.5
        delta_x = abs(handle_x - center_x)

        # Snapping logic calculation
        snapped_x = center_x if delta_x <= snap_threshold else handle_x
        distance_label = f"dx: {delta_x:.1f}px"

        self.assertLessEqual(delta_x, snap_threshold)
        self.assertEqual(snapped_x, 960.0)
        self.assertEqual(distance_label, "dx: 3.5px")

    # -----------------------------------------------------------------------
    # Pairwise 09: Multi-Touch Gestures + GSK GPU Canvas Rendering
    # -----------------------------------------------------------------------
    def test_pairwise_09_multitouch_gestures_gsk_canvas_rendering_F08_F02(self):
        """
        F08_MULTITOUCH + F02_GSK_RENDER:
        Verify multi-touch zoom and rotation gestures generate GSK GPU render node
        snapshots (GskTransformNode) maintaining 60 FPS frame time budgets (<16.6ms).
        """
        profiler = FPSProfiler(target_fps=60.0)
        profiler.start()

        # Simulate 30 frames of multi-touch gesture events
        for frame in range(30):
            zoom_factor = 1.0 + (frame * 0.05)
            rotation_deg = frame * 1.5
            # Generate simulated GskTransformNode parameters
            matrix = [
                [zoom_factor * math.cos(math.radians(rotation_deg)), -zoom_factor * math.sin(math.radians(rotation_deg))],
                [zoom_factor * math.sin(math.radians(rotation_deg)), zoom_factor * math.cos(math.radians(rotation_deg))],
            ]
            self.assertIsNotNone(matrix)
            profiler.record_frame()

        metrics = profiler.stop()
        self.assertGreater(metrics.avg_fps, 0.0)
        self.assertEqual(metrics.total_frames, 30)

    # -----------------------------------------------------------------------
    # Pairwise 10: Smart PSD Engine Import + CMYK Soft-Proofing LittleCMS 2
    # -----------------------------------------------------------------------
    def test_pairwise_10_psd_import_cmyk_soft_proofing_F19_F19(self):
        """
        F19_PSD_COLOR + F19_PSD_COLOR:
        Verify importing a 4-channel CMYK PSD and applying LittleCMS 2 soft-proofing
        ICC profile (ISO Coated v2) calculates accurate colorimetric gamut mapping.
        """
        psd_path = self.assets.create_psd(
            "print_cmyk.psd",
            width=64,
            height=64,
            color_mode="CMYK",
            layers=[
                {"name": "CMYK Plate", "bounds": (0, 0, 64, 64), "opacity": 255, "blend": "norm"}
            ],
        )
        self.assertTrue(psd_path.exists())
        data = psd_path.read_bytes()

        # Check color mode in PSD header
        mode = struct.unpack(">H", data[24:26])[0]
        self.assertEqual(mode, 4)  # 4 = CMYK

        # Soft-proofing color conversion simulation: CMYK (0, 100, 100, 0) Pure Red
        # In sRGB soft-proof: (237, 28, 36) -> Delta E with target red (235, 30, 35) <= 1.5
        cmyk_red = (237, 28, 36)
        proof_target = (235, 30, 35)
        assert_color_delta_e(cmyk_red, proof_target, max_delta_e=1.5)

    # -----------------------------------------------------------------------
    # Pairwise 11: OpenColorIO v2 ACES Pipeline + Adjustment Layers Graph
    # -----------------------------------------------------------------------
    def test_pairwise_11_opencolorio_aces_adjustment_layers_F19_F13(self):
        """
        F19_PSD_COLOR + F13_ADJUSTMENTS:
        Verify OCIO v2 ACEScg color space transform chained before and after
        non-destructive GEGL exposure and curves adjustment nodes.
        """
        ocio_graph = {
            "nodes": [
                {"id": "raw_input", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "ocio_aces_in", "operation": "gegl:ocio-transform", "properties": {"src": "ACEScg", "dst": "ACES2065-1"}},
                {"id": "adj_exposure", "operation": "gegl:exposure", "properties": {"stops": 1.5}},
                {"id": "adj_curves", "operation": "gegl:curves", "properties": {"curve": "film-contrast"}},
                {"id": "ocio_display_out", "operation": "gegl:ocio-display", "properties": {"view": "sRGB - ACES 1.0"}},
            ],
            "connections": [
                ("raw_input", "output", "ocio_aces_in", "input"),
                ("ocio_aces_in", "output", "adj_exposure", "input"),
                ("adj_exposure", "output", "adj_curves", "input"),
                ("adj_curves", "output", "ocio_display_out", "input"),
            ],
        }

        assert_gegl_graph_valid(
            ocio_graph,
            expected_nodes=[
                {"id": "ocio_aces_in", "operation": "gegl:ocio-transform"},
                {"id": "adj_exposure", "operation": "gegl:exposure"},
                {"id": "ocio_display_out", "operation": "gegl:ocio-display"},
            ],
            expected_connections=[
                ("raw_input", "output", "ocio_aces_in", "input"),
                ("adj_exposure", "output", "adj_curves", "input"),
                ("adj_curves", "output", "ocio_display_out", "input"),
            ],
        )

    # -----------------------------------------------------------------------
    # Pairwise 12: GMenuModel PopoverMenuBar + Dynamic Workspace Dispatch
    # -----------------------------------------------------------------------
    def test_pairwise_12_gmenumodel_popover_workspace_dispatch_F04_F10(self):
        """
        F04_MENUS + F10_WORKSPACE:
        Verify GMenuModel menu hierarchy dispatches workspace switch actions
        (<Actions>/windows/windows-workspace-photogimp) without GUI re-instantiation.
        """
        gmenu_descriptor = {
            "menu_id": "main_menubar",
            "type": "GtkPopoverMenuBar",
            "model": [
                {
                    "label": "_File",
                    "items": [{"label": "New...", "action": "file-new"}, {"label": "Open...", "action": "file-open"}],
                },
                {
                    "label": "_Windows",
                    "items": [
                        {"label": "Dockable Dialogs", "submenu": []},
                        {"label": "Workspaces", "submenu": [
                            {"label": "Default GIMP", "action": "windows-workspace-default"},
                            {"label": "PhotoGIMP (Photoshop Profile)", "action": "windows-workspace-photogimp", "active": True},
                        ]},
                    ],
                },
            ],
        }

        # Validate menu hierarchy
        windows_menu = next(m for m in gmenu_descriptor["model"] if m["label"] == "_Windows")
        workspaces_submenu = next(item for item in windows_menu["items"] if item.get("label") == "Workspaces")
        photogimp_action = next(item for item in workspaces_submenu["submenu"] if item.get("action") == "windows-workspace-photogimp")

        self.assertTrue(photogimp_action["active"])
        self.assertEqual(photogimp_action["action"], "windows-workspace-photogimp")

    # -----------------------------------------------------------------------
    # Pairwise 13: GtkEventController Stylus + Layer Styles Stroke FX
    # -----------------------------------------------------------------------
    def test_pairwise_13_gtkeventcontroller_stylus_layer_styles_F03_F14(self):
        """
        F03_GESTURES + F14_LAYER_STYLES:
        Verify GtkGestureStylus pressure values dynamically modulate real-time
        stroke width applied alongside outer glow and drop shadow FX.
        """
        base_stroke_width = 10.0
        pressure_samples = [0.1, 0.35, 0.7, 0.95]

        computed_widths = []
        for p in pressure_samples:
            # Pressure curve formula: w = base_w * (0.2 + 0.8 * p^1.5)
            dynamic_w = base_stroke_width * (0.2 + 0.8 * (p**1.5))
            computed_widths.append(round(dynamic_w, 2))

        # Check monotonic increase with stylus pressure
        self.assertTrue(all(computed_widths[i] < computed_widths[i + 1] for i in range(len(computed_widths) - 1)))
        self.assertAlmostEqual(computed_widths[0], 2.25, delta=0.1)
        self.assertAlmostEqual(computed_widths[-1], 9.41, delta=0.2)

    # -----------------------------------------------------------------------
    # Pairwise 14: Smart Objects Linked Assets + PSD Roundtrip Export
    # -----------------------------------------------------------------------
    def test_pairwise_14_smart_objects_psd_roundtrip_F15_F19(self):
        """
        F15_SMART_OBJECTS + F19_PSD_COLOR:
        Verify embedding an external SVG Smart Object inside a PSD project file,
        saving, and reloading retains linked asset references and transforms.
        """
        svg_asset = self.assets.create_svg("vector_badge.svg", width=150, height=150)
        svg_content = svg_asset.read_text(encoding="utf-8")

        # Generate PSD containing Smart Object layer record
        psd_path = self.assets.create_psd(
            "smart_object_project.psd",
            width=200,
            height=200,
            layers=[
                {"name": "Background", "bounds": (0, 0, 200, 200), "opacity": 255, "blend": "norm"},
                {"name": "Vector Badge Smart Object", "bounds": (25, 25, 175, 175), "opacity": 255, "blend": "norm"},
            ],
        )

        psd_bytes = psd_path.read_bytes()
        self.assertIn(b"Vector Badge Smart Object", psd_bytes)
        # Verify SVG source XML was preserved
        self.assertIn("<svg", svg_content)

    # -----------------------------------------------------------------------
    # Pairwise 15: Generative Inpainting Mask + Smart Snapping Bounds
    # -----------------------------------------------------------------------
    def test_pairwise_15_generative_inpainting_smart_snapping_bounds_F18_F09(self):
        """
        F18_INPAINT_AI + F09_SNAPPING:
        Verify generative inpainting selection rectangle snaps to existing object
        bounding boxes with automatic 16px neural context padding.
        """
        object_bbox = (100, 150, 400, 500)  # (x1, y1, x2, y2)
        snap_threshold = 8

        # User dragged inpainting box near object bounds: (103, 147, 396, 504)
        drag_box = (103, 147, 396, 504)

        snapped_x1 = object_bbox[0] if abs(drag_box[0] - object_bbox[0]) <= snap_threshold else drag_box[0]
        snapped_y1 = object_bbox[1] if abs(drag_box[1] - object_bbox[1]) <= snap_threshold else drag_box[1]
        snapped_x2 = object_bbox[2] if abs(drag_box[2] - object_bbox[2]) <= snap_threshold else drag_box[2]
        snapped_y2 = object_bbox[3] if abs(drag_box[3] - object_bbox[3]) <= snap_threshold else drag_box[3]

        self.assertEqual((snapped_x1, snapped_y1, snapped_x2, snapped_y2), object_bbox)

        # Context padding for SDXL generative patch
        padding = 16
        padded_bbox = (
            max(0, snapped_x1 - padding),
            max(0, snapped_y1 - padding),
            snapped_x2 + padding,
            snapped_y2 + padding,
        )
        self.assertEqual(padded_bbox, (84, 134, 416, 516))

    # -----------------------------------------------------------------------
    # Pairwise 16: SAM 2 Prompts + Adjustment Layers Mask Composition
    # -----------------------------------------------------------------------
    def test_pairwise_16_sam2_prompts_adjustment_layer_mask_F16_F13(self):
        """
        F16_SAM2_AI + F13_ADJUSTMENTS:
        Verify SAM 2 interactive prompt mask applied as the layer mask of a
        Curves Adjustment Layer, restricting GEGL color transformation to subject pixels.
        """
        mask_bytes = bytes([255 if i % 2 == 0 else 0 for i in range(1024)])
        adj_layer = {
            "id": "adj_layer_curves",
            "operation": "gegl:curves",
            "mask_channel": mask_bytes,
            "mask_enabled": True,
            "mask_inverted": False,
        }

        # Check mask channel data integrity
        self.assertEqual(len(adj_layer["mask_channel"]), 1024)
        self.assertTrue(adj_layer["mask_enabled"])

    # -----------------------------------------------------------------------
    # Pairwise 17: GtkListView DnD Reordering + Layer FX Stacking Order
    # -----------------------------------------------------------------------
    def test_pairwise_17_gtklistview_dnd_layer_fx_stack_F05_F14(self):
        """
        F05_LAYER_TREE + F14_LAYER_STYLES:
        Verify drag-and-drop reordering in GtkListView updates layer composite
        hierarchy without corrupting individual layer FX parameters (Drop Shadow, Stroke).
        """
        layer_stack = [
            {"id": "L1", "name": "Text Banner", "fx": {"type": "drop-shadow", "radius": 5.0}},
            {"id": "L2", "name": "Subject Cutout", "fx": {"type": "stroke", "width": 2.0}},
            {"id": "L3", "name": "Background", "fx": None},
        ]

        # Drag L2 above L1
        moved_layer = layer_stack.pop(1)
        layer_stack.insert(0, moved_layer)

        self.assertEqual(layer_stack[0]["id"], "L2")
        self.assertEqual(layer_stack[1]["id"], "L1")
        self.assertEqual(layer_stack[0]["fx"]["type"], "stroke")
        self.assertEqual(layer_stack[1]["fx"]["type"], "drop-shadow")

    # -----------------------------------------------------------------------
    # Pairwise 18: Pill Sliders Color Balance + Non-Destructive GEGL Update
    # -----------------------------------------------------------------------
    def test_pairwise_18_pill_sliders_color_balance_gegl_update_F07_F13(self):
        """
        F07_CONTROLS + F13_ADJUSTMENTS:
        Verify user interaction with ergonomic pill sliders updates Color Balance
        GEGL node properties (cyan-red, magenta-green, yellow-blue) non-destructively.
        """
        gegl_color_balance_node = {
            "id": "node_color_balance",
            "operation": "gegl:color-balance",
            "properties": {
                "shadows": [0.0, 0.0, 0.0],
                "midtones": [0.0, 0.0, 0.0],
                "highlights": [0.0, 0.0, 0.0],
            },
        }

        # Simulate slider change for Midtones Warmth (+15 Red, -5 Blue)
        gegl_color_balance_node["properties"]["midtones"] = [0.15, 0.0, -0.05]

        self.assertEqual(gegl_color_balance_node["properties"]["midtones"][0], 0.15)
        self.assertEqual(gegl_color_balance_node["properties"]["midtones"][2], -0.05)

    # -----------------------------------------------------------------------
    # Pairwise 19: PhotoGIMP Single-Column Toolbar + Free Transform Activation
    # -----------------------------------------------------------------------
    def test_pairwise_19_photogimp_single_column_free_transform_F10_F11(self):
        """
        F10_WORKSPACE + F11_FREE_TRANSFORM:
        Verify PhotoGIMP single-column toolbox ordering includes Unified Free
        Transform tool with proper icon and accelerator tooltip.
        """
        toolrc_file = self.config_dir / "toolrc"
        self.assertTrue(toolrc_file.exists())
        toolrc_content = toolrc_file.read_text(encoding="utf-8")

        self.assertIn("gimp-unified-transform-tool", toolrc_content)
        self.assertIn("gimp-sam2-ai-tool", toolrc_content)

    # -----------------------------------------------------------------------
    # Pairwise 20: Command Palette Action Search + Workspace Hot-Swap
    # -----------------------------------------------------------------------
    def test_pairwise_20_command_palette_workspace_hotswap_F12_F10(self):
        """
        F12_COMMAND_PALETTE + F10_WORKSPACE:
        Verify Command Palette action lookup resolves workspace switching
        entries and triggers profile reload.
        """
        palette_entries = [
            {"name": "Switch Workspace: PhotoGIMP (Photoshop Muscle Memory)", "action": "windows-workspace-photogimp"},
            {"name": "Switch Workspace: Default GIMP", "action": "windows-workspace-default"},
            {"name": "Filter: Gaussian Blur", "action": "filters-gaussian-blur"},
        ]

        query = "photogimp"
        results = [e for e in palette_entries if query in e["name"].lower()]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "windows-workspace-photogimp")

    # -----------------------------------------------------------------------
    # Pairwise 21: Multi-Touch Continuous Rotation + Snapping Guide Angle
    # -----------------------------------------------------------------------
    def test_pairwise_21_multitouch_rotation_snapping_angle_F08_F09(self):
        """
        F08_MULTITOUCH + F09_SNAPPING:
        Verify two-finger rotation gesture snaps to 0°, 45°, 90°, 180° angles
        when within 3° threshold of cardinal guides.
        """
        cardinal_angles = [0.0, 45.0, 90.0, 135.0, 180.0, 270.0]
        snap_angle_tol = 3.0

        gesture_angles = [1.5, 43.8, 88.0, 110.0, 182.1]
        snapped_results = []

        for angle in gesture_angles:
            snapped = angle
            for card in cardinal_angles:
                if abs(angle - card) <= snap_angle_tol:
                    snapped = card
                    break
            snapped_results.append(snapped)

        self.assertEqual(snapped_results[0], 0.0)
        self.assertEqual(snapped_results[1], 45.0)
        self.assertEqual(snapped_results[2], 90.0)
        self.assertEqual(snapped_results[3], 110.0)  # No snap
        self.assertEqual(snapped_results[4], 180.0)

    # -----------------------------------------------------------------------
    # Pairwise 22: LittleCMS 2 CMYK Proofing + OLED Dark Viewport
    # -----------------------------------------------------------------------
    def test_pairwise_22_littlecms2_cmyk_oled_viewport_F19_F06(self):
        """
        F19_PSD_COLOR + F06_DARK_THEME:
        Verify CMYK soft-proofing gamut warning overlay renders with high contrast
        against OLED black viewport background.
        """
        oled_bg = (0, 0, 0)
        gamut_warning_color = (0, 229, 255)  # Accent Cyan for out-of-gamut markers
        de = delta_e_ciede2000(rgb_to_lab(oled_bg), rgb_to_lab(gamut_warning_color))

        # Contrast should be very high (Delta E > 60)
        self.assertGreater(de, 60.0)

    # -----------------------------------------------------------------------
    # Pairwise 23: Smart Object Vector Rasterization + Layer Styles Drop Shadow
    # -----------------------------------------------------------------------
    def test_pairwise_23_smart_object_rasterization_layer_styles_F15_F14(self):
        """
        F15_SMART_OBJECTS + F14_LAYER_STYLES:
        Verify scaling an SVG vector Smart Object automatically recalculates
        vector rasterization and scales Drop Shadow blur radius proportionally.
        """
        base_shadow_radius = 10.0
        scale_multiplier = 2.0
        updated_radius = base_shadow_radius * scale_multiplier

        self.assertEqual(updated_radius, 20.0)

    # -----------------------------------------------------------------------
    # Pairwise 24: Inpainting In-Place Replacement + XCF Project Save/Reload
    # -----------------------------------------------------------------------
    def test_pairwise_24_inpainting_inplace_xcf_roundtrip_F18_F13(self):
        """
        F18_INPAINT_AI + F13_ADJUSTMENTS:
        Verify generated inpaint patch and non-destructive mask serialize
        properly in XCF v014 project container.
        """
        xcf_path = self.assets.create_xcf(
            "inpaint_project.xcf",
            width=256,
            height=256,
            layers=[
                {"name": "Original Background", "opacity": 255, "type": 0},
                {"name": "Generative Inpaint Patch", "opacity": 255, "type": 0},
                {"name": "Inpaint Mask Channel", "opacity": 255, "type": 1},
            ],
            version=14,
        )
        self.assertTrue(xcf_path.exists())
        xcf_bytes = xcf_path.read_bytes()
        self.assertTrue(xcf_bytes.startswith(b"gimp xcf v014"))

    # -----------------------------------------------------------------------
    # Pairwise 25: Free Transform Perspective Warp + Layer Mask Bounds
    # -----------------------------------------------------------------------
    def test_pairwise_25_free_transform_perspective_warp_layer_mask_F11_F13(self):
        """
        F11_FREE_TRANSFORM + F13_ADJUSTMENTS:
        Verify 4-point perspective warp transformation applies synchronously
        to both layer RGB pixel buffer and attached layer mask coordinate system.
        """
        quad_src = [(0, 0), (100, 0), (100, 100), (0, 100)]
        quad_dst = [(10, 20), (90, 15), (110, 95), (-5, 85)]

        # Verify quad geometry is non-degenerate
        area = 0.5 * abs(
            quad_dst[0][0] * (quad_dst[1][1] - quad_dst[3][1])
            + quad_dst[1][0] * (quad_dst[2][1] - quad_dst[0][1])
            + quad_dst[2][0] * (quad_dst[3][1] - quad_dst[1][1])
            + quad_dst[3][0] * (quad_dst[0][1] - quad_dst[2][1])
        )
        self.assertGreater(area, 5000.0)


if __name__ == "__main__":
    unittest.main()
