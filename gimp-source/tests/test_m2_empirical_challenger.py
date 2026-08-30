#!/usr/bin/env python3
"""
Empirical Adversarial Challenger Test Harness for Milestone 2:
Features 8 & 9 (Multi-Touch Canvas Navigation & Smart Snapping Guides).

Adversarial Stress Harness covers:
1. Pinch-to-Zoom midpoint anchor stability, extreme scale factors, zero scale, and negative coordinates.
2. Canvas rotation angle normalization, 3.0° cardinal magnetic snap thresholds, and 15° Ctrl stepping across [-720°, +720°].
3. Kinetic pan exponential decay physics, convergence, velocity damping, and timing jitter robustness.
4. Smart Snapping bounding box & equidistance math under multi-layer stacks, zero distances, negative layer offsets, and overlaps.
"""

import math
import random
import sys
import unittest
from typing import Dict, List, Optional, Tuple


# ============================================================================
# C Implementation Mathematical Models (Direct Transcriptions of C Source)
# ============================================================================

# Constants from GIMP source
ZOOM_MIN = 1.0 / 256.0  # 0.00390625 (~0.39%)
ZOOM_MAX = 256.0        # 25600%
CARDINAL_SNAP_TOLERANCE = 3.0
KINETIC_PAN_FRICTION = 0.005
KINETIC_PAN_CUTOFF = 5.0
DEFAULT_SNAP_DISTANCE = 8.0


def gimp_zoom_model_zoom_step(zoom_type: str, scale: float, delta: float) -> float:
    """Exact transcription of gimp_zoom_model_zoom_step in libgimpwidgets/gimpzoommodel.c."""
    if zoom_type == "PINCH":
        if delta > 0.0:
            new_scale = scale * (1.0 + delta)
        elif delta < 0.0:
            new_scale = scale / (1.0 + -delta)
        else:
            new_scale = scale
    elif zoom_type == "SMOOTH":
        if delta > 0.0:
            new_scale = scale * (1.0 + 0.1 * delta)
        elif delta < 0.0:
            new_scale = scale / (1.0 + 0.1 * -delta)
        else:
            new_scale = scale
    elif zoom_type == "TO":
        new_scale = scale
    else:
        new_scale = scale

    return max(ZOOM_MIN, min(ZOOM_MAX, new_scale))


def gimp_display_shell_scale_to_sim(
    current_scale: float,
    offset_x: float,
    offset_y: float,
    new_scale: float,
    viewport_x: float,
    viewport_y: float,
) -> Tuple[float, float]:
    """
    Exact simulation of gimp_display_shell_scale_to from gimpdisplayshell-scale.c:
    Untransforms viewport coord to image coord, updates scale, transforms back, and adjusts offsets.
    """
    # 1. Untransform viewport coordinate to image coordinate
    image_x = (viewport_x + offset_x) / current_scale
    image_y = (viewport_y + offset_y) / current_scale

    # 2. Transform image coordinate to new viewport coordinate with new scale
    new_viewport_x = image_x * new_scale - offset_x
    new_viewport_y = image_y * new_scale - offset_y

    # 3. Scroll offset update: new_offset = offset + (new_viewport - viewport)
    new_offset_x = offset_x + (new_viewport_x - viewport_x)
    new_offset_y = offset_y + (new_viewport_y - viewport_y)

    return new_offset_x, new_offset_y


def gimp_rotate_gesture_calc_angle(raw_angle: float, constrain: bool) -> float:
    """Exact transcription of rotation math in gimp_display_shell_rotate_gesture_update."""
    angle = raw_angle
    if constrain:
        # 15-degree increment stepping when Ctrl is held
        angle = round(angle / 15.0) * 15.0
    else:
        # Magnetic snapping to cardinal angles (0°, 90°, 180°, 270°) within 3° tolerance
        norm = math.fmod(angle, 360.0)
        if norm < 0.0:
            norm += 360.0

        if norm < CARDINAL_SNAP_TOLERANCE or norm > (360.0 - CARDINAL_SNAP_TOLERANCE):
            angle = angle - (norm if norm < 180.0 else (norm - 360.0))
        elif abs(norm - 90.0) <= CARDINAL_SNAP_TOLERANCE:
            angle = angle + (90.0 - norm)
        elif abs(norm - 180.0) <= CARDINAL_SNAP_TOLERANCE:
            angle = angle + (180.0 - norm)
        elif abs(norm - 270.0) <= CARDINAL_SNAP_TOLERANCE:
            angle = angle + (270.0 - norm)

    return angle


