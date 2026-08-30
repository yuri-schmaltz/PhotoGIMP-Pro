"""
Smoke & Unit Verification Suite for GIMP + PhotoGIMP E2E Test Harness.
Validates all infrastructure components, fixtures, generators, and assertions.
"""

from __future__ import annotations

import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

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
from tests.e2e.harness.fps_profiler import FPSProfiler, FrameMetrics, ViewportBenchmark
from tests.e2e.harness.leak_checker import (
    MemoryDelta,
    MemoryLeakChecker,
    MemorySnapshot,
    ValgrindLogAnalyzer,
    get_process_memory_info,
)
from tests.e2e.harness.mock_assets import (
    MockAssetGenerator,
    create_dummy_psd,
    create_dummy_raw,
    create_dummy_svg,
    create_dummy_tiff,
    create_dummy_xcf,
    create_photogimp_profile,
)
from tests.e2e.harness.xvfb_runner import (
    XvfbContext,
    XvfbRunner,
    find_free_display,
    has_dbus_session,
    has_xvfb,
    is_display_available,
)


class TestHarnessXDGEnvironment(unittest.TestCase):
    """Verifies XDG isolation and profile generation."""

    def test_gimp_env_context_photogimp(self):
        with GimpEnvContext(profile="photogimp") as env_ctx:
            cfg_dir = env_ctx.gimp_config_dir
            self.assertTrue(cfg_dir.exists())
            self.assertTrue((cfg_dir / "shortcutsrc").exists())
            self.assertTrue((cfg_dir / "menurc").exists())
            self.assertTrue((cfg_dir / "gimprc").exists())
            self.assertTrue((cfg_dir / "sessionrc").exists())
            self.assertTrue((cfg_dir / "gimp.css").exists())

            # Verify environment variables
            self.assertEqual(env_ctx.env["GIMP_TESTING_ENV"], "1")
            self.assertEqual(env_ctx.env["G_SLICE"], "always-malloc")
            self.assertEqual(env_ctx.env["G_DEBUG"], "gc-friendly")

    def test_gimp_env_context_default(self):
        with GimpEnvContext(profile="default") as env_ctx:
            cfg_dir = env_ctx.gimp_config_dir
            self.assertTrue(cfg_dir.exists())
            self.assertTrue((cfg_dir / "gimprc").exists())


