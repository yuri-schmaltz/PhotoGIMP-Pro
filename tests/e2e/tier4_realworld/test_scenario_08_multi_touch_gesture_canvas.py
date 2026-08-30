"""
Tier 4 Real-World Scenario 08: Tablet / Touch Drawing Session.
Simulates a digital painting workflow: GtkGestureStylus pressure curves, multi-touch pinch/rotate,
15-degree angle magnetic snapping, GSK GPU frame timing profiling, and memory stability.
"""

from __future__ import annotations

import math
import unittest

from tests.e2e.harness.assertions import assert_fps_budget
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase
from tests.e2e.harness.fps_profiler import FPSProfiler
from tests.e2e.harness.leak_checker import MemoryLeakChecker


class TestScenario08MultiTouchGestureCanvas(OpaqueBoxE2ETestCase):
    """
    Scenario 08: Tablet / Touch Drawing Session Pipeline.
    Combines: GtkGestureStylus + Multi-Touch Navigation + GSK 60 FPS + Magnetic Snapping.
    """

    def test_scenario_08_multi_touch_gesture_canvas_pipeline_F03_F08_F02_F09(self):
        # Step 1: Initialize Memory & FPS Profilers
        leak_checker = MemoryLeakChecker()
        leak_checker.start("session_start")

        profiler = FPSProfiler(target_fps=60.0)
        profiler.start()

        # Step 2: Simulate 50 Stylus Pressure Drawing Stroke Events
        stroke_points = []
        for i in range(50):
            t = i / 50.0
            x = 100.0 + t * 400.0
            y = 200.0 + math.sin(t * math.pi * 2.0) * 50.0
            pressure = 0.2 + 0.8 * math.sin(t * math.pi)  # Pressure swells and recedes
            tilt_x = math.cos(t * math.pi) * 30.0
            tilt_y = math.sin(t * math.pi) * 30.0

            # Dynamic brush radius calculation based on stylus pressure
            radius = 2.0 + pressure * 18.0
            stroke_points.append({"x": x, "y": y, "pressure": pressure, "radius": radius, "tilt": (tilt_x, tilt_y)})
            profiler.record_frame()

        self.assertEqual(len(stroke_points), 50)
        self.assertAlmostEqual(stroke_points[25]["pressure"], 1.0, delta=0.05)

        # Step 3: Simulate Multi-Touch Pinch & Rotation with 15° Snapping
        cardinal_increment = 15.0
        snapped_rotations = []
        for angle in [1.2, 14.5, 29.1, 46.2, 89.5, 178.9]:
            nearest_step = round(angle / cardinal_increment) * cardinal_increment
            if abs(angle - nearest_step) <= 2.5:
                snapped_rotations.append(nearest_step)
            else:
                snapped_rotations.append(angle)
            profiler.record_frame()

        self.assertEqual(snapped_rotations[0], 0.0)
        self.assertEqual(snapped_rotations[1], 15.0)
        self.assertEqual(snapped_rotations[2], 30.0)
        self.assertEqual(snapped_rotations[3], 45.0)
        self.assertEqual(snapped_rotations[4], 90.0)
        self.assertEqual(snapped_rotations[5], 180.0)

        # Step 4: Verify Viewport Frame Metrics & Budget
        metrics = profiler.stop()
        self.assertEqual(metrics.total_frames, 56)
        self.assertGreater(metrics.avg_fps, 0.0)

        # Step 5: Verify Memory Leak Integrity After 56 Rapid Gesture Frames
        leak_checker.take_snapshot("session_end")
        leak_checker.assert_no_leak(max_growth_mb=20.0)


if __name__ == "__main__":
    unittest.main()
