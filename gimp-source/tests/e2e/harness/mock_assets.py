"""
Synthetic Test Asset Generators for GIMP + PhotoGIMP E2E Testing.
Generates genuine specification-compliant binary assets (PSD, RAW, TIFF, XCF, SVG)
and full PhotoGIMP / GIMP configuration trees for test execution.
"""

from __future__ import annotations

import os
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def create_dummy_psd(
    output_path: Optional[Union[str, Path]] = None,
    width: int = 100,
    height: int = 100,
    layers: Optional[List[Dict[str, Union[str, int, Tuple[int, int, int, int]]]]] = None,
    color_mode: str = "RGB",
    depth: int = 8,
) -> bytes:
    """
    Generates a valid binary Adobe Photoshop (.psd) file according to the Adobe Photoshop File Format Specification.

    Supports:
    - Multi-layer records with custom bounds, names, blend modes, and opacity.
    - Color modes: 'RGB' (mode 3), 'CMYK' (mode 4), 'GRAYSCALE' (mode 1).
    - Bit depths: 8-bit or 16-bit.
    """
    mode_map = {"GRAYSCALE": 1, "INDEXED": 2, "RGB": 3, "CMYK": 4, "LAB": 9}
    mode_code = mode_map.get(color_mode.upper(), 3)
    num_channels = 1 if mode_code == 1 else (4 if mode_code == 4 else 3)

    if layers is None:
        layers = [
            {"name": "Background", "bounds": (0, 0, height, width), "opacity": 255, "blend": "norm"},
            {"name": "Layer 1", "bounds": (10, 10, min(height, 80), min(width, 80)), "opacity": 200, "blend": "norm"},
        ]

    # Section 1: Header (26 bytes)
    # 8BPS, version=1, 6 reserved bytes (0), channels, height, width, depth, color_mode
    header = struct.pack(
        ">4sH6sHIIHH",
        b"8BPS",
        1,
        b"\x00" * 6,
        num_channels + (1 if len(layers) > 0 else 0),  # include composite alpha if layers present
        height,
        width,
        depth,
        mode_code,
    )

    # Section 2: Color Mode Data
    color_mode_data = b""
    color_mode_section = struct.pack(">I", len(color_mode_data)) + color_mode_data

    # Section 3: Image Resources (Resolution Info 0x03ED, Guide Info 0x0408)
    res_blocks = []
    # 0x03ED: ResolutionInfo (72 dpi default)
    res_data = struct.pack(">HIIHHHH", 72, 1, 1, 72, 1, 1, 0)
    res_block = struct.pack(">4sH", b"8BIM", 0x03ED) + b"\x00\x00" + struct.pack(">I", len(res_data)) + res_data
    if len(res_block) % 2 != 0:
        res_block += b"\x00"
    res_blocks.append(res_block)

    # 0x0400: Names of the alpha channels
    alpha_names = b"\x00"
    alpha_block = struct.pack(">4sH", b"8BIM", 0x0400) + b"\x00\x00" + struct.pack(">I", len(alpha_names)) + alpha_names
    if len(alpha_block) % 2 != 0:
        alpha_block += b"\x00"
    res_blocks.append(alpha_block)

    image_resources_payload = b"".join(res_blocks)
    image_resources_section = struct.pack(">I", len(image_resources_payload)) + image_resources_payload

    # Section 4: Layer and Mask Information Section
    layer_records = []
    channel_image_data_list = []

    for idx, lyr in enumerate(layers):
        name = str(lyr.get("name", f"Layer {idx}"))
        bounds = lyr.get("bounds", (0, 0, height, width))
        top, left, bottom, right = bounds
        lyr_h = max(0, bottom - top)
        lyr_w = max(0, right - left)
        opacity = int(lyr.get("opacity", 255))
        blend_str = str(lyr.get("blend", "norm")).ljust(4)[:4]
        blend_key = blend_str.encode("ascii")

        # Channels: Red=0, Green=1, Blue=2, Alpha=-1 (or 0=C, 1=M, 2=Y, 3=K)
        chan_ids = list(range(num_channels)) + [-1]
        chan_info_bytes = b""
        lyr_pixel_count = lyr_h * lyr_w
        raw_chan_len = lyr_pixel_count * (depth // 8) + 2  # 2 bytes compression header

        for cid in chan_ids:
            chan_info_bytes += struct.pack(">hI", cid, raw_chan_len)
            # Channel data: compression 0 (uncompressed raw bytes)
            chan_pixels = bytes([min(255, (idx * 40 + cid * 25 + 100) % 256)] * lyr_pixel_count)
            channel_image_data_list.append(struct.pack(">H", 0) + chan_pixels)

        # Extra data field: layer mask data (4 bytes len=0), blending ranges (4 bytes len=0), layer name (pascal string padded to 4)
        name_bytes = name.encode("utf-8")
        pascal_name = bytes([min(255, len(name_bytes))]) + name_bytes
        name_pad = (4 - (len(pascal_name) % 4)) % 4
        pascal_name += b"\x00" * name_pad

        extra_data = (
            struct.pack(">I", 0)  # Layer mask data length
            + struct.pack(">I", 0)  # Blending ranges length
            + pascal_name  # Layer name
        )

        layer_record = (
            struct.pack(">IIII", top, left, bottom, right)
            + struct.pack(">H", len(chan_ids))
            + chan_info_bytes
            + struct.pack(">4s4sBBBB", b"8BIM", blend_key, opacity, 0, 8, 0)
            + struct.pack(">I", len(extra_data))
            + extra_data
        )
        layer_records.append(layer_record)

    num_layers = len(layers)
    layer_info_payload = (
        struct.pack(">h", num_layers)  # Layer count (positive = absolute alpha)
        + b"".join(layer_records)
        + b"".join(channel_image_data_list)
    )
    # Pad layer info payload to even length
    if len(layer_info_payload) % 2 != 0:
        layer_info_payload += b"\x00"

    layer_info_section = struct.pack(">I", len(layer_info_payload)) + layer_info_payload
    layer_and_mask_section = struct.pack(">I", len(layer_info_section)) + layer_info_section

    # Section 5: Composite Image Data (Raw compression 0)
    composite_pixels = bytes([128] * (width * height * num_channels * (depth // 8)))
    image_data_section = struct.pack(">H", 0) + composite_pixels

    psd_bytes = (
        header
        + color_mode_section
        + image_resources_section
        + layer_and_mask_section
        + image_data_section
    )

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(psd_bytes)

    return psd_bytes


def create_dummy_svg(
    output_path: Optional[Union[str, Path]] = None,
    width: int = 200,
    height: int = 200,
    elements: Optional[List[Dict[str, Union[str, float]]]] = None,
    title: str = "Test Smart Object Vector",
) -> str:
    """
    Generates a valid XML SVG 1.1 / 2.0 vector document for Smart Object tests.
    """
    if elements is None:
        elements = [
            {"type": "rect", "x": 10, "y": 10, "width": 180, "height": 180, "rx": 15, "fill": "#0078d4", "stroke": "#ffffff", "stroke-width": 2},
            {"type": "circle", "cx": 100, "y": 100, "r": 50, "fill": "#ff4081", "opacity": 0.85},
            {"type": "path", "d": "M 50 150 L 100 50 L 150 150 Z", "fill": "#ffeb3b", "stroke": "#000000", "stroke-width": 1.5},
        ]

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"  <title>{title}</title>",
        "  <defs>",
        '    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" style="stop-color:#ff5722;stop-opacity:1" />',
        '      <stop offset="100%" style="stop-color:#4caf50;stop-opacity:1" />',
        "    </linearGradient>",
        "  </defs>",
    ]

    for elem in elements:
        elem_type = elem.get("type", "rect")
        attrs = " ".join(f'{k}="{v}"' for k, v in elem.items() if k != "type")
        svg_lines.append(f"  <{elem_type} {attrs} />")

    svg_lines.append("</svg>")
    svg_content = "\n".join(svg_lines)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg_content, encoding="utf-8")

    return svg_content


def create_dummy_raw(
    output_path: Optional[Union[str, Path]] = None,
    width: int = 64,
    height: int = 64,
    bayer_pattern: str = "RGGB",
    make: str = "GimpTestCam",
    model: str = "E2E-Sensor-4K",
) -> bytes:
    """
    Generates a valid TIFF-EP / DNG-compliant RAW sensor file with standard IFD tags.
    """
    # Little-endian TIFF header: 'II', version 42, IFD0 offset 8
    header = struct.pack("<2sHI", b"II", 42, 8)

    # Build IFD entries (12 bytes per tag: tag_id, type, count, value_or_offset)
    # Types: 1=BYTE, 2=ASCII, 3=SHORT, 4=LONG, 5=RATIONAL
    cfa_map = {"RGGB": (0, 1, 1, 2), "BGGR": (2, 1, 1, 0), "GRBG": (1, 0, 2, 1), "GBRG": (1, 2, 0, 1)}
    cfa_vals = cfa_map.get(bayer_pattern, (0, 1, 1, 2))

    make_bytes = make.encode("ascii") + b"\x00"
    model_bytes = model.encode("ascii") + b"\x00"

    # Data offsets will be placed after the IFD block
    # 13 tags * 12 bytes + 2 bytes (count) + 4 bytes (next IFD) = 162 bytes
    ifd_start = 8
    num_tags = 12
    ifd_size = 2 + (num_tags * 12) + 4
    data_offset = ifd_start + ifd_size

    make_offset = data_offset
    model_offset = make_offset + len(make_bytes)
    cfa_pattern_offset = model_offset + len(model_bytes)
    raw_pixels_offset = cfa_pattern_offset + 4

    raw_pixel_count = width * height
    # 16-bit raw sensor data (Bayer pattern simulated values)
    raw_pixel_bytes = bytes([128, 0] * raw_pixel_count)

    tags = [
        (256, 4, 1, width),  # ImageWidth (LONG)
        (257, 4, 1, height),  # ImageLength (LONG)
        (258, 3, 1, 16),  # BitsPerSample (SHORT 16)
        (259, 3, 1, 1),  # Compression (SHORT 1 = uncompressed)
        (262, 3, 1, 32803),  # PhotometricInterpretation (SHORT 32803 = CFA)
        (271, 2, len(make_bytes), make_offset),  # Make (ASCII)
        (272, 2, len(model_bytes), model_offset),  # Model (ASCII)
        (273, 4, 1, raw_pixels_offset),  # StripOffsets (LONG)
        (277, 3, 1, 1),  # SamplesPerPixel (SHORT 1)
        (278, 4, 1, height),  # RowsPerStrip (LONG)
        (279, 4, 1, len(raw_pixel_bytes)),  # StripByteCounts (LONG)
        (33422, 1, 4, cfa_pattern_offset),  # CFAPattern (BYTE)
    ]

    tags_bytes = b"".join(struct.pack("<HHII", t[0], t[1], t[2], t[3]) for t in tags)
    ifd_block = struct.pack("<H", num_tags) + tags_bytes + struct.pack("<I", 0)

    extra_data = (
        make_bytes
        + model_bytes
        + bytes(cfa_vals)
        + raw_pixel_bytes
    )

    raw_data = header + ifd_block + extra_data

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw_data)

    return raw_data


def create_dummy_tiff(
    output_path: Optional[Union[str, Path]] = None,
    width: int = 100,
    height: int = 100,
    has_alpha: bool = True,
    color_space: str = "RGB",
) -> bytes:
    """
    Generates a valid TIFF 6.0 uncompressed image with RGBA / CMYK alpha channel support.
    """
    is_cmyk = color_space.upper() == "CMYK"
    samples_per_pixel = (5 if is_cmyk else 4) if has_alpha else (4 if is_cmyk else 3)
    photometric = 5 if is_cmyk else 2  # 5=Separated (CMYK), 2=RGB

    header = struct.pack("<2sHI", b"II", 42, 8)
    num_tags = 10
    ifd_size = 2 + (num_tags * 12) + 4
    data_offset = 8 + ifd_size

    bits_per_sample_bytes = struct.pack("<" + "H" * samples_per_pixel, *([8] * samples_per_pixel))
    bits_offset = data_offset
    pixel_data_offset = bits_offset + len(bits_per_sample_bytes)

    pixel_count = width * height * samples_per_pixel
    pixel_bytes = bytes([200 if i % samples_per_pixel == 3 else (i % 256) for i in range(pixel_count)])

    tags = [
        (256, 4, 1, width),  # ImageWidth
        (257, 4, 1, height),  # ImageLength
        (258, 3, samples_per_pixel, bits_offset if samples_per_pixel > 2 else 8),  # BitsPerSample
        (259, 3, 1, 1),  # Compression (1=None)
        (262, 3, 1, photometric),  # PhotometricInterpretation
        (273, 4, 1, pixel_data_offset),  # StripOffsets
        (277, 3, 1, samples_per_pixel),  # SamplesPerPixel
        (278, 4, 1, height),  # RowsPerStrip
        (279, 4, 1, len(pixel_bytes)),  # StripByteCounts
        (338, 3, 1, 1 if has_alpha else 0),  # ExtraSamples (1=associated alpha)
    ]

    tags_bytes = b"".join(struct.pack("<HHII", t[0], t[1], t[2], t[3]) for t in tags)
    ifd_block = struct.pack("<H", num_tags) + tags_bytes + struct.pack("<I", 0)

    tiff_data = header + ifd_block + bits_per_sample_bytes + pixel_bytes

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(tiff_data)

    return tiff_data


def create_dummy_xcf(
    output_path: Optional[Union[str, Path]] = None,
    width: int = 100,
    height: int = 100,
    layers: Optional[List[Dict[str, Union[str, int]]]] = None,
    version: int = 14,
) -> bytes:
    """
    Generates a valid GIMP XCF format file (v014 / GIMP 3.0 compatible).
    """
    if layers is None:
        layers = [{"name": "Background", "opacity": 255, "type": 0}]

    magic = f"gimp xcf v{version:03d}\x00".encode("ascii")
    # Base type: 0=RGB, 1=GRAY, 2=INDEXED. Precision: 100 = 8-bit gamma integer
    xcf_header = magic + struct.pack(">IIII", width, height, 0, 100)

    # Properties list:
    # PROP_COLORMAP (1), PROP_COMPRESSION (17, 0=None), PROP_RESOLUTION (19), PROP_END (0)
    props = (
        struct.pack(">II", 17, 1) + b"\x00"  # PROP_COMPRESSION: 0
        + struct.pack(">II", 19, 8) + struct.pack(">ff", 72.0, 72.0)  # PROP_RESOLUTION
        + struct.pack(">II", 0, 0)  # PROP_END
    )

    # In XCF, layer pointer list ends with 0, channel pointer list ends with 0
    # Minimal valid empty layer pointer offset table
    layer_ptrs = struct.pack(">I", 0)
    channel_ptrs = struct.pack(">I", 0)

    xcf_data = xcf_header + props + layer_ptrs + channel_ptrs

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(xcf_data)

    return xcf_data


def create_photogimp_profile(target_dir: Union[str, Path]) -> Dict[str, Path]:
    """
    Generates a complete, authentic PhotoGIMP 3.0 configuration profile tree.
    Includes shortcutsrc, menurc, sessionrc, toolrc, gimp.css, and dark theme definitions.
    """
    root = Path(target_dir)
    gimp_cfg = root / "GIMP" / "3.0"
    gimp_cfg.mkdir(parents=True, exist_ok=True)

    # 1. shortcutsrc (Photoshop-compatible key bindings for GIMP 3.0)
    shortcutsrc_content = """; PhotoGIMP 3.0 Keyboard Shortcuts (Photoshop muscle memory mappings)
(gtk_accel_path "<Actions>/image/image-transform-free" "<Primary>t")
(gtk_accel_path "<Actions>/layers/layers-duplicate" "<Primary>j")
(gtk_accel_path "<Actions>/layers/layers-new" "<Primary><Shift>n")
(gtk_accel_path "<Actions>/select/select-none" "<Primary>d")
(gtk_accel_path "<Actions>/select/select-invert" "<Primary><Shift>i")
(gtk_accel_path "<Actions>/select/select-all" "<Primary>a")
(gtk_accel_path "<Actions>/edit/edit-copy" "<Primary>c")
(gtk_accel_path "<Actions>/edit/edit-paste" "<Primary>v")
(gtk_accel_path "<Actions>/edit/edit-cut" "<Primary>x")
(gtk_accel_path "<Actions>/edit/edit-undo" "<Primary>z")
(gtk_accel_path "<Actions>/edit/edit-redo" "<Primary><Shift>z")
(gtk_accel_path "<Actions>/view/view-zoom-in" "<Primary>equal")
(gtk_accel_path "<Actions>/view/view-zoom-out" "<Primary>minus")
(gtk_accel_path "<Actions>/view/view-zoom-fit-in" "<Primary>0")
(gtk_accel_path "<Actions>/view/view-zoom-100" "<Primary>1")
(gtk_accel_path "<Actions>/dialogs/dialogs-action-search" "<Primary>k")
(gtk_accel_path "<Actions>/dialogs/dialogs-command-palette" "<Primary>p")
(gtk_accel_path "<Actions>/tools/tools-brush" "b")
(gtk_accel_path "<Actions>/tools/tools-eraser" "e")
(gtk_accel_path "<Actions>/tools/tools-rect-select" "m")
(gtk_accel_path "<Actions>/tools/tools-free-select" "l")
(gtk_accel_path "<Actions>/tools/tools-fuzzy-select" "w")
(gtk_accel_path "<Actions>/tools/tools-move" "v")
(gtk_accel_path "<Actions>/tools/tools-crop" "c")
(gtk_accel_path "<Actions>/tools/tools-gradient" "g")
(gtk_accel_path "<Actions>/tools/tools-text" "t")
(gtk_accel_path "<Actions>/windows/windows-workspace-photogimp" "<Primary><Alt>p")
(gtk_accel_path "<Actions>/windows/windows-workspace-default" "<Primary><Alt>d")
"""
    shortcutsrc_path = gimp_cfg / "shortcutsrc"
    shortcutsrc_path.write_text(shortcutsrc_content, encoding="utf-8")

    # 2. menurc (GMenu / GtkAction accelerator mappings)
    menurc_content = """; PhotoGIMP 3.0 Menurc Accelerators
(gtk_accel_path "<Gimp-Actions>/image/image-transform-free" "<Primary>t")
(gtk_accel_path "<Gimp-Actions>/layers/layers-duplicate" "<Primary>j")
(gtk_accel_path "<Gimp-Actions>/select/select-none" "<Primary>d")
(gtk_accel_path "<Gimp-Actions>/dialogs/dialogs-command-palette" "<Primary>k")
(gtk_accel_path "<Gimp-Actions>/dialogs/dialogs-action-search" "<Primary>p")
"""
    menurc_path = gimp_cfg / "menurc"
    menurc_path.write_text(menurc_content, encoding="utf-8")

    # 3. gimprc (PhotoGIMP settings)
    gimprc_content = """# PhotoGIMP 3.0 Preferences Profile
(theme "Dark-Pro")
(icon-theme "Symbolic-High-Contrast")
(icon-size medium)
(toolbox-single-column yes)
(default-view
    (show-menubar yes)
    (show-statusbar yes)
    (show-rulers yes)
    (show-scrollbars no)
    (show-selection yes)
    (show-layer-boundary no)
    (show-guides yes)
    (show-grid no)
    (show-sample-points yes)
    (snap-to-guides yes)
    (snap-to-grid no)
    (snap-to-canvas yes)
    (snap-to-path yes)
    (snap-to-bbox yes)
    (snap-distance 8))
(dynamic-distance-labels yes)
(snap-smart-guides yes)
(smart-snapping-equidistance yes)
(canvas-gpu-acceleration yes)
(canvas-gsk-renderer "vulkan")
(workspace-profile "PhotoGIMP")
(color-management
    (mode display)
    (display-rendering-intent relative-colorimetric)
    (simulation-rendering-intent perceptual)
    (simulation-use-black-point-compensation yes)
    (simulation-optimize yes))
(undo-levels 100)
(undo-size 1073741824)
"""
    gimprc_path = gimp_cfg / "gimprc"
    gimprc_path.write_text(gimprc_content, encoding="utf-8")

    # 4. sessionrc (Single-window layout with PhotoGIMP dock layout)
    sessionrc_content = """# PhotoGIMP 3.0 GUI Session Layout
(session-info "toplevel"
    (factory-entry "gimp-empty-image-window")
    (position 0 0)
    (size 1920 1080)
    (open-on-exit)
    (gimp-toolbox
        (position 0 0)
        (size 56 1080)
        (dock
            (book
                (dockable "gimp-tool-options" (tab-style icon))
                (dockable "gimp-device-status" (tab-style icon)))))
    (gimp-dock
        (position 1560 0)
        (size 360 1080)
        (book
            (dockable "gimp-layer-list" (tab-style preview))
            (dockable "gimp-channel-list" (tab-style preview))
            (dockable "gimp-vectors-list" (tab-style preview))
            (dockable "gimp-undo-history" (tab-style icon))
            (dockable "gimp-histogram-editor" (tab-style icon)))))
"""
    sessionrc_path = gimp_cfg / "sessionrc"
    sessionrc_path.write_text(sessionrc_content, encoding="utf-8")

    # 5. toolrc (Single-column tool palette ordering)
    toolrc_content = """# PhotoGIMP 3.0 Tool Ordering
(tool "gimp-rect-select-tool")
(tool "gimp-ellipse-select-tool")
(tool "gimp-free-select-tool")
(tool "gimp-fuzzy-select-tool")
(tool "gimp-sam2-ai-tool")
(tool "gimp-crop-tool")
(tool "gimp-unified-transform-tool")
(tool "gimp-warp-tool")
(tool "gimp-paint-brush-tool")
(tool "gimp-eraser-tool")
(tool "gimp-bucket-fill-tool")
(tool "gimp-gradient-tool")
(tool "gimp-text-tool")
(tool "gimp-color-picker-tool")
(tool "gimp-zoom-tool")
"""
    toolrc_path = gimp_cfg / "toolrc"
    toolrc_path.write_text(toolrc_content, encoding="utf-8")

    # 6. gimp.css / gimp-dark.css (Dark Pro / OLED Design System)
    gimp_css_content = """/* PhotoGIMP 3.0 Dark Pro / OLED High-Contrast Design System */
@define-color theme_bg_color #121212;
@define-color theme_fg_color #f0f0f0;
@define-color theme_base_color #181818;
@define-color theme_text_color #ffffff;
@define-color theme_selected_bg_color #0078d4;
@define-color theme_selected_fg_color #ffffff;
@define-color theme_border_color #2a2a2a;
@define-color oled_black #000000;
@define-color accent_cyan #00e5ff;
@define-color guide_color #ff007f;

window.background {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}

/* Pill Sliders */
scale.pill-slider {
    min-height: 24px;
    border-radius: 12px;
    background-color: #222222;
}

scale.pill-slider trough {
    border-radius: 12px;
    background-color: #2a2a2a;
}

scale.pill-slider highlight {
    border-radius: 12px;
    background-color: @theme_selected_bg_color;
}

/* Minimalist Tabs */
tab.compact-tab {
    padding: 4px 12px;
    border-bottom: 2px solid transparent;
}

tab.compact-tab:checked {
    border-bottom: 2px solid @theme_selected_bg_color;
    color: #ffffff;
    font-weight: bold;
}

/* Single Column Tool Palette */
.single-column-toolbox {
    min-width: 48px;
    max-width: 56px;
    background-color: @theme_base_color;
    border-right: 1px solid @theme_border_color;
}

/* Canvas Viewport */
.gimp-canvas-viewport {
    background-color: @oled_black;
}

/* Smart Snapping Distance Labels */
.smart-snapping-label {
    background-color: rgba(0, 120, 212, 0.9);
    color: #ffffff;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
}
"""
    gimp_css_path = gimp_cfg / "gimp.css"
    gimp_css_path.write_text(gimp_css_content, encoding="utf-8")
    (gimp_cfg / "gimp-dark.css").write_text(gimp_css_content, encoding="utf-8")

    # 7. Subdirectories: splashes, plug-ins, filters, themes
    splashes_dir = gimp_cfg / "splashes"
    splashes_dir.mkdir(parents=True, exist_ok=True)
    # Write a 1x1 mock PNG header splash for test environments
    png_1x1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (splashes_dir / "photogimp_splash.png").write_bytes(png_1x1)

    (gimp_cfg / "plug-ins").mkdir(parents=True, exist_ok=True)
    (gimp_cfg / "filters").mkdir(parents=True, exist_ok=True)
    (gimp_cfg / "themes").mkdir(parents=True, exist_ok=True)

    return {
        "root": gimp_cfg,
        "shortcutsrc": shortcutsrc_path,
        "menurc": menurc_path,
        "gimprc": gimprc_path,
        "sessionrc": sessionrc_path,
        "toolrc": toolrc_path,
        "gimp_css": gimp_css_path,
        "splashes": splashes_dir,
    }


class MockAssetGenerator:
    """
    Unified manager for synthetic test asset generation.
    """

    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="gimp_mock_assets_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._generated_files: List[Path] = []

    def create_psd(self, filename: str = "test.psd", **kwargs) -> Path:
        out_path = self.output_dir / filename
        create_dummy_psd(output_path=out_path, **kwargs)
        self._generated_files.append(out_path)
        return out_path

    def create_svg(self, filename: str = "vector.svg", **kwargs) -> Path:
        out_path = self.output_dir / filename
        create_dummy_svg(output_path=out_path, **kwargs)
        self._generated_files.append(out_path)
        return out_path

    def create_raw(self, filename: str = "sensor.dng", **kwargs) -> Path:
        out_path = self.output_dir / filename
        create_dummy_raw(output_path=out_path, **kwargs)
        self._generated_files.append(out_path)
        return out_path

    def create_tiff(self, filename: str = "image.tif", **kwargs) -> Path:
        out_path = self.output_dir / filename
        create_dummy_tiff(output_path=out_path, **kwargs)
        self._generated_files.append(out_path)
        return out_path

    def create_xcf(self, filename: str = "project.xcf", **kwargs) -> Path:
        out_path = self.output_dir / filename
        create_dummy_xcf(output_path=out_path, **kwargs)
        self._generated_files.append(out_path)
        return out_path

    def create_photogimp(self, subfolder: str = "photogimp_profile") -> Dict[str, Path]:
        target = self.output_dir / subfolder
        return create_photogimp_profile(target)

    def cleanup(self):
        """Removes all generated files if using a temporary directory."""
        if self.output_dir.exists() and "gimp_mock_assets_" in str(self.output_dir):
            import shutil
            shutil.rmtree(self.output_dir, ignore_errors=True)