class TestHarnessMockAssets(unittest.TestCase):
    """Verifies synthetic asset generators for specification compliance."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="gimp_test_assets_"))
        self.gen = MockAssetGenerator(output_dir=self.temp_dir)

    def tearDown(self):
        self.gen.cleanup()

    def test_psd_generation(self):
        psd_path = self.gen.create_psd("test_sample.psd", width=64, height=48, color_mode="RGB")
        self.assertTrue(psd_path.exists())
        data = psd_path.read_bytes()

        # Check 8BPS header signature and version 1
        sig, version = struct.unpack(">4sH", data[:6])
        self.assertEqual(sig, b"8BPS")
        self.assertEqual(version, 1)

        # Height, Width, Depth, Mode
        _, height, width, depth, mode = struct.unpack(">HIIHH", data[12:26])
        self.assertEqual(width, 64)
        self.assertEqual(height, 48)
        self.assertEqual(depth, 8)
        self.assertEqual(mode, 3)  # RGB

    def test_psd_cmyk_generation(self):
        psd_path = self.gen.create_psd("cmyk_sample.psd", width=32, height=32, color_mode="CMYK")
        data = psd_path.read_bytes()
        mode = struct.unpack(">H", data[24:26])[0]
        self.assertEqual(mode, 4)  # CMYK

    def test_svg_generation(self):
        svg_path = self.gen.create_svg("vector_sample.svg", width=120, height=120)
        self.assertTrue(svg_path.exists())
        content = svg_path.read_text(encoding="utf-8")
        root = ET.fromstring(content)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.attrib.get("width"), "120")
        self.assertEqual(root.attrib.get("height"), "120")

    def test_raw_generation(self):
        raw_path = self.gen.create_raw("sensor_sample.dng", width=64, height=64, bayer_pattern="RGGB")
        self.assertTrue(raw_path.exists())
        data = raw_path.read_bytes()
        magic, ver = struct.unpack("<2sH", data[:4])
        self.assertEqual(magic, b"II")
        self.assertEqual(ver, 42)

    def test_tiff_generation(self):
        tiff_path = self.gen.create_tiff("sample.tif", width=80, height=80, has_alpha=True)
        self.assertTrue(tiff_path.exists())
        data = tiff_path.read_bytes()
        magic, ver = struct.unpack("<2sH", data[:4])
        self.assertEqual(magic, b"II")
        self.assertEqual(ver, 42)

    def test_xcf_generation(self):
        xcf_path = self.gen.create_xcf("project.xcf", width=100, height=100, version=14)
        self.assertTrue(xcf_path.exists())
        data = xcf_path.read_bytes()
        self.assertTrue(data.startswith(b"gimp xcf v014"))


class TestHarnessMemoryLeakChecker(unittest.TestCase):
    """Verifies memory measurement and leak tracking."""

    def test_process_memory_info(self):
        info = get_process_memory_info()
        self.assertGreater(info["rss_bytes"], 0)

    def test_memory_snapshot_and_delta(self):
        checker = MemoryLeakChecker()
        checker.start("init")
        snap1 = checker.get_baseline()
        self.assertGreater(snap1.rss_mb, 0.0)

        # Allocate temporary buffer
        buf = bytes(1024 * 1024 * 5)  # 5 MB
        snap2 = checker.take_snapshot("after_alloc")
        delta = snap2.diff(snap1)

        self.assertEqual(delta.baseline_label, "init")
        self.assertEqual(delta.current_label, "after_alloc")
        # Assert stability
        checker.assert_no_leak(max_growth_mb=50.0, max_percentage=1000.0)
        del buf

    def test_valgrind_analyzer(self):
        sample_log = """