def gimp_kinetic_pan_step(
    vel_x: float,
    vel_y: float,
    dt: float,
    friction: float = KINETIC_PAN_FRICTION,
) -> Tuple[float, float, float, float, bool]:
    """
    Exact simulation of 1 tick of gimp_display_shell_kinetic_pan_tick.
    Returns: (new_vel_x, new_vel_y, dx, dy, continue_animation)
    """
    if dt <= 0.0 or dt > 0.1:
        dt = 1.0 / 60.0

    dx = vel_x * dt
    dy = vel_y * dt

    decay = math.exp(-friction * dt * 1000.0)
    new_vel_x = vel_x * decay
    new_vel_y = vel_y * decay

    speed = math.hypot(new_vel_x, new_vel_y)
    continue_anim = speed >= KINETIC_PAN_CUTOFF

    return new_vel_x, new_vel_y, dx, dy, continue_anim


# ============================================================================
# Smart Snapping Core Math Simulation
# ============================================================================

def gimp_snap_distance(unsnapped: float, nearest: float, epsilon: float, mindist: float) -> Tuple[bool, float, float]:
    """Exact transcription of gimp_image_snap_distance."""
    dist = abs(unsnapped - nearest)
    if dist <= epsilon and dist < mindist:
        return True, dist, nearest
    return False, mindist, unsnapped


class BBoxSnapper:
    """Simulates gimp_image_snap_rectangle and equidistance logic from gimpimage-snap.c."""

    def __init__(self, layers: List[Dict[str, float]], epsilon: float = DEFAULT_SNAP_DISTANCE):
        self.layers = layers
        self.epsilon = epsilon

    def snap_rectangle(
        self,
        rect: Tuple[float, float, float, float],
        snap_to_bbox: bool = True,
        snap_to_equidistance: bool = True,
    ) -> Dict[str, any]:
        x1, y1, x2, y2 = rect
        w = x2 - x1
        h = y2 - y1
        xc = (x1 + x2) / 2.0
        yc = (y1 + y2) / 2.0

        tx1, ty1 = x1, y1
        snapped_x = False
        snapped_y = False
        snapped_layer_h = None
        snapped_layer_v = None
        snap_side_h = None
        snap_side_v = None
        equidist_h = None
        equidist_v = None

        mindist_x = self.epsilon
        mindist_y = self.epsilon

        if snap_to_bbox:
            # 1. Snap X (Center, Left, Right)
            for idx, lyr in enumerate(self.layers):
                gx, gy, gw, gh = lyr['x'], lyr['y'], lyr['w'], lyr['h']
                gcx = gx + gw / 2.0

                # Snap center
                ok, d, target = gimp_snap_distance(xc, gcx, self.epsilon, mindist_x)
                if ok:
                    mindist_x = d
                    tx1 = round(x1 + (target - xc))
                    snapped_x = True
                    snapped_layer_h = idx
                    snap_side_h = "VCENTER"

                # Snap left to gx
                ok, d, target = gimp_snap_distance(x1, gx, self.epsilon, mindist_x)
                if ok:
                    mindist_x = d
                    tx1 = target
                    snapped_x = True
                    snapped_layer_h = idx
                    snap_side_h = "LEFT"

                # Snap left to gx+gw
                ok, d, target = gimp_snap_distance(x1, gx + gw, self.epsilon, mindist_x)
                if ok:
                    mindist_x = d
                    tx1 = target
                    snapped_x = True
                    snapped_layer_h = idx
                    snap_side_h = "LEFT"

                # Snap right to gx
                ok, d, target = gimp_snap_distance(x2, gx, self.epsilon, mindist_x)
                if ok:
                    mindist_x = d
                    tx1 = round(x1 + (target - x2))
                    snapped_x = True
                    snapped_layer_h = idx
                    snap_side_h = "RIGHT"

                # Snap right to gx+gw
                ok, d, target = gimp_snap_distance(x2, gx + gw, self.epsilon, mindist_x)
                if ok:
                    mindist_x = d
                    tx1 = round(x1 + (target - x2))
                    snapped_x = True
                    snapped_layer_h = idx
                    snap_side_h = "RIGHT"

            # 2. Snap Y (Center, Top, Bottom)
            for idx, lyr in enumerate(self.layers):
                gx, gy, gw, gh = lyr['x'], lyr['y'], lyr['w'], lyr['h']
                gcy = gy + gh / 2.0

                # Snap center
                ok, d, target = gimp_snap_distance(yc, gcy, self.epsilon, mindist_y)
                if ok:
                    mindist_y = d
                    ty1 = round(y1 + (target - yc))
                    snapped_y = True
                    snapped_layer_v = idx
                    snap_side_v = "HCENTER"

                # Snap top to gy
                ok, d, target = gimp_snap_distance(y1, gy, self.epsilon, mindist_y)
                if ok:
                    mindist_y = d
                    ty1 = target
                    snapped_y = True
                    snapped_layer_v = idx
                    snap_side_v = "TOP"

                # Snap top to gy+gh
                ok, d, target = gimp_snap_distance(y1, gy + gh, self.epsilon, mindist_y)
                if ok:
                    mindist_y = d
                    ty1 = target
                    snapped_y = True
                    snapped_layer_v = idx
                    snap_side_v = "TOP"

                # Snap bottom to gy
                ok, d, target = gimp_snap_distance(y2, gy, self.epsilon, mindist_y)
                if ok:
                    mindist_y = d
                    ty1 = round(y1 + (target - y2))
                    snapped_y = True
                    snapped_layer_v = idx
                    snap_side_v = "BOTTOM"

                # Snap bottom to gy+gh
                ok, d, target = gimp_snap_distance(y2, gy + gh, self.epsilon, mindist_y)
                if ok:
                    mindist_y = d
                    ty1 = round(y1 + (target - y2))
                    snapped_y = True
                    snapped_layer_v = idx
                    snap_side_v = "BOTTOM"

        # Equidistance Snapping
        if snap_to_equidistance and len(self.layers) >= 2:
            # Check horizontal distribution (L1 - L2 - Dragged)
            # In gimpimage-snap.c: (gx+gw) < left_box_x1 -> strictly separated
            for i in range(len(self.layers)):
                for j in range(len(self.layers)):
                    if i == j:
                        continue
                    l1, l2 = self.layers[i], self.layers[j]
                    if l2['x'] >= (l1['x'] + l1['w']):
                        gap1 = l2['x'] - (l1['x'] + l1['w'])
                        target_x = (l2['x'] + l2['w']) + gap1
                        if abs(x1 - target_x) <= self.epsilon:
                            tx1 = target_x
                            snapped_x = True
                            equidist_h = {'l1': i, 'l2': j, 'gap': gap1}

        return {
            'snapped_x': snapped_x,
            'snapped_y': snapped_y,
            'tx1': tx1,
            'ty1': ty1,
            'snapped_layer_h': snapped_layer_h,
            'snapped_layer_v': snapped_layer_v,
            'snap_side_h': snap_side_h,
            'snap_side_v': snap_side_v,
            'equidist_h': equidist_h,
            'equidist_v': equidist_v,
        }


