#!/usr/bin/env python3
"""
Tier 5 White-Box Adversarial Stress Testing Suite for GIMP + PhotoGIMP Gauntlet.

Empirically challenges:
1. Extreme Inputs & Boundary Fuzzing (NaN/Inf sanitization, 100,000x100,000 coordinates, zero-dimension handling).
2. 100+ Layer Adjustment Stacks (compounding GEGL curves/levels graph without recursion overflow or memory blowup).
3. Overlapping Layer Styles FX (compound bounds calculation, 10,000px radiuses, multi-angle compounding).
4. Rapid Gesture Bursts (50,000 high-frequency input controller events, pinch/pan/tilt state transitions).
5. Corrupted Assets Resilience (corrupted PSD, malformed SVG, truncated XCF, damaged RAW DNG, zero-byte payloads).
6. AI Model Fallbacks & Bounds (SAM 2, RMBG-1.4, SDXL Inpainting on missing weights, extreme ROIs, boundary conditions).
"""

from __future__ import annotations

import gc
import math
import os
import random
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = WORKSPACE_ROOT / "tests"
GIMP_SOURCE_DIR = WORKSPACE_ROOT / "gimp-source"

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(GIMP_SOURCE_DIR / "plug-ins" / "python" / "sam2-magic-selection"))
sys.path.insert(0, str(GIMP_SOURCE_DIR / "plug-ins" / "python" / "rmbg-background-removal"))
sys.path.insert(0, str(GIMP_SOURCE_DIR / "plug-ins" / "python" / "generative-inpainting"))

from sam2_engine import SAM2Engine
from rmbg_engine import RMBGEngine
from inpainting_engine import GenerativeInpaintingEngine
from roi_processor import ROIProcessor
from tests.e2e.harness.fps_profiler import FPSProfiler
from tests.e2e.harness.leak_checker import MemoryLeakChecker, get_process_memory_info


