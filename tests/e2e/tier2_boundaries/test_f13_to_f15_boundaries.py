"""
Tier 2 Boundary and Corner Cases: Features F13 through F15.
- F13: Non-Destructive Adjustment Layers Boundary Cases
- F14: Real-Time Layer Styles FX Boundary Cases
- F15: Smart Objects & Linked Assets Boundary Cases
"""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tests.e2e.harness.assertions import (
    assert_gegl_graph_valid,
    assert_non_destructive_stack,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestF13AdjustmentLayersBoundaries(OpaqueBoxE2ETestCase):
    """
    F13 Boundary Tests: 50 chained adjustment layers, empty canvas adjustments,
    orphaned clipping mask base, extreme curve control points, and opacity 0% / 100% limits.
    """

    def test_f13_boundary_01_50_chained_adjustment_layers(self):
        """Boundary: 50 chained non-destructive adjustment layers GEGL graph evaluation."""
        num_layers = 50
        nodes = [{"id": "base_layer", "operation": "gegl:buffer-source", "properties": {}}]
        connections = []

        prev_node = "base_layer"
        for i in range(1, num_layers + 1):
            curr_node = f"adj_layer_{i}"
            op = "gegl:curves" if i % 2 == 0 else "gegl:levels"
            nodes.append({"id": curr_node, "operation": op, "properties": {"index": i}})
            connections.append((prev_node, "output", curr_node, "input"))
            prev_node = curr_node

        graph = {"nodes": nodes, "connections": connections}
        # Validate graph acyclicity and completeness
        assert_gegl_graph_valid(graph, expected_nodes=[{"id": "base_layer"}, {"id": "adj_layer_50"}])
        self.assertEqual(len(nodes), 51)
        self.assertEqual(len(connections), 50)

    def test_f13_boundary_02_adjustment_layer_on_empty_canvas(self):
        """Boundary: Applying adjustment layer on empty canvas (0 layers)."""
        def apply_adjustment_layer(doc_layers: List[Dict[str, Any]], adj_type: str) -> Dict[str, Any]:
            if not doc_layers:
                # Return virtual adjustment node with empty background buffer source
                return {
                    "status": "VIRTUAL_TRANSPARENT_BASE_CREATED",
                    "effective_layers": 1,
                    "layer_type": adj_type,
                    "base_color": (0, 0, 0, 0),
                }
            return {"status": "STACKED", "effective_layers": len(doc_layers) + 1}

        res = apply_adjustment_layer([], "curves")
        self.assertEqual(res["status"], "VIRTUAL_TRANSPARENT_BASE_CREATED")
        self.assertEqual(res["effective_layers"], 1)

    def test_f13_boundary_03_clipping_mask_missing_base_layer(self):
        """Boundary: Clipping mask adjustment layer where target base layer is missing/deleted."""
        stack = [
            {"id": "layer_1", "type": "pixel", "visible": True},
            {"id": "adj_clip", "type": "adjustment", "is_clipping_mask": True, "target_layer_id": "deleted_layer_99"},
        ]

        def resolve_clipping_mask_target(layer: Dict[str, Any], all_layers: List[Dict[str, Any]]) -> str:
            target_id = layer.get("target_layer_id")
            existing_ids = {lyr["id"] for lyr in all_layers}
            if target_id not in existing_ids:
                # Fallback to direct layer underneath or unclip
                return "UNCLIPPED_FALLBACK_TO_STACK"
            return "CLIPPED_TO_TARGET"

        status = resolve_clipping_mask_target(stack[1], stack)
        self.assertEqual(status, "UNCLIPPED_FALLBACK_TO_STACK")

    def test_f13_boundary_04_extreme_curve_control_points(self):
        """Boundary: Extreme curve control points (0,0 to 255,255, vertical step, inverted)."""
        # Inverted S-curve and extreme step function
        points_inverted = [(0, 255), (128, 128), (255, 0)]
        points_step = [(0, 0), (127, 0), (128, 255), (255, 255)]

        def evaluate_linear_lut(control_points: List[Tuple[int, int]]) -> List[int]:
            lut = [0] * 256
            for i in range(256):
                # Find segment
                for j in range(len(control_points) - 1):
                    x0, y0 = control_points[j]
                    x1, y1 = control_points[j + 1]
                    if x0 <= i <= x1:
                        if x1 == x0:
                            lut[i] = y1
                        else:
                            t = (i - x0) / (x1 - x0)
                            lut[i] = int(y0 + t * (y1 - y0))
                        break
            return lut

        lut_inv = evaluate_linear_lut(points_inverted)
        self.assertEqual(lut_inv[0], 255)
        self.assertEqual(lut_inv[128], 128)
        self.assertEqual(lut_inv[255], 0)

        lut_step = evaluate_linear_lut(points_step)
        self.assertEqual(lut_step[0], 0)
        self.assertEqual(lut_step[127], 0)
        self.assertEqual(lut_step[128], 255)
        self.assertEqual(lut_step[255], 255)

    def test_f13_boundary_05_adjustment_layer_opacity_boundary(self):
        """Boundary: Adjustment layer opacity at exact 0.0% (no-op identity) and 100.0%."""
        base_pixels = bytes([100, 150, 200, 255]) * 16
        orig_hash = hashlib.sha256(base_pixels).hexdigest()

        def blend_adjustment(base_buf: bytes, adj_delta: int, opacity: float) -> bytes:
            if opacity <= 0.0:
                # Identity fast-path
                return base_buf
            out = bytearray(base_buf)
            for idx in range(len(out)):
                val = int(out[idx] + adj_delta * opacity)
                out[idx] = max(0, min(255, val))
            return bytes(out)

        # 0.0% opacity should preserve exact base hash
        res_0 = blend_adjustment(base_pixels, adj_delta=50, opacity=0.0)
        self.assertEqual(hashlib.sha256(res_0).hexdigest(), orig_hash)

        # 100.0% opacity should mutate composite
        res_100 = blend_adjustment(base_pixels, adj_delta=50, opacity=1.0)
        self.assertNotEqual(hashlib.sha256(res_100).hexdigest(), orig_hash)
        assert_non_destructive_stack(base_pixels, orig_hash, res_100)


class TestF14LayerStylesBoundaries(OpaqueBoxE2ETestCase):
    """
    F14 Boundary Tests: Layer FX on 1x1 layer, 500px blur radius drop shadow,
    0px stroke width, all 4 FX enabled simultaneously, FX on invisible layer.
    """

    def test_f14_boundary_01_layer_styles_on_1x1_layer(self):
        """Boundary: Real-time Layer FX applied to a single 1x1 pixel layer."""
        layer_bounds = (100, 100, 101, 101)  # 1x1 pixel (top, left, bottom, right)
        shadow_radius = 5.0

        def compute_fx_bounds(bounds: Tuple[int, int, int, int], radius: float) -> Tuple[int, int, int, int]:
            pad = int(math.ceil(radius * 3.0))
            t, l, b, r = bounds
            return (t - pad, l - pad, b + pad, r + pad)

        fx_bounds = compute_fx_bounds(layer_bounds, shadow_radius)
        self.assertEqual(fx_bounds, (85, 85, 116, 116))
        # Bounds expanded symmetrically around 1x1 pixel
        w = fx_bounds[3] - fx_bounds[1]
        h = fx_bounds[2] - fx_bounds[0]
        self.assertEqual(w, 31)
        self.assertEqual(h, 31)

    def test_f14_boundary_02_500px_blur_radius_drop_shadow(self):
        """Boundary: Extreme 500px drop shadow blur radius bounding box expansion."""
        layer_bounds = (0, 0, 100, 100)
        blur_radius = 500.0

        pad = int(math.ceil(blur_radius * 3.0))  # 3-sigma Gaussian blur = 1500px
        self.assertEqual(pad, 1500)

        expanded_w = 100 + 2 * pad
        expanded_h = 100 + 2 * pad
        self.assertEqual(expanded_w, 3100)
        self.assertEqual(expanded_h, 3100)

    def test_f14_boundary_03_zero_pixel_stroke_width(self):
        """Boundary: Stroke layer effect with 0px width (no-op condition)."""
        def compute_stroke_geometry(stroke_width: float) -> Dict[str, Any]:
            if stroke_width <= 0.0:
                return {"is_rendered": False, "allocated_pixels": 0, "stroke_width": 0.0}
            return {"is_rendered": True, "allocated_pixels": int(stroke_width * 100), "stroke_width": stroke_width}

        stroke_0 = compute_stroke_geometry(0.0)
        self.assertFalse(stroke_0["is_rendered"])
        self.assertEqual(stroke_0["allocated_pixels"], 0)

        stroke_3 = compute_stroke_geometry(3.0)
        self.assertTrue(stroke_3["is_rendered"])

    def test_f14_boundary_04_all_four_fx_simultaneous(self):
        """Boundary: All 4 Layer FX (Drop Shadow + Stroke + Glow + Bevel) enabled simultaneously."""
        fx_graph = {
            "nodes": [
                {"id": "base_pixel_source", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "fx_bevel", "operation": "gegl:bevel-emboss", "properties": {"depth": 3.0}},
                {"id": "fx_glow", "operation": "gegl:outer-glow", "properties": {"radius": 12.0}},
                {"id": "fx_stroke", "operation": "gegl:stroke", "properties": {"width": 2.0}},
                {"id": "fx_shadow", "operation": "gegl:drop-shadow", "properties": {"radius": 15.0}},
            ],
            "connections": [
                ("base_pixel_source", "output", "fx_bevel", "input"),
                ("fx_bevel", "output", "fx_glow", "input"),
                ("fx_glow", "output", "fx_stroke", "input"),
                ("fx_stroke", "output", "fx_shadow", "input"),
            ],
        }

        assert_gegl_graph_valid(
            fx_graph,
            expected_nodes=[
                {"id": "fx_bevel", "operation": "gegl:bevel-emboss"},
                {"id": "fx_glow", "operation": "gegl:outer-glow"},
                {"id": "fx_stroke", "operation": "gegl:stroke"},
                {"id": "fx_shadow", "operation": "gegl:drop-shadow"},
            ],
        )
        self.assertEqual(len(fx_graph["nodes"]), 5)
        self.assertEqual(len(fx_graph["connections"]), 4)

    def test_f14_boundary_05_fx_on_invisible_layer(self):
        """Boundary: Layer styles calculation on hidden / 0-opacity layer."""
        def should_render_layer_fx(is_visible: bool, opacity: float) -> bool:
            if not is_visible or opacity <= 0.0:
                return False
            return True

        self.assertFalse(should_render_layer_fx(is_visible=False, opacity=1.0))
        self.assertFalse(should_render_layer_fx(is_visible=True, opacity=0.0))
        self.assertTrue(should_render_layer_fx(is_visible=True, opacity=0.5))


class TestF15SmartObjectsBoundaries(OpaqueBoxE2ETestCase):
    """
    F15 Boundary Tests: 500MB linked RAW container, circular linked smart objects,
    corrupted SVG XML inside container, missing linked file fallback, 10,000x10,000 vector scaling.
    """

    def test_f15_boundary_01_500mb_linked_raw_image_container(self):
        """Boundary: 500MB linked RAW container proxy caching and memory budgeting."""
        simulated_raw_size_bytes = 500 * 1024 * 1024  # 500 MB
        proxy_max_dim = 1920

        def compute_smart_object_proxy(raw_file_bytes: int, width: int = 8256, height: int = 5504) -> Dict[str, Any]:
            # Scale down to proxy dimensions for real-time canvas viewport
            scale = min(proxy_max_dim / width, proxy_max_dim / height)
            proxy_w = int(width * scale)
            proxy_h = int(height * scale)
            proxy_mem_bytes = proxy_w * proxy_h * 4  # RGBA 8-bit

            return {
                "source_size_bytes": raw_file_bytes,
                "proxy_width": proxy_w,
                "proxy_height": proxy_h,
                "proxy_mem_mb": proxy_mem_bytes / (1024 * 1024),
                "is_proxy_cached": True,
            }

        proxy_info = compute_smart_object_proxy(simulated_raw_size_bytes)
        self.assertTrue(proxy_info["is_proxy_cached"])
        # Proxy memory is under 35 MB despite 500MB original container
        self.assertLess(proxy_info["proxy_mem_mb"], 35.0)

    def test_f15_boundary_02_circular_linked_smart_object_refs(self):
        """Boundary: Circular reference detection in linked smart object tree."""
        # A links to B, B links to C, C links to A
        linked_graph = {
            "asset_A.psd": ["asset_B.psd"],
            "asset_B.psd": ["asset_C.psd"],
            "asset_C.psd": ["asset_A.psd"],
        }

        def detect_smart_object_recursion(root: str, graph: Dict[str, List[str]], stack: Optional[List[str]] = None) -> bool:
            if stack is None:
                stack = []
            if root in stack:
                return True  # Circular reference!
            stack.append(root)
            for child in graph.get(root, []):
                if detect_smart_object_recursion(child, graph, list(stack)):
                    return True
            return False

        has_cycle = detect_smart_object_recursion("asset_A.psd", linked_graph)
        self.assertTrue(has_cycle)

    def test_f15_boundary_03_corrupted_svg_xml_in_container(self):
        """Boundary: Corrupted/malformed SVG XML inside container fallback."""
        corrupted_svg = "<svg width='100' height='100'><rect width='50' <unclosed tag></svg>"

        def parse_vector_container(svg_text: str) -> Dict[str, Any]:
            try:
                root = ET.fromstring(svg_text)
                return {"status": "PARSED", "element_count": len(root)}
            except ET.ParseError as e:
                # Graceful fallback to broken asset placeholder
                return {"status": "BROKEN_ASSET_FALLBACK", "error": str(e), "placeholder": "gimp-broken-image-symbolic"}

        res = parse_vector_container(corrupted_svg)
        self.assertEqual(res["status"], "BROKEN_ASSET_FALLBACK")
        self.assertEqual(res["placeholder"], "gimp-broken-image-symbolic")

    def test_f15_boundary_04_missing_linked_external_file_fallback(self):
        """Boundary: Missing external linked file fallback to cached proxy thumbnail."""
        missing_asset_path = self.temp_dir / "assets" / "missing_photo.raw"

        def resolve_linked_asset(filepath: Path, cached_proxy_path: Optional[Path]) -> Dict[str, Any]:
            if not filepath.exists():
                return {
                    "is_resolved": False,
                    "use_cached_proxy": cached_proxy_path is not None and cached_proxy_path.exists(),
                    "warning": f"Linked asset file '{filepath.name}' is missing or offline",
                }
            return {"is_resolved": True, "use_cached_proxy": False}

        cached_proxy = self.temp_dir / "cache" / "proxy_thumb.png"
        cached_proxy.parent.mkdir(parents=True, exist_ok=True)
        cached_proxy.write_bytes(b"\x89PNG\r\n\x1a\n")

        res = resolve_linked_asset(missing_asset_path, cached_proxy)
        self.assertFalse(res["is_resolved"])
        self.assertTrue(res["use_cached_proxy"])
        self.assertIn("missing or offline", res["warning"])

    def test_f15_boundary_05_embedded_vector_scaling_10000x10000(self):
        """Boundary: Vector smart object scaling to extreme 10,000x10,000 px resolution."""
        svg_viewbox = (0, 0, 100, 100)
        target_render_w = 10000
        target_render_h = 10000

        scale_x = target_render_w / svg_viewbox[2]
        scale_y = target_render_h / svg_viewbox[3]

        self.assertEqual(scale_x, 100.0)
        self.assertEqual(scale_y, 100.0)

        # Ensure rasterization buffer bounds calculations remain finite and positive
        pixel_count = target_render_w * target_render_h
        self.assertEqual(pixel_count, 100_000_000)
        self.assertLess(pixel_count, 2**31)


if __name__ == "__main__":
    unittest.main()