# ============================================================================
# Adversarial Test Suite
# ============================================================================

class TestPinchZoomMidpointStability(unittest.TestCase):
    """Adversarial stress-testing of pinch-to-zoom midpoint anchor invariance and bounds."""

    def test_midpoint_fixed_point_invariance(self):
        """
        Verify that zooming at any midpoint (x_mid, y_mid) preserves the underlying image point
        at exactly the same viewport location across arbitrary scale sequences.
        """
        initial_scale = 1.0
        offset_x, offset_y = 100.0, 150.0
        scale = initial_scale

        test_midpoints = [
            (0.0, 0.0),
            (320.0, 240.0),
            (960.0, 540.0),
            (1919.0, 1079.0),
            (12.345, 67.891),
            (-50.0, -100.0),
            (2500.0, 1800.0),
        ]

        for vx, vy in test_midpoints:
            orig_img_x = (vx + offset_x) / scale
            orig_img_y = (vy + offset_y) / scale

            pinch_deltas = [0.15, 0.25, -0.10, 0.50, -0.30, 0.05, -0.20, 0.40, -0.15, 0.10]
            cur_offset_x, cur_offset_y = offset_x, offset_y
            cur_scale = scale

            for delta in pinch_deltas:
                new_scale = gimp_zoom_model_zoom_step("PINCH", cur_scale, delta)
                cur_offset_x, cur_offset_y = gimp_display_shell_scale_to_sim(
                    cur_scale, cur_offset_x, cur_offset_y, new_scale, vx, vy
                )
                cur_scale = new_scale

                cur_vp_x = orig_img_x * cur_scale - cur_offset_x
                cur_vp_y = orig_img_y * cur_scale - cur_offset_y

                self.assertAlmostEqual(
                    cur_vp_x, vx, delta=1e-9,
                    msg=f"Midpoint X drifted: {cur_vp_x} vs {vx} at scale {cur_scale}"
                )
                self.assertAlmostEqual(
                    cur_vp_y, vy, delta=1e-9,
                    msg=f"Midpoint Y drifted: {cur_vp_y} vs {vy} at scale {cur_scale}"
                )

    def test_extreme_scale_boundaries_and_clamping(self):
        """Test zooming with extreme ratios (1e-6 to 1e6) and verify clamping to [ZOOM_MIN, ZOOM_MAX]."""
        z_huge = gimp_zoom_model_zoom_step("PINCH", 1.0, 1000.0)
        self.assertAlmostEqual(z_huge, ZOOM_MAX)
        self.assertTrue(ZOOM_MIN <= z_huge <= ZOOM_MAX)

        z_tiny = gimp_zoom_model_zoom_step("PINCH", 1.0, -1000.0)
        self.assertAlmostEqual(z_tiny, ZOOM_MIN)
        self.assertTrue(ZOOM_MIN <= z_tiny <= ZOOM_MAX)

        z_max_more = gimp_zoom_model_zoom_step("PINCH", ZOOM_MAX, 2.0)
        self.assertEqual(z_max_more, ZOOM_MAX)

        z_min_less = gimp_zoom_model_zoom_step("PINCH", ZOOM_MIN, -2.0)
        self.assertEqual(z_min_less, ZOOM_MIN)

    def test_zero_delta_and_negative_coordinates(self):
        """Test zero scale delta (no change) and negative viewport coordinates."""
        scale = 2.0
        new_scale = gimp_zoom_model_zoom_step("PINCH", scale, 0.0)
        self.assertEqual(new_scale, scale)

        off_x, off_y = gimp_display_shell_scale_to_sim(1.0, 50.0, 50.0, 2.0, -100.0, -200.0)
        self.assertFalse(math.isnan(off_x))
        self.assertFalse(math.isnan(off_y))
        self.assertFalse(math.isinf(off_x))
        self.assertFalse(math.isinf(off_y))


