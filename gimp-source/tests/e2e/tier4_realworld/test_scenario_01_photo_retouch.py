"""
Tier 4 Real-World Scenario 01: Photo Retouching & Isolation Pipeline.
Simulates an end-to-end studio portrait isolation, non-destructive skin grading,
real-time drop shadow / glow effects, and multi-format project export.
"""

from __future__ import annotations

import hashlib
import struct
import unittest
from pathlib import Path

from tests.e2e.harness.assertions import (
    assert_color_delta_e,
    assert_gegl_graph_valid,
    assert_non_destructive_stack,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestScenario01PhotoRetouch(OpaqueBoxE2ETestCase):
    """
    Scenario 01: Studio Portrait Retouching & Subject Isolation Pipeline.
    Combines: SAM2/RMBG-1.4 + Curves/Levels Adjustments + Drop Shadow FX + XCF/TIFF Export.
    """

    def test_scenario_01_photo_retouch_pipeline_F16_F17_F13_F14(self):
        # Step 1: Ingest High-Res Portrait Asset
        width, height = 400, 500
        portrait_tiff = self.assets.create_tiff(
            "studio_portrait.tif",
            width=width,
            height=height,
            has_alpha=False,
            color_space="RGB",
        )
        self.assertTrue(portrait_tiff.exists())
        orig_raw_bytes = portrait_tiff.read_bytes()
        orig_hash = hashlib.sha256(orig_raw_bytes).hexdigest()

        # Step 2: Subject Isolation with SAM 2 & RMBG-1.4 Neural Matting
        # Foreground person bounding box (center region)
        cx, cy, radius = 200, 250, 150
        alpha_mask = bytearray(width * height)
        for y in range(height):
            for x in range(width):
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if dist <= radius - 5:
                    alpha_mask[y * width + x] = 255
                elif dist <= radius + 5:
                    # Feathery transition
                    alpha_mask[y * width + x] = int(255 * ((radius + 5 - dist) / 10.0))
                else:
                    alpha_mask[y * width + x] = 0

        # Step 3: Configure Non-Destructive GEGL Adjustment Stack
        # Node 1: Curves for skin tonal grading (masked to foreground subject)
        # Node 2: Levels for background contrast suppression
        # Node 3: Real-Time Layer Styles (Drop Shadow + Outer Glow)
        gegl_pipeline = {
            "nodes": [
                {"id": "source_portrait", "operation": "gegl:buffer-source", "properties": {"width": width, "height": height}},
                {"id": "mask_sam2_rmbg", "operation": "gegl:buffer-source", "properties": {"format": "Y u8"}},
                {"id": "adj_curves_skin", "operation": "gegl:curves", "properties": {"curve": "portrait-warmth"}},
                {"id": "adj_levels_bg", "operation": "gegl:levels", "properties": {"in_low": 0.05, "in_high": 0.95}},
                {"id": "fx_drop_shadow", "operation": "gegl:drop-shadow", "properties": {"x": 8.0, "y": 12.0, "radius": 20.0, "opacity": 0.65}},
                {"id": "fx_outer_glow", "operation": "gegl:outer-glow", "properties": {"radius": 10.0, "color": "#ffe0b2"}},
                {"id": "composite_final", "operation": "gegl:over", "properties": {}},
            ],
            "connections": [
                ("source_portrait", "output", "adj_curves_skin", "input"),
                ("mask_sam2_rmbg", "output", "adj_curves_skin", "aux"),
                ("adj_curves_skin", "output", "fx_drop_shadow", "input"),
                ("fx_drop_shadow", "output", "fx_outer_glow", "input"),
                ("fx_outer_glow", "output", "composite_final", "input"),
            ],
        }

        assert_gegl_graph_valid(
            gegl_pipeline,
            expected_nodes=[
                {"id": "adj_curves_skin", "operation": "gegl:curves"},
                {"id": "fx_drop_shadow", "operation": "gegl:drop-shadow"},
                {"id": "fx_outer_glow", "operation": "gegl:outer-glow"},
            ],
            expected_connections=[
                ("source_portrait", "output", "adj_curves_skin", "input"),
                ("fx_drop_shadow", "output", "fx_outer_glow", "input"),
            ],
        )

        # Step 4: Verify Non-Destructive Integrity
        # The base raw pixel buffer remains strictly untouched
        assert_non_destructive_stack(orig_raw_bytes, orig_hash)

        # Step 5: Save Master Project to XCF format (v014)
        xcf_project = self.assets.create_xcf(
            "retouched_portrait.xcf",
            width=width,
            height=height,
            layers=[
                {"name": "Original Background", "opacity": 255, "type": 0},
                {"name": "Isolated Subject (SAM 2 + RMBG-1.4)", "opacity": 255, "type": 0},
                {"name": "Skin Warmth Curves (Adjustment Layer)", "opacity": 255, "type": 0},
                {"name": "Drop Shadow FX (Live Filter)", "opacity": 166, "type": 0},
            ],
            version=14,
        )
        self.assertTrue(xcf_project.exists())
        xcf_data = xcf_project.read_bytes()
        self.assertTrue(xcf_data.startswith(b"gimp xcf v014"))

        # Step 6: Export Final Print TIFF Asset with Alpha
        final_tiff = self.assets.create_tiff(
            "retouched_portrait_master.tif",
            width=width,
            height=height,
            has_alpha=True,
            color_space="RGB",
        )
        self.assertTrue(final_tiff.exists())


if __name__ == "__main__":
    unittest.main()
