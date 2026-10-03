"""Model inputs exactly as the paper's evaluation built them.

The paper's runs composited boxes onto the original 640x360 frames:
  * rear gallery: every candidate box (orange, 2 px, 10% fill) with a dark alias tag C1, C2, ...
  * full RGB:     the front frame with the target box (cyan, 3 px, 22% fill) tagged "T"
  * target crop:  the front target padded by max(8, round(0.18 * longer side)) px, JPEG q90
  * silhouette:   the target's full-frame binary mask PNG, sent unchanged
Boxes are drawn as in the original SVG overlay. Text is rendered with a bold sans font
(Liberation Sans or DejaVu Sans), so glyphs can differ by a pixel from the original
Arial rasterisation; geometry, colours and labels are identical.
"""

from __future__ import annotations

import io
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .data import Pair

CANDIDATE_STYLE = {"stroke": (244, 151, 108, 255), "fill": (244, 151, 108, 26), "width": 2}
TARGET_STYLE = {"stroke": (210, 253, 255, 255), "fill": (35, 169, 194, 56), "width": 3}
TAG_FILL = (16, 26, 50, 194)


@lru_cache(maxsize=1)
def _font(size: int = 10):
    for name in ("LiberationSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_boxes(image: Image.Image, boxes: list[tuple[str, tuple[float, float, float, float]]], style: dict) -> Image.Image:
    base = image.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    half = style["width"] / 2
    for alias, (x1, y1, x2, y2) in boxes:
        w, h = max(1.0, x2 - x1), max(1.0, y2 - y1)
        draw.rectangle([x1, y1, x1 + w, y1 + h], fill=style["fill"])
        # SVG strokes are centred on the rectangle edge
        draw.rectangle([x1 - half, y1 - half, x1 + w + half, y1 + h + half], outline=style["stroke"], width=style["width"])
        text_y = max(13.0, y1 + 12)
        tag_w = max(18, len(alias) * 8 + 8)
        draw.rounded_rectangle([x1, max(0.0, text_y - 12), x1 + tag_w, max(0.0, text_y - 12) + 14], radius=3, fill=TAG_FILL)
        draw.text((x1 + 4, text_y - 2), alias, fill=(255, 255, 255, 255), font=_font(), anchor="ls")
    return Image.alpha_composite(base, layer).convert("RGB")


def _jpeg(image: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def rear_gallery(pair: Pair) -> Image.Image:
    with Image.open(pair.rear_image) as im:
        return _draw_boxes(im, [(c.candidate_id, c.bbox_xyxy) for c in pair.candidates], CANDIDATE_STYLE)


def front_marked(pair: Pair) -> Image.Image:
    with Image.open(pair.front_image) as im:
        return _draw_boxes(im, [("T", pair.target_bbox_xyxy)], TARGET_STYLE)


def crop_window(pair: Pair) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = pair.target_bbox_xyxy
    width, height = pair.front_size
    # JavaScript Math.round: halves round up
    pad = max(8, math.floor(max(x2 - x1, y2 - y1) * 0.18 + 0.5))
    left, top = max(0, math.floor(x1 - pad)), max(0, math.floor(y1 - pad))
    w = min(width - left, math.ceil(x2 - x1 + pad * 2))
    h = min(height - top, math.ceil(y2 - y1 + pad * 2))
    return left, top, left + max(1, w), top + max(1, h)


def front_crop(pair: Pair) -> Image.Image:
    with Image.open(pair.front_image) as im:
        return im.convert("RGB").crop(crop_window(pair))


def model_inputs(pair: Pair, condition: str) -> list[dict]:
    """Return the images for one paper condition, in the order they were sent.

    Each item: {"label", "mime", "bytes"}. Labels match the text the model saw
    ("Image 1: front_target", ...).
    """
    rear = {"label": "rear_candidates", "mime": "image/jpeg", "bytes": _jpeg(rear_gallery(pair), 88)}
    if condition == "rgb_full":
        front = {"label": "front_target", "mime": "image/jpeg", "bytes": _jpeg(front_marked(pair), 88)}
    elif condition == "front_crop":
        front = {"label": "front_target_crop", "mime": "image/jpeg", "bytes": _jpeg(front_crop(pair), 90)}
    elif condition == "front_mask":
        front = {"label": "front_target_mask", "mime": "image/png", "bytes": Path(pair.target_mask).read_bytes()}
    else:
        raise ValueError(f"unknown condition {condition!r}")
    return [front, rear]