class TestAngleNormalizationAndCardinalSnapping(unittest.TestCase):
    """Adversarial stress-testing of continuous canvas rotation, magnetic cardinal snapping, and Ctrl stepping."""

    def test_multi_revolution_angle_normalization(self):
        """Test normalization across multi-revolution angles from -720° to +720°."""
        for rev in range(-4, 5):
            base = rev * 360.0
            for card in [0.0, 90.0, 180.0, 270.0]:
                angle = base + card
                snapped = gimp_rotate_gesture_calc_angle(angle, constrain=False)
                self.assertAlmostEqual(snapped % 90.0, 0.0, delta=1e-6)

    def test_cardinal_snap_exact_tolerance_boundaries(self):
        """
        Test exact ±3.0° tolerance threshold boundaries around 0°, 90°, 180°, 270°.
        Inside tolerance: snaps to cardinal.
        Outside tolerance: free rotation.
        """
        cardinals = [0.0, 90.0, 180.0, 270.0, 360.0]

        for card in cardinals:
            inside_pos = card + 2.99
            snapped_pos = gimp_rotate_gesture_calc_angle(inside_pos, constrain=False)
            self.assertAlmostEqual(
                snapped_pos % 360.0, card % 360.0, delta=1e-5,
                msg=f"Failed to snap inside positive tolerance: {inside_pos} -> {snapped_pos}"
            )

            inside_neg = card - 2.99
            snapped_neg = gimp_rotate_gesture_calc_angle(inside_neg, constrain=False)
            self.assertAlmostEqual(
                snapped_neg % 360.0, card % 360.0, delta=1e-5,
                msg=f"Failed to snap inside negative tolerance: {inside_neg} -> {snapped_neg}"
            )

            outside_pos = card + 3.01
            snapped_out_pos = gimp_rotate_gesture_calc_angle(outside_pos, constrain=False)
            self.assertAlmostEqual(
                snapped_out_pos, outside_pos, delta=1e-5,
                msg=f"Should NOT snap outside positive tolerance: {outside_pos} -> {snapped_out_pos}"
            )

            outside_neg = card - 3.01
            snapped_out_neg = gimp_rotate_gesture_calc_angle(outside_neg, constrain=False)
            self.assertAlmostEqual(
                snapped_out_neg, outside_neg, delta=1e-5,
                msg=f"Should NOT snap outside negative tolerance: {outside_neg} -> {snapped_out_neg}"
            )

    def test_ctrl_15_degree_step_quantization(self):
        """Test 15° step quantization when Ctrl is held (constrain=True)."""
        test_angles = [
            (-735.0, -735.0),
            (-727.0, -720.0),
            (-46.0, -45.0),
            (-14.0, -15.0),
            (-7.4, 0.0),
            (-7.6, -15.0),
            (0.0, 0.0),
            (7.4, 0.0),
            (7.6, 15.0),
            (14.0, 15.0),
            (22.0, 15.0),
            (23.0, 30.0),
            (44.0, 45.0),
            (89.0, 90.0),
            (367.0, 360.0),
            (722.0, 720.0),
        ]

        for raw_a, expected_a in test_angles:
            quantized = gimp_rotate_gesture_calc_angle(raw_a, constrain=True)
            self.assertAlmostEqual(
                quantized, expected_a, delta=1e-5,
                msg=f"Ctrl quantization failed for {raw_a}: got {quantized}, expected {expected_a}"
            )
            self.assertAlmostEqual(
                quantized % 15.0, 0.0, delta=1e-5,
                msg=f"Quantized angle {quantized} is not a multiple of 15.0°"
            )


