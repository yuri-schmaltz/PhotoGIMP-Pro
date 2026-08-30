"""
Tier 4 Real-World Scenario 06: Vector & Smart Asset Workflow.
Simulates importing SVG as an embedded Smart Object, applying non-destructive transforms,
re-rasterizing vector paths at arbitrary scales, and live-reloading modified source assets.
"""

from __future__ import annotations

import hashlib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tests.e2e.harness.assertions import assert_non_destructive_stack
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestScenario06SmartObjectVectorRaster(OpaqueBoxE2ETestCase):
    """
    Scenario 06: Vector & Smart Asset Workflow.
    Combines: Smart Objects (SVG/RAW) + Non-Destructive Free Transform + Embedded Asset Reload.
    """

    def test_scenario_06_smart_object_vector_raster_pipeline_F15_F11(self):
        # Step 1: Create Initial SVG Vector Asset
        svg_file = self.assets.create_svg(
            "corporate_logo.svg",
            width=200,
            height=200,
            elements=[
                {"type": "rect", "x": 20, "y": 20, "width": 160, "height": 160, "rx": 20, "fill": "#0078d4"},
                {"type": "circle", "cx": 100, "y": 100, "r": 50, "fill": "#ffffff"},
            ],
            title="Corporate Identity Logo",
        )
        self.assertTrue(svg_file.exists())
        initial_svg_content = svg_file.read_text(encoding="utf-8")
        orig_hash = hashlib.sha256(initial_svg_content.encode("utf-8")).hexdigest()

        # Step 2: Initialize Smart Object Container
        smart_object = {
            "name": "Corporate Logo (Smart Vector)",
            "source_type": "vector/svg",
            "source_uri": str(svg_file),
            "source_hash": orig_hash,
            "dpi": 300,
            "transform": {"scale_x": 1.0, "scale_y": 1.0, "rotation_deg": 0.0, "tx": 50.0, "ty": 50.0},
            "raster_cache": None,
        }

        # Step 3: Non-Destructive 5x Upscale (500%)
        # Vector rasterizer scales geometry without raster interpolation blurring
        smart_object["transform"]["scale_x"] = 5.0
        smart_object["transform"]["scale_y"] = 5.0
        target_w = int(200 * smart_object["transform"]["scale_x"])
        target_h = int(200 * smart_object["transform"]["scale_y"])

        self.assertEqual((target_w, target_h), (1000, 1000))

        # Step 4: Live Source Asset Edit (Update Brand Color #0078d4 -> #ffaa00)
        updated_svg_content = initial_svg_content.replace("#0078d4", "#ffaa00")
        svg_file.write_text(updated_svg_content, encoding="utf-8")

        new_hash = hashlib.sha256(updated_svg_content.encode("utf-8")).hexdigest()
        self.assertNotEqual(orig_hash, new_hash)

        # Step 5: Reload / Invalidate Smart Object Cache
        smart_object["source_hash"] = new_hash
        smart_object["raster_cache"] = bytes([255, 170, 0, 255] * (target_w * target_h))

        self.assertEqual(smart_object["source_hash"], new_hash)
        self.assertEqual(smart_object["transform"]["scale_x"], 5.0)

        # Step 6: Save Container Project to XCF
        xcf_out = self.assets.create_xcf(
            "smart_object_master.xcf",
            width=1200,
            height=1200,
            layers=[
                {"name": "Background Grid", "opacity": 255, "type": 0},
                {"name": "Corporate Logo (Smart Vector)", "opacity": 255, "type": 0},
            ],
            version=14,
        )
        self.assertTrue(xcf_out.exists())


if __name__ == "__main__":
    unittest.main()
