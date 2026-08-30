#!/usr/bin/env python3
"""
ROI Processor: Calculates Region of Interest bounding boxes, context padding,
and feathered alpha recombination for generative diffusion inpainting.
"""

from __future__ import annotations

import math
from typing import Tuple


class ROIProcessor:
    @staticmethod
    def calculate_roi_bounds(
        img_width: int,
        img_height: int,
        sel_bounds: Tuple[int, int, int, int],  # (x1, y1, x2, y2)
        min_padding: int = 64,
        align_multiple: int = 64,
    ) -> Tuple[int, int, int, int]:
        """
        Expands selection bounding box with contextual padding and aligns dimensions
        to multiples of align_multiple (e.g. 64 for VAE latent space).
        Returns (rx, ry, rw, rh).
        """
        x1, y1, x2, y2 = sel_bounds
        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)

        pad_x = max(min_padding, int(bw * 0.25))
        pad_y = max(min_padding, int(bh * 0.25))

        rx = max(0, x1 - pad_x)
        ry = max(0, y1 - pad_y)
        rw = min(img_width - rx, (x2 + pad_x) - rx)
        rh = min(img_height - ry, (y2 + pad_y) - ry)

        # Snap to multiples of align_multiple
        rw = min(img_width - rx, int(math.ceil(rw / align_multiple) * align_multiple))
        rh = min(img_height - ry, int(math.ceil(rh / align_multiple) * align_multiple))

        return rx, ry, rw, rh

    @staticmethod
    def create_feather_mask(
        width: int,
        height: int,
        feather_radius: int = 16,
    ) -> bytearray:
        """Generates a feather alpha mask around the outer perimeter."""
        mask = bytearray(width * height)
        for y in range(height):
            for x in range(width):
                dist_border = min(x, y, width - 1 - x, height - 1 - y)
                if dist_border >= feather_radius:
                    mask[y * width + x] = 255
                else:
                    mask[y * width + x] = int(255 * (dist_border / feather_radius))
        return mask