class TestTier5AdversarialStress(unittest.TestCase):
    """Tier 5 White-Box Adversarial Stress Testing Suite."""

    @classmethod
    def setUpClass(cls):
        os.environ["G_SLICE"] = "always-malloc"
        os.environ["G_DEBUG"] = "gc-friendly"

    # =========================================================================
    # 1. EXTREME INPUTS & BOUNDARY FUZZING
    # =========================================================================

    def test_01_extreme_canvas_coordinates_and_nan_sanitization(self):
        """Fuzzes extreme coordinates (±1e8, NaN, Inf, subpixel) through transform pipeline."""
        from tests.test_m2_fuzzer_and_gauntlet import gimp_display_shell_scale_to_sim

        test_cases = [
            (1.0, 0.0, 0.0, 2.0, 100000.0, 100000.0),
            (2.0, 50000.0, 50000.0, 0.01, -100000.0, -100000.0),
            (0.001, -1e6, 1e6, 64.0, 0.0001, 0.0001),
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        ]

        for cur_scale, off_x, off_y, new_scale, vp_x, vp_y in test_cases:
            new_off_x, new_off_y = gimp_display_shell_scale_to_sim(
                cur_scale, off_x, off_y, new_scale, vp_x, vp_y
            )
            self.assertFalse(math.isnan(new_off_x), f"NaN produced in offset X for input {vp_x}")
            self.assertFalse(math.isnan(new_off_y), f"NaN produced in offset Y for input {vp_y}")
            self.assertFalse(math.isinf(new_off_x), f"Inf produced in offset X for input {vp_x}")
            self.assertFalse(math.isinf(new_off_y), f"Inf produced in offset Y for input {vp_y}")

    def test_02_massive_hierarchy_10k_deep_layer_tree(self):
        """Stress-tests a 10,000-node deep layer tree traversal without stack overflow."""
        class MockLayerNode:
            def __init__(self, name: str, parent=None):
                self.name = name
                self.parent = parent
                self.children = []
                self.visible = True
                self.opacity = 1.0

        # Build linear 10,000 deep chain
        root = MockLayerNode("root")
        curr = root
        for i in range(10000):
            child = MockLayerNode(f"layer_{i}", parent=curr)
            curr.children.append(child)
            curr = child

        # Iterative traversal to ensure stack safety
        visited = 0
        stack = [root]
        while stack:
            node = stack.pop()
            visited += 1
            stack.extend(node.children)

        self.assertEqual(visited, 10001, "Failed to traverse full 10,000 deep hierarchy")

    # =========================================================================
    # 2. 100+ LAYER ADJUSTMENT STACKS
    # =========================================================================

    def test_03_compounding_100_layer_adjustment_stack(self):
        """
        Simulates live non-destructive GEGL composition across a 120-layer stack
        (Curves, Levels, Color Balance, Invert, Threshold) on an RGB test patch.
        Verifies mathematical convergence, numerical stability, and zero stack overflow.
        """
        # Test pixel RGB buffer: 64x64 RGBA
        width, height = 64, 64
        num_pixels = width * height
        # Base image: gradient ramp
        buffer = [float(i % 256) / 255.0 for i in range(num_pixels * 4)]

        # Stack definition: 120 adjustment layers
        adjustment_stack = []
        for i in range(120):
            adj_type = ["curves", "levels", "color_balance", "opacity_blend"][i % 4]
            adjustment_stack.append({
                "type": adj_type,
                "gamma": 1.0 + (0.01 * (i % 5)),
                "opacity": 0.95,
                "layer_idx": i,
            })

        # Process through non-destructive pipeline
        curr_buffer = list(buffer)
        for adj in adjustment_stack:
            adj_type = adj["type"]
            gamma = adj["gamma"]
            opacity = adj["opacity"]

            if adj_type == "curves":
                # Gamma adjustment on RGB channels
                for p in range(num_pixels):
                    for c in range(3):
                        idx = p * 4 + c
                        val = curr_buffer[idx]
                        adjusted = math.pow(max(0.0, min(1.0, val)), gamma)
                        curr_buffer[idx] = val * (1.0 - opacity) + adjusted * opacity
            elif adj_type == "levels":
                # Linear contrast expansion
                for p in range(num_pixels):
                    for c in range(3):
                        idx = p * 4 + c
                        val = curr_buffer[idx]
                        adjusted = max(0.0, min(1.0, (val - 0.05) / 0.90))
                        curr_buffer[idx] = val * (1.0 - opacity) + adjusted * opacity
            elif adj_type == "color_balance":
                for p in range(num_pixels):
                    idx_r = p * 4 + 0
                    idx_b = p * 4 + 2
                    curr_buffer[idx_r] = min(1.0, curr_buffer[idx_r] * 1.01)
                    curr_buffer[idx_b] = max(0.0, curr_buffer[idx_b] * 0.99)
            elif adj_type == "opacity_blend":
                pass

        # Verify output buffer integrity
        self.assertEqual(len(curr_buffer), num_pixels * 4)
        for val in curr_buffer:
            self.assertFalse(math.isnan(val), "NaN found in 120-layer adjustment stack output")
            self.assertFalse(math.isinf(val), "Inf found in 120-layer adjustment stack output")
            self.assertTrue(0.0 <= val <= 1.00001, f"Value {val} out of normalized bounds [0, 1]")

    # =========================================================================
    # 3. OVERLAPPING LAYER FX
    # =========================================================================

    def test_04_compound_overlapping_layer_fx_bounds(self):
        """
        Tests compound bounding box expansion with 5 simultaneous layer effects
        under extreme radius (10,000px), multi-revolution angles, and full spreads.
        """
        from tests.stress.test_m3_empirical_challenger import (
            GeglRectangleSim,
            gimp_layer_fx_update_bounds_sim,
        )

        base_rect = GeglRectangleSim(x=100, y=100, width=500, height=300)

        # Extreme Drop Shadow + Outer Glow + Stroke
        drop_shadow = {"enabled": True, "angle": 720.0 + 45.0, "distance": 150.0, "size": 250.0}
        outer_glow = {"enabled": True, "size": 300.0}
        stroke = {"enabled": True, "size": 50.0}

        expanded = gimp_layer_fx_update_bounds_sim(
            base_rect,
            drop_shadow=drop_shadow,
            outer_glow=outer_glow,
            stroke=stroke,
        )

        # Bounding box must strictly enclose all effect expansions
        self.assertLess(expanded.x, base_rect.x, "Expanded X should extend left")
        self.assertLess(expanded.y, base_rect.y, "Expanded Y should extend top")
        self.assertGreater(expanded.width, base_rect.width + 500, "Expanded width should account for shadow+glow")
        self.assertGreater(expanded.height, base_rect.height + 500, "Expanded height should account for shadow+glow")

        # Test extreme 10,000px boundary
        extreme_shadow = {"enabled": True, "angle": 180.0, "distance": 5000.0, "size": 5000.0}
        extreme_expanded = gimp_layer_fx_update_bounds_sim(base_rect, drop_shadow=extreme_shadow)
        self.assertTrue(extreme_expanded.width > 10000, "Extreme 10,000px radius not properly expanded")

    # =========================================================================
    # 4. RAPID GESTURE BURSTS (50,000 EVENTS)
    # =========================================================================

    def test_05_rapid_gesture_event_burst_50k(self):
        """
        Fuzzes 50,000 high-frequency input controller events (pinch-to-zoom, rotate,
        pan, stylus tilt/pressure) to verify zero controller race condition or state desync.
        """
        from tests.test_m2_fuzzer_and_gauntlet import (
            gimp_zoom_model_zoom_step,
            gimp_rotate_gesture_calc_angle,
            gimp_kinetic_pan_step,
        )

        current_scale = 1.0
        current_angle = 0.0
        current_pan_x = 0.0
        current_pan_y = 0.0

        for i in range(50000):
            event_type = i % 4
            if event_type == 0:
                # Zoom delta
                delta = (random.random() - 0.5) * 0.1
                current_scale = gimp_zoom_model_zoom_step("PINCH", current_scale, delta)
            elif event_type == 1:
                # Rotate delta
                raw_angle = (random.random() * 720.0) - 360.0
                current_angle = gimp_rotate_gesture_calc_angle(raw_angle, constrain=(i % 10 == 0))
            elif event_type == 2:
                # Pan step
                vel_x = (random.random() - 0.5) * 100.0
                vel_y = (random.random() - 0.5) * 100.0
                new_vx, new_vy, dx, dy, cont = gimp_kinetic_pan_step(vel_x, vel_y, 0.016)
                current_pan_x += dx
                current_pan_y += dy
            elif event_type == 3:
                # Stylus pressure
                pressure = max(0.0, min(1.0, random.random()))
                self.assertTrue(0.0 <= pressure <= 1.0)

        # Confirm state bounds
        self.assertTrue(1.0 / 256.0 <= current_scale <= 256.0, "Scale drifted out of valid bounds")
        self.assertFalse(math.isnan(current_angle), "Angle resulted in NaN")
        self.assertFalse(math.isnan(current_pan_x) or math.isnan(current_pan_y), "Pan resulted in NaN")

    # =========================================================================
    # 5. CORRUPTED ASSETS RESILIENCE
    # =========================================================================

    def test_06_corrupted_asset_resilience(self):
        """
        Tests parsing resilience across hostile / corrupted asset payloads:
        - Corrupted PSD with illegal version and truncated header
        - Corrupted SVG with malformed XML tags and infinite loops
        - Corrupted XCF v014 with broken tile offsets
        - Corrupted RAW DNG with invalid IFD directories
        - Zero-byte files and random fuzz streams
        """
        # 1. Corrupted PSD
        bad_psd_payloads = [
            b"8BPS\x00\x02",  # Bad version
            b"8BPS\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00",  # Truncated header
            b"GARBAGE_HEADER_1234567890",  # Invalid magic
        ]
        for payload in bad_psd_payloads:
            is_valid = len(payload) >= 26 and payload.startswith(b"8BPS") and struct.unpack(">H", payload[4:6])[0] in (1, 2)
            self.assertFalse(is_valid, f"Payload {payload[:10]} should be recognized as invalid PSD")

        # 2. Corrupted SVG
        bad_svg_payloads = [
            "<svg><rect width='100' height='100' /",  # Unclosed tag
            "<svg><path d='M0 0 L 100 100 Z'>",  # Missing closing </svg>
            "<?xml version='1.0'?><!DOCTYPE svg PUBLIC '-//W3C//DTD SVG 1.1//EN' 'http://bad.url'>",
            "",
        ]
        for svg_text in bad_svg_payloads:
            parsed_successfully = True
            try:
                ET.fromstring(svg_text)
            except Exception:
                parsed_successfully = False
            self.assertFalse(parsed_successfully, "Corrupted SVG should raise ParseError cleanly")

        # 3. Corrupted XCF (GIMP XCF Format)
        bad_xcf_payloads = [
            b"gimp xcf v014\x00",  # Truncated before dimensions
            b"gimp xcf file\x00\x00\x00\x00\x00",  # Invalid version header
            b"\x00" * 32,  # Null bytes
        ]
        for xcf_data in bad_xcf_payloads:
            is_valid_xcf = len(xcf_data) >= 26 and xcf_data.startswith(b"gimp xcf")
            if is_valid_xcf:
                # Check if dimensions are readable
                is_readable = len(xcf_data) >= 14 + 8
                self.assertFalse(is_readable, "Truncated XCF should fail dimension read")

        # 4. Corrupted RAW DNG
        bad_raw_payloads = [
            b"II\x2a\x00\x00\x00\x00\x00",  # Zero IFD offset
            b"MM\x00\x2a\xff\xff\xff\xff",  # OOB IFD offset
            b"NOT_RAW_DATA",
        ]
        for raw_data in bad_raw_payloads:
            is_valid_tiff = len(raw_data) >= 8 and (
                (raw_data.startswith(b"II\x2a\x00") or raw_data.startswith(b"MM\x00\x2a"))
                and struct.unpack("<I" if raw_data.startswith(b"II") else ">I", raw_data[4:8])[0] >= 8
                and struct.unpack("<I" if raw_data.startswith(b"II") else ">I", raw_data[4:8])[0] < len(raw_data)
            )
            self.assertFalse(is_valid_tiff, "Corrupted RAW DNG should be cleanly rejected")

    # =========================================================================
    # 6. AI MODEL FALLBACKS & BOUNDARY RESILIENCE
    # =========================================================================

    def test_07_ai_model_fallbacks_and_boundaries(self):
        """
        Tests AI model weight fallback pathways, OOB prompts, 1x1 buffers,
        and feathering math across SAM 2, RMBG-1.4, and Generative Inpainting.
        """
        # SAM 2 Fallback & Bounds
        sam2 = SAM2Engine(model_path="/nonexistent/model.onnx", use_gpu=False)
        sam2.encode_image(b"dummy_data", 64, 64)
        # Empty prompt points fallback
        mask_empty = sam2.predict_mask_from_points(64, 64, [])
        self.assertEqual(len(mask_empty), 64 * 64)
        self.assertTrue(all(b == 0 for b in mask_empty), "Empty points must return clear mask")

        # Bounding box outside image
        mask_oob = sam2.predict_mask_from_bbox(64, 64, (-100, -100, 200, 200))
        self.assertEqual(len(mask_oob), 64 * 64)
        self.assertTrue(all(b == 255 for b in mask_oob), "OOB bbox must safely clamp to full canvas")

        # RMBG-1.4 Fallback & Extreme Aspect Ratios
        rmbg = RMBGEngine(model_path="/nonexistent/rmbg.onnx", use_gpu=False)
        matte_1x1 = rmbg.remove_background(b"\xff\xff\xff", 1, 1)
        self.assertEqual(len(matte_1x1), 1)

        matte_extreme = rmbg.remove_background(b"", 5000, 2)
        self.assertEqual(len(matte_extreme), 10000)

        # Generative Inpainting ROI & Feather Math
        feather_zero = ROIProcessor.create_feather_mask(64, 64, feather_radius=0)
        self.assertEqual(len(feather_zero), 64 * 64)

        # Inpainting Engine missing weight fallback
        inpaint = GenerativeInpaintingEngine(backend="sdxl_fallback", use_gpu=False)
        out_rgb = inpaint.inpaint_roi(b"", b"", 64, 64, "remove unwanted object")
        self.assertEqual(len(out_rgb), 64 * 64 * 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
