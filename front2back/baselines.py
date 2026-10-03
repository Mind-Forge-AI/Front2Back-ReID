"""The paper's four non-generative controls. Each ranks tight crops of the rear
candidates against a tight crop of the front target (no padding, crop condition only).

  random_gallery  uniform draw, made deterministic by a fixed per-pair key
  hsv_histogram   16x16x16 HSV histogram, L1-normalised, 1 - Bhattacharyya distance
  dinov2_vitb14   frozen DINOv2 ViT-B/14 (torch.hub), cosine similarity of embeddings
  siglip2_base    frozen google/siglip2-base-patch16-224, cosine similarity of image features
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path

from .data import Pair

BASELINES = {"random_gallery": "Random gallery", "hsv_histogram": "HSV histogram",
             "dinov2_vitb14": "DINOv2 ViT-B/14", "siglip2_base": "SigLIP2 Base"}


@lru_cache(maxsize=1)
def _random_keys() -> dict[str, str]:
    path = Path(__file__).with_name("resources") / "random_gallery_keys.json"
    return json.loads(path.read_text())["keys"]


def _clamp(box, width, height):
    x1, y1, x2, y2 = box
    left = max(0, min(width - 1, int(math.floor(x1))))
    top = max(0, min(height - 1, int(math.floor(y1))))
    right = max(left + 1, min(width, int(math.ceil(x2))))
    bottom = max(top + 1, min(height, int(math.ceil(y2))))
    return left, top, right, bottom


def crops(pair: Pair):
    from PIL import Image

    with Image.open(pair.front_image) as im:
        f = im.convert("RGB"); target = f.crop(_clamp(pair.target_bbox_xyxy, f.width, f.height))
    with Image.open(pair.rear_image) as im:
        r = im.convert("RGB"); gallery = [r.crop(_clamp(c.bbox_xyxy, r.width, r.height)) for c in pair.candidates]
    return target, gallery


def _softmax(scores, scale):
    peak = max(scores)
    exps = [math.exp(max(-50.0, min(50.0, (s - peak) * scale))) for s in scores]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


class Baseline:
    def __init__(self, name: str, device: str | None = None):
        if name not in BASELINES:
            raise ValueError(f"unknown baseline {name!r}; choose from {list(BASELINES)}")
        self.name, self.model, self.processor = name, None, None
        if name in ("dinov2_vitb14", "siglip2_base"):
            import torch

            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            if name == "dinov2_vitb14":
                self.model = torch.hub.load("facebookresearch/dinov2", os.environ.get("DINOV2_BASELINE_MODEL", "dinov2_vitb14"), trust_repo=True).to(self.device).eval()
            else:
                from transformers import AutoModel, AutoProcessor

                model_id = os.environ.get("SIGLIP2_BASELINE_MODEL", "google/siglip2-base-patch16-224")
                self.processor = AutoProcessor.from_pretrained(model_id)
                self.model = AutoModel.from_pretrained(model_id).to(self.device).eval()

    def predict(self, pair: Pair) -> dict:
        aliases = pair.aliases
        if self.name == "random_gallery":
            idx = int(_random_keys()[pair.pair_id][:16], 16) % len(aliases)
            probs = [1 / len(aliases)] * len(aliases)
            scores = probs
        else:
            target, gallery = crops(pair)
            if self.name == "hsv_histogram":
                scores = self._hsv(target, gallery); probs = _softmax(scores, 8.0)
            else:
                emb = self._embed([target, *gallery])
                scores = [float(v) for v in (emb[1:] @ emb[0]).tolist()]; probs = _softmax(scores, 12.0)
            idx = max(range(len(scores)), key=scores.__getitem__)
        return {"pair_id": pair.pair_id, "model": self.name, "condition": "front_crop", "reasoning_effort": "none",
                "status": "parsed", "candidate_id": aliases[idx], "confidence": probs[idx],
                "candidate_probabilities": dict(zip(aliases, probs)), "candidate_scores": dict(zip(aliases, scores))}

    @staticmethod
    def _hsv(target, gallery):
        import cv2
        import numpy as np

        def hist(image):
            hsv = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2HSV)
            h = cv2.calcHist([hsv], [0, 1, 2], None, [16, 16, 16], [0, 180, 0, 256, 0, 256])
            return cv2.normalize(h, h, alpha=1.0, norm_type=cv2.NORM_L1)

        t = hist(target)
        return [1.0 - float(cv2.compareHist(t, hist(g), cv2.HISTCMP_BHATTACHARYYA)) for g in gallery]

    def _embed(self, images):
        import torch

        with torch.inference_mode():
            if self.name == "dinov2_vitb14":
                from torchvision import transforms

                tf = transforms.Compose([
                    transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC), transforms.CenterCrop(224),
                    transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
                feats = self.model(torch.stack([tf(im) for im in images]).to(self.device))
            else:
                inputs = {k: v.to(self.device) for k, v in self.processor(images=images, return_tensors="pt").items()}
                feats = self.model.get_image_features(**inputs)
                if hasattr(feats, "pooler_output"):
                    feats = feats.pooler_output
            return torch.nn.functional.normalize(feats.float(), dim=-1).cpu()
