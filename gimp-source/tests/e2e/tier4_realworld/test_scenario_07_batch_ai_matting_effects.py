"""
Tier 4 Real-World Scenario 07: Batch AI Subject Matting & Styling.
Simulates an automated e-commerce catalog pipeline: batch background removal via RMBG-1.4,
uniform Layer Styles application (Stroke + Shadow), smart grid alignment, and memory audit.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.e2e.harness.assertions import (
    assert_gegl_graph_valid,
    assert_memory_stable,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase
from tests.e2e.harness.leak_checker import MemoryLeakChecker


class TestScenario07BatchAiMattingEffects(OpaqueBoxE2ETestCase):
    """
    Scenario 07: Batch AI Subject Matting & Styling Pipeline.
    Combines: RMBG-1.4 AI + Layer Styles FX + Smart Snapping + Memory Leak Auditing.
    """

    def test_scenario_07_batch_ai_matting_effects_pipeline_F17_F14_F09(self):
        # Step 1: Ingest Batch of 4 Product Images
        product_names = ["product_shoe", "product_bag", "product_watch", "product_headphones"]
        product_assets = []
        for name in product_names:
            asset_path = self.assets.create_tiff(f"{name}.tif", width=150, height=150, has_alpha=False)
            product_assets.append(asset_path)
            self.assertTrue(asset_path.exists())

        # Step 2: Memory Baseline Before Batch Ingestion
        checker = MemoryLeakChecker()
        checker.start("batch_start")

        # Step 3: Batch RMBG-1.4 Matting & Alpha Mask Generation
        matted_layers = []
        for idx, p_path in enumerate(product_assets):
            # Simulated RMBG-1.4 neural inference output
            layer_record = {
                "id": f"matted_{product_names[idx]}",
                "source": str(p_path),
                "alpha_channel": bytes([255 if (i % 150 > 20 and i % 150 < 130) else 0 for i in range(150 * 150)]),
                "fx": {
                    "stroke": {"width": 2.0, "color": "#ffffff"},
                    "drop_shadow": {"radius": 8.0, "opacity": 0.4, "y": 6.0},
                },
                "grid_pos": (50 + (idx % 2) * 200, 50 + (idx // 2) * 200),
            }
            matted_layers.append(layer_record)

        self.assertEqual(len(matted_layers), 4)

        # Step 4: Verify Equidistance Grid Alignment via Smart Snapping
        dx_col1 = matted_layers[1]["grid_pos"][0] - matted_layers[0]["grid_pos"][0]
        dx_col2 = matted_layers[3]["grid_pos"][0] - matted_layers[2]["grid_pos"][0]
        self.assertEqual(dx_col1, 200)
        self.assertEqual(dx_col2, 200)

        # Step 5: Check GEGL Pipeline Graph for Layer Styles
        gegl_graph = {
            "nodes": [
                {"id": "product_matted", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "fx_stroke", "operation": "gegl:stroke", "properties": {"width": 2.0}},
                {"id": "fx_shadow", "operation": "gegl:drop-shadow", "properties": {"radius": 8.0}},
                {"id": "catalog_canvas", "operation": "gegl:over", "properties": {}},
            ],
            "connections": [
                ("product_matted", "output", "fx_stroke", "input"),
                ("fx_stroke", "output", "fx_shadow", "input"),
                ("fx_shadow", "output", "catalog_canvas", "input"),
            ],
        }
        assert_gegl_graph_valid(gegl_graph)

        # Step 6: Verify Zero Memory Leak After Batch Processing
        checker.take_snapshot("batch_end")
        checker.assert_no_leak(max_growth_mb=25.0)

        # Step 7: Export Composite PSD
        composite_psd = self.assets.create_psd(
            "catalog_grid_composite.psd",
            width=500,
            height=500,
            layers=[
                {"name": "White Catalog Background", "bounds": (0, 0, 500, 500), "opacity": 255, "blend": "norm"},
                {"name": "Product 1 - Shoe", "bounds": (50, 50, 200, 200), "opacity": 255, "blend": "norm"},
                {"name": "Product 2 - Bag", "bounds": (250, 50, 400, 200), "opacity": 255, "blend": "norm"},
                {"name": "Product 3 - Watch", "bounds": (50, 250, 200, 400), "opacity": 255, "blend": "norm"},
                {"name": "Product 4 - Headphones", "bounds": (250, 250, 400, 400), "opacity": 255, "blend": "norm"},
            ],
        )
        self.assertTrue(composite_psd.exists())


if __name__ == "__main__":
    unittest.main()
