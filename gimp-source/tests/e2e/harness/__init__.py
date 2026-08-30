"""
E2E Test Harness for GIMP + PhotoGIMP Modernization.
Provides test cases, XDG isolation, headless display execution, leak detection,
FPS profiling, synthetic asset generators, and domain assertions.
"""

from .assertions import (
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
    srgb_to_xyz,
    xyz_to_lab,
)
from .base_test import GimpEnvContext, OpaqueBoxE2ETestCase
from .fps_profiler import FPSProfiler, FrameMetrics, ViewportBenchmark
from .leak_checker import (
    MemoryDelta,
    MemoryLeakChecker,
    MemorySnapshot,
    ValgrindLogAnalyzer,
    ValgrindReport,
    get_process_memory_info,
)
from .mock_assets import (
    MockAssetGenerator,
    create_dummy_psd,
    create_dummy_raw,
    create_dummy_svg,
    create_dummy_tiff,
    create_dummy_xcf,
    create_photogimp_profile,
)
from .xvfb_runner import (
    XvfbContext,
    XvfbRunner,
    find_free_display,
    has_dbus_session,
    has_xvfb,
    is_display_available,
    run_in_xvfb,
)

__all__ = [
    "OpaqueBoxE2ETestCase",
    "GimpEnvContext",
    "XvfbRunner",
    "XvfbContext",
    "run_in_xvfb",
    "is_display_available",
    "has_xvfb",
    "has_dbus_session",
    "find_free_display",
    "MemoryLeakChecker",
    "MemorySnapshot",
    "MemoryDelta",
    "ValgrindLogAnalyzer",
    "ValgrindReport",
    "get_process_memory_info",
    "FPSProfiler",
    "FrameMetrics",
    "ViewportBenchmark",
    "MockAssetGenerator",
    "create_dummy_psd",
    "create_dummy_svg",
    "create_dummy_raw",
    "create_dummy_tiff",
    "create_dummy_xcf",
    "create_photogimp_profile",
    "assert_gtk4_widget_tree",
    "assert_gegl_graph_valid",
    "assert_color_delta_e",
    "assert_shortcut_mapping",
    "assert_non_destructive_stack",
    "assert_memory_stable",
    "assert_fps_budget",
    "delta_e_ciede2000",
    "parse_shortcut_file",
    "rgb_to_lab",
    "srgb_to_xyz",
    "xyz_to_lab",
]
