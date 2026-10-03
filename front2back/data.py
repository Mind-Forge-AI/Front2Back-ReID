"""Load the Front2Back-ReID release (front2back-reid-v1.1/)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# The three front-evidence conditions evaluated in the paper.
CONDITIONS = ("rgb_full", "front_crop", "front_mask")
CONDITION_LABELS = {"rgb_full": "Full RGB", "front_crop": "Target crop", "front_mask": "Silhouette"}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class Pair:
    """One closed-gallery handover. Paths are absolute."""

    pair_id: str
    road_context: str
    time_of_day: str
    weather: str
    front_image: Path
    front_size: tuple[int, int]
    target_bbox_xyxy: tuple[float, float, float, float]
    target_mask: Path
    rear_image: Path
    rear_size: tuple[int, int]
    candidates: tuple[Candidate, ...]
    raw: dict

    @property
    def aliases(self) -> list[str]:
        return [c.candidate_id for c in self.candidates]


class Benchmark:
    """The frozen 500-pair test set.

    >>> bench = Benchmark("data/front2back-reid-v1.1")
    >>> pair = bench["P0001"]; bench.answer("P0001")
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        manifest = self.root / "annotations" / "pairs.jsonl"
        if not manifest.exists():
            raise FileNotFoundError(
                f"{manifest} not found. Download the release (python scripts/download_data.py) "
                "and pass the unzipped front2back-reid-v1.1 folder."
            )
        order = [l.strip() for l in (self.root / "splits" / "test500.txt").read_text().splitlines() if l.strip()]
        rows = {r["pair_id"]: r for r in _jsonl(manifest)}
        self.pairs: dict[str, Pair] = {pid: self._pair(rows[pid]) for pid in order}
        self._truth: dict[str, str] | None = None

    def _pair(self, r: dict) -> Pair:
        f, b = r["front"], r["rear"]
        return Pair(
            pair_id=r["pair_id"], road_context=r["road_context"], time_of_day=r["time_of_day"], weather=r["weather"],
            front_image=self.root / f["image"], front_size=(f["width"], f["height"]),
            target_bbox_xyxy=tuple(f["target_bbox_xyxy"]), target_mask=self.root / f["target_mask"],
            rear_image=self.root / b["image"], rear_size=(b["width"], b["height"]),
            candidates=tuple(Candidate(c["candidate_id"], tuple(c["bbox_xyxy"])) for c in b["candidates"]),
            raw=r,
        )

    def __len__(self) -> int:
        return len(self.pairs)

    def __iter__(self) -> Iterator[Pair]:
        return iter(self.pairs.values())

    def __getitem__(self, pair_id: str) -> Pair:
        return self.pairs[pair_id]

    # Ground truth is loaded lazily and only for scoring; never put it in a prompt.
    @property
    def truth(self) -> dict[str, str]:
        if self._truth is None:
            self._truth = {a["pair_id"]: a["correct_candidate_id"] for a in _jsonl(self.root / "annotations" / "ground_truth.jsonl")}
        return self._truth

    def answer(self, pair_id: str) -> str:
        return self.truth[pair_id]
