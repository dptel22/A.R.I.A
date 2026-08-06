"""
aria/inference/preprocess.py - Shared image preprocessing for A.R.I.A.

Single responsibility: transform a raw image array into the exact
letterboxed + CLAHE-LAB enhanced array used at training time.

Color channels
--------------
This module is colour-explicit.  The *input* array's channel order is declared
via ``color_order`` ("bgr" or "rgb"); the returned array preserves that same
order.  Callers must declare the order of the array they pass in.

Ultralytics treats numpy HWC sources as OpenCV-compatible **BGR**, so the array
that reaches ``model.predict`` must be BGR in both production paths:

    - ``aria/inference/pipeline.py`` decodes via PIL (RGB) and converts once to
      BGR, then calls ``preprocess(image, color_order="bgr")`` and hands the BGR
      result to ``detector.detect()`` (whose contract is a BGR ``(H, W, 3)``
      array).
    - ``scripts/demo_infer.py`` reads images with OpenCV (BGR), so it calls
      ``preprocess(image, color_order="bgr")`` and hands the BGR result straight
      to ``model.predict()``.

CLAHE is applied to the L channel in LAB space, which is order-independent, so
converting once before CLAHE keeps pixels identical across both paths.

CLAHE clip limit and tile grid match the training-time enhancement used when
the Stage-1 model was trained.
"""
from __future__ import annotations

import logging
from typing import Literal

import cv2
import numpy as np

log: logging.Logger = logging.getLogger(__name__)

_LETTERBOX_SIZE: int = 640
_CLAHE_CLIP_LIMIT: float = 2.0
_CLAHE_TILE_GRID: tuple[int, int] = (8, 8)

# (to-LAB conversion, from-LAB conversion) per declared channel order.
_LAB_CONVERSIONS: dict[str, tuple[int, int]] = {
    "bgr": (cv2.COLOR_BGR2LAB, cv2.COLOR_LAB2BGR),
    "rgb": (cv2.COLOR_RGB2LAB, cv2.COLOR_LAB2RGB),
}


def letterbox(image: np.ndarray, size: int = _LETTERBOX_SIZE) -> np.ndarray:
    """Resize *image* to fit within ``size`` x ``size`` and pad with zeros."""
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized_width = int(round(width * scale))
    resized_height = int(round(height * scale))

    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
    return cv2.copyMakeBorder(
        resized,
        top=(size - resized_height) // 2,
        bottom=size - resized_height - ((size - resized_height) // 2),
        left=(size - resized_width) // 2,
        right=size - resized_width - ((size - resized_width) // 2),
        borderType=cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )


def apply_clahe_lab(image: np.ndarray, *, color_order: str = "bgr") -> np.ndarray:
    """Apply CLAHE to the L channel in LAB space, preserving channel order."""
    to_lab, from_lab = _LAB_CONVERSIONS[color_order]
    lab = cv2.cvtColor(image, to_lab)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=_CLAHE_CLIP_LIMIT, tileGridSize=_CLAHE_TILE_GRID)
    normalized_l = clahe.apply(l_channel)
    normalized_lab = cv2.merge((normalized_l, a_channel, b_channel))
    return cv2.cvtColor(normalized_lab, from_lab)


def preprocess(
    image: np.ndarray,
    *,
    color_order: Literal["bgr", "rgb"] = "bgr",
    size: int = _LETTERBOX_SIZE,
) -> np.ndarray:
    """Letterbox to ``size`` then apply CLAHE-LAB enhancement.

    Args:
        image: ``uint8`` ``(H, W, 3)`` image array.
        color_order: Channel order of *image* ("bgr" or "rgb"). The returned
            array uses the same order.
        size: Target square size for letterboxing.

    Returns:
        Enhanced ``uint8`` array with shape ``(size, size, 3)`` in the same
        channel order as *image*.

    Raises:
        ValueError: If *image* is not an ``(H, W, 3)`` array or *color_order*
            is not one of "bgr" / "rgb".
    """
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(
            f"Expected (H, W, 3) uint8 image array, "
            f"got {'None' if image is None else image.shape}"
        )
    if color_order not in _LAB_CONVERSIONS:
        raise ValueError(
            f"Unsupported color_order={color_order!r}; expected 'bgr' or 'rgb'."
        )

    letterboxed = letterbox(image, size=size)
    return apply_clahe_lab(letterboxed, color_order=color_order)
