"""Front2Back-ReID: benchmark tools for asymmetric front-to-rear vehicle re-identification.

Paper: Front-to-Back: Benchmarking Vision-Language Models for Asymmetric Cross-View
Vehicle Re-Identification (Mots'oehli & Babeli, arXiv:2609.39492).
"""

from .data import Benchmark, Pair, CONDITIONS
from .scoring import score, ScoreError
from .stats import bca_interval, paired_bca_interval

__all__ = ["Benchmark", "Pair", "CONDITIONS", "score", "ScoreError", "bca_interval", "paired_bca_interval"]
__version__ = "1.1.0"
