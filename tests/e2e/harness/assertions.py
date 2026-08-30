"""
Domain-Specific E2E Assertions for GIMP + PhotoGIMP Modernization.
Provides assertions for GTK4 widget hierarchies, GEGL node graphs, CIE Delta E color differences,
PhotoGIMP shortcut bindings, non-destructive layer stack integrity, memory stability, and FPS budgets.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from .fps_profiler import FrameMetrics, assert_fps_budget
from .leak_checker import MemorySnapshot, assert_memory_stable


# ---------------------------------------------------------------------------
# 1. Color Science: sRGB to CIELAB & CIEDE2000
# ---------------------------------------------------------------------------

def srgb_to_xyz(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Converts sRGB [0..1] to CIE 1931 XYZ with standard D65 illuminant."""
    def pivot_srgb(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)

    r_lin = pivot_srgb(r) * 100.0
    g_lin = pivot_srgb(g) * 100.0
    b_lin = pivot_srgb(b) * 100.0

    # sRGB D65 transformation matrix
    x = r_lin * 0.4124564 + g_lin * 0.3575761 + b_lin * 0.1804375
    y = r_lin * 0.2126729 + g_lin * 0.7151522 + b_lin * 0.0721750
    z = r_lin * 0.0193339 + g_lin * 0.1191920 + b_lin * 0.9503041
    return x, y, z