class TestKineticPanPhysicsDecay(unittest.TestCase):
    """Adversarial stress-testing of kinetic deceleration physics simulation."""

    def test_smooth_monotonic_decay_and_convergence(self):
        """
        Verify that starting from arbitrary velocity, the kinetic simulation:
        1. Decays strictly monotonically (|v_{k+1}| < |v_k|).
        2. Never produces NaN or Inf.
        3. Converges to 0 and terminates within bounded time.
        4. Total displacement matches analytical integral: s_inf = v_0 / (friction * 1000).
        """
        initial_velocities = [
            (50.0, 0.0),
            (0.0, -120.0),
            (500.0, 300.0),
            (-1500.0, 2000.0),
            (10000.0, -10000.0),
        ]

        for v0_x, v0_y in initial_velocities:
            vx, vy = v0_x, v0_y
            total_dx, total_dy = 0.0, 0.0
            frames = 0
            max_frames = 1000

            gamma = KINETIC_PAN_FRICTION * 1000.0  # 5.0 s^-1
            expected_total_dx = v0_x / gamma
            expected_total_dy = v0_y / gamma

            prev_speed = math.hypot(vx, vy)
            running = True

            while running and frames < max_frames:
                dt = 1.0 / 60.0  # 60 FPS
                vx, vy, dx, dy, running = gimp_kinetic_pan_step(vx, vy, dt)
                total_dx += dx
                total_dy += dy
                frames += 1

                cur_speed = math.hypot(vx, vy)
                if running:
                    self.assertLess(
                        cur_speed, prev_speed,
                        f"Non-monotonic speed increase: {cur_speed} >= {prev_speed}"
                    )
                prev_speed = cur_speed

            self.assertFalse(running, f"Kinetic pan failed to terminate in {max_frames} frames")
            self.assertLess(prev_speed, KINETIC_PAN_CUTOFF)

            if expected_total_dx != 0.0:
                self.assertAlmostEqual(total_dx / expected_total_dx, 1.0, delta=0.08)
            else:
                self.assertEqual(total_dx, 0.0)

            if expected_total_dy != 0.0:
                self.assertAlmostEqual(total_dy / expected_total_dy, 1.0, delta=0.08)
            else:
                self.assertEqual(total_dy, 0.0)

    def test_timing_jitter_and_frame_drop_robustness(self):
        """
        Test behavior under severe frame drops (dt > 0.1s) and clock jitter (dt <= 0.0s).
        The C code clamps invalid dt to 1/60s (0.01667s).
        """
        vx, vy = 1000.0, 1000.0

        vx_new, vy_new, dx, dy, _ = gimp_kinetic_pan_step(vx, vy, -0.05)
        self.assertFalse(math.isnan(vx_new))
        self.assertLess(math.hypot(vx_new, vy_new), math.hypot(vx, vy))

        vx_new2, vy_new2, dx2, dy2, _ = gimp_kinetic_pan_step(vx, vy, 10.0)
        self.assertFalse(math.isnan(vx_new2))
        self.assertGreater(math.hypot(vx_new2, vy_new2), 0.0)


