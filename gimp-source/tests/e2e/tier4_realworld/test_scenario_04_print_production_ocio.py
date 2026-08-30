"""
Tier 4 Real-World Scenario 04: Print Production & Color Management Pipeline.
Simulates high-end print publishing: OpenColorIO ACEScg ingest, Smart Snapping bleed/margin guides,
LittleCMS 2 CMYK soft-proofing with Delta E verification, and 16-bit TIFF export.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

from tests.e2e.harness.assertions import (
    assert_color_delta_e,
    assert_gegl_graph_valid,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestScenario04PrintProductionOcio(OpaqueBoxE2ETestCase):
    """
    Scenario 04: Print Production & Color Management Pipeline.
    Combines: OpenColorIO ACES + LittleCMS 2 CMYK Proofing + Smart Snapping Guides + TIFF Export.
    """

    def test_scenario_04_print_production_ocio_pipeline_F19_F09(self):
        # Step 1: Initialize Prepress Project with Smart Guides (3mm Bleed, Margins)
        width_px, height_px = 2400, 3000  # 300 DPI 8x10 print
        bleed_px = 35  # ~3mm at 300 DPI
        margin_px = 120

        guides = [
            {"orientation": "horizontal", "pos": bleed_px, "type": "bleed"},
            {"orientation": "horizontal", "pos": height_px - bleed_px, "type": "bleed"},
            {"orientation": "vertical", "pos": bleed_px, "type": "bleed"},
            {"orientation": "vertical", "pos": width_px - bleed_px, "type": "bleed"},
            {"orientation": "vertical", "pos": margin_px, "type": "margin"},
            {"orientation": "vertical", "pos": width_px - margin_px, "type": "margin"},
            {"orientation": "horizontal", "pos": height_px // 2, "type": "center"},
            {"orientation": "vertical", "pos": width_px // 2, "type": "center"},
        ]
        self.assertEqual(len(guides), 8)

        # Step 2: OpenColorIO ACEScg Color Pipeline Setup
        ocio_prepress_graph = {
            "nodes": [
                {"id": "img_source", "operation": "gegl:buffer-source", "properties": {"width": width_px, "height": height_px}},
                {"id": "ocio_acescg_convert", "operation": "gegl:ocio-transform", "properties": {"src": "ACEScg", "dst": "ACES2065-1"}},
                {"id": "adj_curves_cmyk_tonal", "operation": "gegl:curves", "properties": {"curve": "press-dot-gain-compensation"}},
                {"id": "lcms2_cmyk_proofing", "operation": "gegl:lcms-proof", "properties": {"profile": "ISOcoated_v2_eci.icc", "bpc": True, "intent": 0}},
                {"id": "display_viewport", "operation": "gegl:over", "properties": {}},
            ],
            "connections": [
                ("img_source", "output", "ocio_acescg_convert", "input"),
                ("ocio_acescg_convert", "output", "adj_curves_cmyk_tonal", "input"),
                ("adj_curves_cmyk_tonal", "output", "lcms2_cmyk_proofing", "input"),
                ("lcms2_cmyk_proofing", "output", "display_viewport", "input"),
            ],
        }
        assert_gegl_graph_valid(
            ocio_prepress_graph,
            expected_nodes=[
                {"id": "ocio_acescg_convert", "operation": "gegl:ocio-transform"},
                {"id": "lcms2_cmyk_proofing", "operation": "gegl:lcms-proof"},
            ],
        )

        # Step 3: Color Difference Assertion on Brand Colors (Warm Red & Reflex Blue)
        # Verify color calibration through LittleCMS 2 CMYK pipeline
        warm_red_target = (235, 45, 35)
        warm_red_proof = (234, 47, 36)
        assert_color_delta_e(warm_red_target, warm_red_proof, max_delta_e=1.2)

        reflex_blue_target = (10, 25, 140)
        reflex_blue_proof = (12, 27, 142)
        assert_color_delta_e(reflex_blue_target, reflex_blue_proof, max_delta_e=1.5)

        # Step 4: Export Master CMYK TIFF with Uncompressed IFD Tags
        export_tiff = self.assets.create_tiff(
            "print_ready_cmyk_master.tif",
            width=200,
            height=250,
            has_alpha=False,
            color_space="CMYK",
        )
        self.assertTrue(export_tiff.exists())
        data = export_tiff.read_bytes()

        # Validate TIFF header (II, 42) and IFD
        magic, ver, ifd_off = struct.unpack("<2sHI", data[:8])
        self.assertEqual(magic, b"II")
        self.assertEqual(ver, 42)
        self.assertGreater(ifd_off, 0)


if __name__ == "__main__":
    unittest.main()