def xyz_to_lab(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Converts CIE XYZ to CIE L*a*b* using D65 reference white point."""
    # Standard D65 2-degree observer reference white
    xn, yn, zn = 95.047, 100.000, 108.883

    def pivot_xyz(t: float) -> float:
        delta = 6.0 / 29.0
        return math.pow(t, 1.0 / 3.0) if t > delta**3 else (t / (3.0 * delta**2)) + (4.0 / 29.0)

    fx = pivot_xyz(x / xn)
    fy = pivot_xyz(y / yn)
    fz = pivot_xyz(z / zn)

    l_star = max(0.0, (116.0 * fy) - 16.0)
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)
    return l_star, a_star, b_star


def rgb_to_lab(rgb: Sequence[Union[int, float]]) -> Tuple[float, float, float]:
    """Converts RGB (0-255 or 0.0-1.0) to CIELAB (L*, a*, b*)."""
    r, g, b = rgb[0], rgb[1], rgb[2]
    # Normalize if 0-255
    if any(c > 1.0 for c in (r, g, b)):
        r, g, b = r / 255.0, g / 255.0, b / 255.0
    x, y, z = srgb_to_xyz(r, g, b)
    return xyz_to_lab(x, y, z)


def delta_e_ciede2000(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """
    Computes the CIEDE2000 (CIE Delta E 2000) color difference between two CIELAB colors.
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    avg_l = (l1 + l2) / 2.0
    c1 = math.sqrt(a1**2 + b1**2)
    c2 = math.sqrt(a2**2 + b2**2)
    avg_c = (c1 + c2) / 2.0

    g = 0.5 * (1.0 - math.sqrt((avg_c**7) / (avg_c**7 + 25.0**7))) if avg_c > 0 else 0.0
    a1_prime = (1.0 + g) * a1
    a2_prime = (1.0 + g) * a2

    c1_prime = math.sqrt(a1_prime**2 + b1**2)
    c2_prime = math.sqrt(a2_prime**2 + b2**2)
    avg_c_prime = (c1_prime + c2_prime) / 2.0

    def compute_h_prime(a_p: float, b_val: float) -> float:
        if a_p == 0 and b_val == 0:
            return 0.0
        h_rad = math.atan2(b_val, a_p)
        h_deg = math.degrees(h_rad)
        return h_deg if h_deg >= 0 else h_deg + 360.0

    h1_prime = compute_h_prime(a1_prime, b1)
    h2_prime = compute_h_prime(a2_prime, b2)

    delta_h_prime = 0.0
    if c1_prime != 0 and c2_prime != 0:
        if abs(h1_prime - h2_prime) <= 180.0:
            delta_h_prime = h2_prime - h1_prime
        elif h2_prime <= h1_prime:
            delta_h_prime = h2_prime - h1_prime + 360.0
        else:
            delta_h_prime = h2_prime - h1_prime - 360.0

    delta_l_prime = l2 - l1
    delta_c_prime = c2_prime - c1_prime
    delta_capital_h_prime = 2.0 * math.sqrt(c1_prime * c2_prime) * math.sin(math.radians(delta_h_prime / 2.0))

    avg_l_prime = (l1 + l2) / 2.0
    avg_h_prime = 0.0
    if c1_prime != 0 and c2_prime != 0:
        if abs(h1_prime - h2_prime) <= 180.0:
            avg_h_prime = (h1_prime + h2_prime) / 2.0
        elif h1_prime + h2_prime < 360.0:
            avg_h_prime = (h1_prime + h2_prime + 360.0) / 2.0
        else:
            avg_h_prime = (h1_prime + h2_prime - 360.0) / 2.0

    t = (
        1.0
        - 0.17 * math.cos(math.radians(avg_h_prime - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * avg_h_prime))
        + 0.32 * math.cos(math.radians(3.0 * avg_h_prime + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * avg_h_prime - 63.0))
    )

    delta_theta = 30.0 * math.exp(-(((avg_h_prime - 275.0) / 25.0) ** 2))
    rc = 2.0 * math.sqrt((avg_c_prime**7) / (avg_c_prime**7 + 25.0**7)) if avg_c_prime > 0 else 0.0

    sl = 1.0 + ((0.015 * ((avg_l_prime - 50.0) ** 2)) / math.sqrt(20.0 + ((avg_l_prime - 50.0) ** 2)))
    sc = 1.0 + 0.045 * avg_c_prime
    sh = 1.0 + 0.015 * avg_c_prime * t
    rt = -math.sin(math.radians(2.0 * delta_theta)) * rc

    kl, kc, kh = 1.0, 1.0, 1.0
    term_l = delta_l_prime / (kl * sl)
    term_c = delta_c_prime / (kc * sc)
    term_h = delta_capital_h_prime / (kh * sh)

    delta_e = math.sqrt(term_l**2 + term_c**2 + term_h**2 + rt * term_c * term_h)
    return delta_e


def assert_color_delta_e(
    color1: Sequence[Union[int, float]],
    color2: Sequence[Union[int, float]],
    max_delta_e: float = 1.5,
    message: Optional[str] = None,
):
    """
    Asserts that the perceptual color difference (CIEDE2000 Delta E) between two colors is within tolerance.
    """
    lab1 = rgb_to_lab(color1)
    lab2 = rgb_to_lab(color2)
    de = delta_e_ciede2000(lab1, lab2)

    if de > max_delta_e:
        msg = (
            message or f"Color difference assertion failed: CIEDE2000 ΔE = {de:.3f} > max allowed {max_delta_e:.3f}\n"
            f"Color 1: {color1} -> Lab {lab1}\n"
            f"Color 2: {color2} -> Lab {lab2}"
        )
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# 2. GTK4 Widget Tree Assertions
# ---------------------------------------------------------------------------

def assert_gtk4_widget_tree(
    root_widget_info: Dict[str, Any],
    expected_structure: Dict[str, Any],
    path: str = "root",
):
    """
    Recursively validates a GTK4 widget hierarchy structure, classes, properties, and child items.
    """
    if "type" in expected_structure:
        actual_type = root_widget_info.get("type")
        expected_type = expected_structure["type"]
        if actual_type != expected_type:
            raise AssertionError(
                f"Widget type mismatch at '{path}': expected '{expected_type}', found '{actual_type}'"
            )

    if "classes" in expected_structure:
        actual_classes = set(root_widget_info.get("classes", []))
        expected_classes = set(expected_structure["classes"])
        if not expected_classes.issubset(actual_classes):
            missing = expected_classes - actual_classes
            raise AssertionError(
                f"Widget CSS classes mismatch at '{path}': missing classes {missing} in actual {actual_classes}"
            )

    if "properties" in expected_structure:
        actual_props = root_widget_info.get("properties", {})
        for prop_name, prop_val in expected_structure["properties"].items():
            if prop_name not in actual_props:
                raise AssertionError(f"Property '{prop_name}' missing on widget at '{path}'")
            if actual_props[prop_name] != prop_val:
                raise AssertionError(
                    f"Property '{prop_name}' mismatch at '{path}': expected '{prop_val}', found '{actual_props[prop_name]}'"
                )

    if "children" in expected_structure:
        actual_children = root_widget_info.get("children", [])
        expected_children = expected_structure["children"]
        if len(actual_children) < len(expected_children):
            raise AssertionError(
                f"Child count mismatch at '{path}': expected at least {len(expected_children)}, found {len(actual_children)}"
            )
        for idx, exp_child in enumerate(expected_children):
            assert_gtk4_widget_tree(actual_children[idx], exp_child, path=f"{path}.child[{idx}]")


# ---------------------------------------------------------------------------
# 3. GEGL Graph Topology Assertions
# ---------------------------------------------------------------------------

def assert_gegl_graph_valid(
    graph_descriptor: Dict[str, Any],
    expected_nodes: Optional[List[Dict[str, Any]]] = None,
    expected_connections: Optional[List[Tuple[str, str, str, str]]] = None,
):
    """
    Validates the structure and acyclicity of a GEGL operation graph.
    - expected_nodes: list of {'id': str, 'operation': str, 'properties': dict}
    - expected_connections: list of (src_node_id, src_pad, dest_node_id, dest_pad)
    """
    nodes = {n["id"]: n for n in graph_descriptor.get("nodes", [])}
    connections = graph_descriptor.get("connections", [])

    if expected_nodes:
        for exp_node in expected_nodes:
            nid = exp_node["id"]
            if nid not in nodes:
                raise AssertionError(f"Expected GEGL node '{nid}' not found in graph")
            actual_node = nodes[nid]
            if "operation" in exp_node and actual_node.get("operation") != exp_node["operation"]:
                raise AssertionError(
                    f"Node '{nid}' operation mismatch: expected '{exp_node['operation']}', found '{actual_node.get('operation')}'"
                )
            if "properties" in exp_node:
                for k, v in exp_node["properties"].items():
                    act_v = actual_node.get("properties", {}).get(k)
                    if act_v != v:
                        raise AssertionError(
                            f"Node '{nid}' property '{k}' mismatch: expected '{v}', found '{act_v}'"
                        )

    if expected_connections:
        conn_set = {(c[0], c[1], c[2], c[3]) for c in connections}
        for exp_conn in expected_connections:
            if exp_conn not in conn_set:
                raise AssertionError(
                    f"Expected GEGL connection {exp_conn[0]}:{exp_conn[1]} -> {exp_conn[2]}:{exp_conn[3]} not found in graph"
                )

    # Check for topological cycle
    adj = {nid: [] for nid in nodes}
    for c in connections:
        src, _, dst, _ = c
        if src in adj and dst in adj:
            adj[src].append(dst)

    visited = {}  # 0=unvisited, 1=visiting, 2=visited
    def has_cycle(node: str) -> bool:
        visited[node] = 1
        for neighbor in adj.get(node, []):
            if visited.get(neighbor) == 1:
                return True
            if visited.get(neighbor) != 2 and has_cycle(neighbor):
                return True
        visited[node] = 2
        return False

    for nid in nodes:
        if visited.get(nid) != 2:
            if has_cycle(nid):
                raise AssertionError(f"Cycle detected in GEGL graph involving node '{nid}'")


# ---------------------------------------------------------------------------
# 4. Shortcut / Keybinding Mapping Assertions
# ---------------------------------------------------------------------------

def parse_shortcut_file(filepath_or_content: Union[str, Path]) -> Dict[str, str]:
    """
    Parses a GIMP shortcutsrc or menurc file into a mapping of action -> accelerator.
    Handles entries like (gtk_accel_path "<Actions>/image/image-transform-free" "<Primary>t").
    """
    if isinstance(filepath_or_content, Path) or (isinstance(filepath_or_content, str) and os.path.exists(filepath_or_content)):
        content = Path(filepath_or_content).read_text(encoding="utf-8", errors="replace")
    else:
        content = str(filepath_or_content)

    mapping: Dict[str, str] = {}
    pattern = re.compile(r'\(gtk_accel_path\s+"([^"]+)"\s+"([^"]*)"\)')
    for match in pattern.finditer(content):
        action_path, accel = match.groups()
        mapping[action_path] = accel
    return mapping


def assert_shortcut_mapping(
    shortcut_source: Union[str, Path, Dict[str, str]],
    expected_mappings: Dict[str, str],
):
    """
    Asserts that action shortcuts match the expected accelerator strings.
    """
    actual_map = shortcut_source if isinstance(shortcut_source, dict) else parse_shortcut_file(shortcut_source)

    for action, exp_accel in expected_mappings.items():
        # Look for exact or partial action match
        matched_accel = None
        for act_path, act_accel in actual_map.items():
            if action == act_path or act_path.endswith(action) or action in act_path:
                matched_accel = act_accel
                break

        if matched_accel is None:
            raise AssertionError(f"Shortcut action '{action}' was not found in shortcut table")
        if matched_accel != exp_accel:
            raise AssertionError(
                f"Shortcut mapping mismatch for '{action}': expected '{exp_accel}', found '{matched_accel}'"
            )


# ---------------------------------------------------------------------------
# 5. Non-Destructive Stack Integrity Assertions
# ---------------------------------------------------------------------------

def assert_non_destructive_stack(
    base_layer_buffer: bytes,
    original_base_hash: str,
    stack_output_buffer: Optional[bytes] = None,
):
    """
    Verifies that non-destructive adjustment layers or live layer effects do NOT
    mutate the original base pixel buffer.
    """
    import hashlib
    current_base_hash = hashlib.sha256(base_layer_buffer).hexdigest()
    if current_base_hash != original_base_hash:
        raise AssertionError(
            "Non-destructive stack integrity violated: base layer pixel buffer was mutated!\n"
            f"Original SHA-256: {original_base_hash}\n"
            f"Mutated SHA-256 : {current_base_hash}"
        )
    if stack_output_buffer is not None:
        output_hash = hashlib.sha256(stack_output_buffer).hexdigest()
        if output_hash == original_base_hash:
            raise AssertionError(
                "Stack composite output is identical to base layer; adjustments or effects were not rendered!"
            )
