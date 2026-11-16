"""Make a clean page look like a phone photo of a printed page: paper tint, slight
perspective and tilt, uneven light, softness, sensor noise and JPEG compression."""
from __future__ import annotations

import cv2
import numpy as np


def phone_photo(src: str, dst: str, seed: int = 0, strength: float = 1.0) -> str:
    rng = np.random.default_rng(seed)
    img = cv2.imread(src, cv2.IMREAD_COLOR).astype(np.float32)
    h, w = img.shape[:2]
    # paper tint
    img *= np.array([0.86, 0.9, 0.94], np.float32)  # BGR: warm paper
    # place on a darker table, with a margin, then warp the page corners
    pad = int(0.06 * w)
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), (70, 80, 92), np.float32)
    canvas[pad:pad + h, pad:pad + w] = img
    H, W = canvas.shape[:2]
    src_pts = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    j = 0.025 * strength * w
    dst_pts = src_pts + rng.uniform(-j, j, src_pts.shape).astype(np.float32)
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    angle = rng.uniform(-2.5, 2.5) * strength
    R = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1.0)
    R3 = np.vstack([R, [0, 0, 1]]).astype(np.float32)
    canvas = cv2.warpPerspective(canvas, (R3 @ M).astype(np.float32), (W, H), borderValue=(70, 80, 92))
    # uneven light: a gradient from one side plus a soft vignette
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    gx, gy = rng.uniform(-1, 1, 2)
    grad = 1 - 0.35 * strength * ((xx / W - 0.5) * gx + (yy / H - 0.5) * gy + 0.5)
    vig = 1 - 0.25 * strength * (((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2)
    canvas *= (grad * vig)[..., None]
    # softness and noise
    canvas = cv2.GaussianBlur(canvas, (0, 0), 0.9 * strength + 0.3)
    canvas += rng.normal(0, 4 * strength, canvas.shape).astype(np.float32)
    canvas = np.clip(canvas, 0, 255).astype(np.uint8)
    # a 12-megapixel phone gives about 3000 px on the long side of a page
    k = 3000 / max(canvas.shape[:2])
    canvas = cv2.resize(canvas, (round(canvas.shape[1] * k), round(canvas.shape[0] * k)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(dst, canvas, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return dst
