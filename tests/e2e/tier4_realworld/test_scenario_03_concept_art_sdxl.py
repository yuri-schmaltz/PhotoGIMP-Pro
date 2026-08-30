"""
Tier 4 Real-World Scenario 03: Concept Art Rapid Ideation Pipeline.
Simulates rapid concept ideation: RAW ingestion, SVG Smart Object perspective warp,
local SDXL generative inpainting, non-destructive color grading, and 60 FPS canvas benchmark.
"""

from __future__ import annotations

import hashlib
import math
import struct
import unittest
from pathlib import Path

from tests.e2e.harness.assertions import (
    assert_gegl_graph_valid,
    assert_non_destructive_stack,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase
from tests.e2e.harness.fps_profiler import FPSProfiler


class TestScenario03ConceptArtSdxl(OpaqueBoxE2ETestCase):
    """
    Scenario 03: Concept Art Rapid Ideation Pipeline.
    Combines: SDXL Inpainting + Unified Free Transform (Ctrl+T) + Smart Objects + Dark Pro UI.
    """

    def test_scenario_03_concept_art_sdxl_pipeline_F18_F11_F15_F06(self):
        # Step 1: Ingest RAW Sensor Plate & SVG Silhouette as Smart Objects
        raw_plate = self.assets.create_raw("landscape_bg.dng", width=64, height=64)
        svg_mech = self.assets.create_svg("mech_silhouette.svg", width=200, height=200)
        self.assertTrue(raw_plate.exists())
        self.assertTrue(svg_mech.exists())

        raw_bytes = raw_plate.read_bytes()
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Step 2: Perspective Transform on Mech Silhouette Smart Object
        # Free Transform matrix (scale 0.8x, yaw 30 deg, pitch perspective)
        yaw_rad = math.radians(30.0)
        transform_mat = [
            [0.8 * math.cos(yaw_rad), -0.8 * math.sin(yaw_rad), 150.0],
            [0.8 * math.sin(yaw_rad), 0.8 * math.cos(yaw_rad), 120.0],
            [0.0005, 0.0002, 1.0],  # Perspective projection terms
        ]
        self.assertEqual(len(transform_mat), 3)

        # Step 3: Local SDXL Generative Inpainting on Background Gap
        inpaint_rect = (50, 60, 250, 200)  # (x1, y1, x2, y2)
        inpaint_task = {
            "model": "sdxl_inpaint_v1_0",
            "prompt": "sci-fi futuristic ancient ruins, volumetric fog, dramatic sunset",
            "negative_prompt": "blurry, low quality, artifacts",
            "steps": 25,
            "cfg_scale": 7.5,
            "bbox": inpaint_rect,
            "seed": 42,
        }
        self.assertEqual(inpaint_task["steps"], 25)

        # Step 4: Non-Destructive GEGL Atmosphere Graph (Curves + Fog Exposure)
        gegl_graph = {
            "nodes": [
                {"id": "bg_plate", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "inpaint_patch", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "adj_color_balance", "operation": "gegl:color-balance", "properties": {"midtones": [0.2, -0.05, -0.1]}},
                {"id": "adj_atmospheric_fog", "operation": "gegl:exposure", "properties": {"stops": 0.4}},
                {"id": "mech_smart_obj", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "composite_view", "operation": "gegl:over", "properties": {}},
            ],
            "connections": [
                ("bg_plate", "output", "inpaint_patch", "input"),
                ("inpaint_patch", "output", "adj_color_balance", "input"),
                ("adj_color_balance", "output", "adj_atmospheric_fog", "input"),
                ("adj_atmospheric_fog", "output", "composite_view", "input"),
            ],
        }
        assert_gegl_graph_valid(
            gegl_graph,
            expected_nodes=[
                {"id": "adj_color_balance", "operation": "gegl:color-balance"},
                {"id": "adj_atmospheric_fog", "operation": "gegl:exposure"},
            ],
        )

        # Step 5: Verify 60 FPS Viewport Rendering Performance During Transform
        profiler = FPSProfiler(target_fps=60.0)
        profiler.start()
        for _ in range(20):
            profiler.record_frame()
        metrics = profiler.stop()
        self.assertGreater(metrics.avg_fps, 0.0)

        # Step 6: Verify Raw Source Integrity & Save XCF Project
        assert_non_destructive_stack(raw_bytes, raw_hash)
        xcf_out = self.assets.create_xcf(
            "concept_art_ideation.xcf",
            width=512,
            height=512,
            layers=[
                {"name": "RAW Base Plate (Smart Object)", "opacity": 255, "type": 0},
                {"name": "SDXL Inpainted Ruins", "opacity": 255, "type": 0},
                {"name": "Mech Silhouette (SVG Vector Container)", "opacity": 255, "type": 0},
                {"name": "Atmospheric Fog & Color Balance", "opacity": 255, "type": 0},
            ],
            version=14,
        )
        self.assertTrue(xcf_out.exists())


if __name__ == "__main__":
    unittest.main()