==12345== LEAK SUMMARY:
==12345==    definitely lost: 0 bytes in 0 blocks
==12345==    indirectly lost: 0 bytes in 0 blocks
==12345==      possibly lost: 128 bytes in 2 blocks
==12345==    still reachable: 4,096 bytes in 16 blocks
==12345==         suppressed: 0 bytes in 0 blocks
==12345== ERROR SUMMARY: 0 errors from 0 contexts
"""
        report = ValgrindLogAnalyzer.parse_log(sample_log)
        self.assertEqual(report.definitely_lost_bytes, 0)
        self.assertEqual(report.indirectly_lost_bytes, 0)
        self.assertEqual(report.possibly_lost_bytes, 128)
        self.assertEqual(report.still_reachable_bytes, 4096)
        self.assertEqual(report.total_error_count, 0)
        self.assertTrue(report.is_clean)


class TestHarnessFPSProfiler(unittest.TestCase):
    """Verifies frame timing and 60 FPS budget calculations."""

    def test_fps_profiler_basic(self):
        profiler = FPSProfiler(target_fps=60.0)
        profiler.start()
        for _ in range(10):
            profiler.record_frame()
        metrics = profiler.stop()

        self.assertEqual(metrics.total_frames, 10)
        self.assertIn("avg_fps", metrics.to_dict())
        self.assertTrue(len(metrics.summary_table()) > 50)

    def test_viewport_pan_simulation(self):
        metrics = ViewportBenchmark.simulate_canvas_pan(num_steps=10, step_delay_sec=0.005)
        self.assertEqual(metrics.total_frames, 10)
        self.assertGreater(metrics.avg_fps, 0.0)


class TestHarnessAssertions(unittest.TestCase):
    """Verifies high-level domain assertions."""

    def test_delta_e_color_assertion(self):
        c1 = (255, 0, 0)
        c2 = (255, 2, 1)  # almost identical red
        assert_color_delta_e(c1, c2, max_delta_e=2.0)

        # Distant colors should raise AssertionError
        c_blue = (0, 0, 255)
        with self.assertRaises(AssertionError):
            assert_color_delta_e(c1, c_blue, max_delta_e=1.5)

    def test_gtk4_widget_tree_assertion(self):
        tree = {
            "type": "GtkWindow",
            "classes": ["oled-dark", "main-window"],
            "properties": {"title": "PhotoGIMP"},
            "children": [
                {
                    "type": "GtkPopoverMenuBar",
                    "classes": ["menubar"],
                    "properties": {},
                    "children": [],
                },
                {
                    "type": "GimpSpinScale",
                    "classes": ["pill-slider"],
                    "properties": {"value": 100},
                    "children": [],
                },
            ],
        }

        expected = {
            "type": "GtkWindow",
            "classes": ["oled-dark"],
            "children": [
                {"type": "GtkPopoverMenuBar"},
                {"type": "GimpSpinScale", "classes": ["pill-slider"]},
            ],
        }
        assert_gtk4_widget_tree(tree, expected)

    def test_gegl_graph_assertion(self):
        graph = {
            "nodes": [
                {"id": "input_layer", "operation": "gegl:buffer-source", "properties": {}},
                {"id": "adj_curves", "operation": "gegl:curves", "properties": {"curve": "s-curve"}},
                {"id": "fx_shadow", "operation": "gegl:drop-shadow", "properties": {"radius": 10.0}},
            ],
            "connections": [
                ("input_layer", "output", "adj_curves", "input"),
                ("adj_curves", "output", "fx_shadow", "input"),
            ],
        }
        assert_gegl_graph_valid(
            graph,
            expected_nodes=[
                {"id": "adj_curves", "operation": "gegl:curves"},
                {"id": "fx_shadow", "operation": "gegl:drop-shadow"},
            ],
            expected_connections=[
                ("input_layer", "output", "adj_curves", "input"),
                ("adj_curves", "output", "fx_shadow", "input"),
            ],
        )

    def test_shortcut_mapping_assertion(self):
        shortcut_text = """
(gtk_accel_path "<Actions>/image/image-transform-free" "<Primary>t")
(gtk_accel_path "<Actions>/layers/layers-duplicate" "<Primary>j")
(gtk_accel_path "<Actions>/select/select-none" "<Primary>d")
"""
        assert_shortcut_mapping(
            shortcut_text,
            {
                "image-transform-free": "<Primary>t",
                "layers-duplicate": "<Primary>j",
                "select-none": "<Primary>d",
            },
        )

    def test_non_destructive_stack_assertion(self):
        base_pixels = b"\x00\x11\x22\x33" * 100
        import hashlib
        orig_hash = hashlib.sha256(base_pixels).hexdigest()
        composite_pixels = b"\x44\x55\x66\x77" * 100

        # Unmodified base + distinct composite should pass
        assert_non_destructive_stack(base_pixels, orig_hash, composite_pixels)

        # Mutated base should fail
        mutated_base = b"\xff" + base_pixels[1:]
        with self.assertRaises(AssertionError):
            assert_non_destructive_stack(mutated_base, orig_hash, composite_pixels)


class TestOpaqueBoxBaseTestCase(OpaqueBoxE2ETestCase):
    """Verifies that OpaqueBoxE2ETestCase lifecycle and helper methods work smoothly."""

    def test_subproc_and_asset_helpers(self):
        # Create an asset via helper
        psd = self.assets.create_psd("test_box.psd")
        self.assertTrue(psd.exists())

        # Run command helper
        res = self.run_subproc(["python3", "-c", "import os; print(os.environ.get('GIMP_TESTING_ENV'))"])
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "1")


if __name__ == "__main__":
    unittest.main()