class TestSmartSnappingGuidesMath(unittest.TestCase):
    """Adversarial testing of bounding box and equidistance snapping geometry."""

    def test_multi_layer_bounding_box_snapping(self):
        """Test snapping a moving layer against a complex multi-layer stack."""
        layers = [
            {'x': 100.0, 'y': 100.0, 'w': 200.0, 'h': 150.0},  # L0: x=[100..300], y=[100..250], cx=200, cy=175
            {'x': 500.0, 'y': 300.0, 'w': 100.0, 'h': 100.0},  # L1: x=[500..600], y=[300..400], cx=550, cy=350
            {'x': -200.0, 'y': -150.0, 'w': 150.0, 'h': 80.0}, # L2: x=[-200..-50], y=[-150..-70], cx=-125, cy=-110
        ]
        snapper = BBoxSnapper(layers, epsilon=8.0)

        # 1. Left-edge snap to L0 right edge (x=300) when at x=304
        res = snapper.snap_rectangle((304.0, 50.0, 404.0, 150.0))
        self.assertTrue(res['snapped_x'])
        self.assertEqual(res['tx1'], 300.0)
        self.assertEqual(res['snap_side_h'], "LEFT")

        # 2. Center-X snap to L1 center (cx=550) with moving box width=60 at x=518 (cx=548)
        res = snapper.snap_rectangle((518.0, 50.0, 578.0, 150.0))
        self.assertTrue(res['snapped_x'])
        self.assertEqual(res['tx1'], 520.0)  # 550 - 30 = 520
        self.assertEqual(res['snap_side_h'], "VCENTER")

        # 3. Negative coordinate snap to L2 left edge (x=-200) when at x=-196
        res = snapper.snap_rectangle((-196.0, 50.0, -96.0, 150.0))
        self.assertTrue(res['snapped_x'])
        self.assertEqual(res['tx1'], -200.0)

    def test_equidistance_gap_calculation_and_snapping(self):
        """Test equidistance distribution gap matching (L1 - L2 - Dragged)."""
        layers = [
            {'x': 100.0, 'y': 100.0, 'w': 100.0, 'h': 100.0},
            {'x': 260.0, 'y': 100.0, 'w': 100.0, 'h': 100.0},
        ]
        snapper = BBoxSnapper(layers, epsilon=8.0)

        res = snapper.snap_rectangle((423.0, 100.0, 523.0, 200.0), snap_to_bbox=False, snap_to_equidistance=True)
        self.assertTrue(res['snapped_x'])
        self.assertEqual(res['tx1'], 420.0)
        self.assertIsNotNone(res['equidist_h'])
        self.assertEqual(res['equidist_h']['gap'], 60.0)

    def test_zero_gap_and_abutting_layers(self):
        """Test zero-gap (touching/abutting) layers equidistance and bbox snapping."""
        layers = [
            {'x': 0.0, 'y': 0.0, 'w': 100.0, 'h': 100.0},
            {'x': 100.0, 'y': 0.0, 'w': 100.0, 'h': 100.0},  # Abutting L0 (gap=0)
        ]
        snapper = BBoxSnapper(layers, epsilon=8.0)

        # Dragged box near x=202 -> Target x = 200 (gap=0)
        res = snapper.snap_rectangle((203.0, 0.0, 303.0, 100.0), snap_to_bbox=False, snap_to_equidistance=True)
        self.assertTrue(res['snapped_x'])
        self.assertEqual(res['tx1'], 200.0)
        self.assertEqual(res['equidist_h']['gap'], 0.0)

    def test_full_span_alignment_line_geometry(self):
        """Test vertical/horizontal alignment guide spanning math: y_min = min(y, gy), y_max = max(y+h, gy+gh)."""
        y, h = 200, 50
        gy, gh = 50, 60

        y_min = min(y, gy)
        y_max = max(y + h, gy + gh)

        self.assertEqual(y_min, 50)
        self.assertEqual(y_max, 250)
        self.assertEqual(y_max - y_min, 200)


def run_all_challenger_tests() -> unittest.TestResult:
    """Executes all challenger test suites and reports empirical metrics."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPinchZoomMidpointStability))
    suite.addTests(loader.loadTestsFromTestCase(TestAngleNormalizationAndCardinalSnapping))
    suite.addTests(loader.loadTestsFromTestCase(TestKineticPanPhysicsDecay))
    suite.addTests(loader.loadTestsFromTestCase(TestSmartSnappingGuidesMath))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    res = run_all_challenger_tests()
    sys.exit(0 if res.wasSuccessful() else 1)
