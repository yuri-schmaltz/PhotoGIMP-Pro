"""
Tier 1 Feature Coverage Test Suite for GIMP + PhotoGIMP Modernization.
Covers Features F01 through F19 with opaque-box, requirement-driven test cases.

Module layout:
- test_f01_to_f05_core_gtk4.py (25 tests: F01-F05)
- test_f06_to_f09_ui_ux.py (20 tests: F06-F09)
- test_f10_to_f12_workspace_tools.py (15 tests: F10-F12)
- test_f13_to_f15_layers_smart_objects.py (15 tests: F13-F15)
- test_f16_to_f18_local_ai.py (15 tests: F16-F18)
- test_f19_psd_color.py (5 tests: F19)
Total: 95 tests.
"""

TIER_NAME = "Tier 1: Feature Coverage"
FEATURE_COUNT = 19
MIN_TESTS_PER_FEATURE = 5
TOTAL_TEST_COUNT = 95
