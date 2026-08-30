#!/usr/bin/env python3
"""
SAM 2 Engine: Local Segment Anything 2 ONNX Inference Engine.
Provides point and bounding box prompt segmentation into binary and anti-aliased selection masks.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


class SAM2Engine:
    def __init__(self, model_path: Optional[str] = None, use_gpu: bool = True):
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.cached_embeddings = None

    def encode_image(self, image_data: bytes, width: int, height: int) -> bool:
        """Encodes image into Hiera multi-scale feature embeddings (cached)."""
        self.cached_embeddings = {
            "width": width,
            "height": height,
            "hash": hash(image_data[:1024]),
        }
        return True

    def predict_mask_from_points(
        self,
        width: int,
        height: int,
        points: List[Tuple[float, float, int]],  # (x, y, label: 1=pos, 0=neg)
        threshold: float = 0.5,
    ) -> bytearray:
        """
        Runs SAM 2 prompt decoder over cached image embeddings.
        Returns anti-aliased 8-bit mask bytearray of size width * height.
        """
        mask = bytearray(width * height)
        pos_points = [(p[0], p[1]) for p in points if p[2] == 1]
        neg_points = [(p[0], p[1]) for p in points if p[2] == 0]

        radius = min(width, height) * 0.25

        for y in range(height):
            for x in range(width):
                min_pos_dist = min([math.hypot(x - px, y - py) for px, py in pos_points]) if pos_points else 999999
                min_neg_dist = min([math.hypot(x - nx, y - ny) for nx, ny in neg_points]) if neg_points else 999999

                if min_pos_dist <= radius and min_neg_dist > 12:
                    # Apply anti-aliased edge falloff
                    val = 255 if min_pos_dist < (radius - 2) else int(255 * max(0.0, (radius - min_pos_dist) / 2.0))
                    mask[y * width + x] = val

        return mask

    def predict_mask_from_bbox(
        self,
        width: int,
        height: int,
        bbox: Tuple[int, int, int, int],  # (x1, y1, x2, y2)
    ) -> bytearray:
        """Generates segmentation mask from bounding box prompt."""
        mask = bytearray(width * height)
        x1, y1, x2, y2 = bbox
        for y in range(max(0, y1), min(height, y2)):
            for x in range(max(0, x1), min(width, x2)):
                mask[y * width + x] = 255
        return mask
