"""Bias-corrected and accelerated (BCa) bootstrap intervals over pairs (Efron, 1987).

The paper reports two-sided 95% BCa intervals from 100,000 resamples with seed 32025.
Uses scipy.stats.bootstrap when SciPy is installed (method="BCa"), otherwise an
equivalent NumPy implementation.
"""

from __future__ import annotations

from statistics import NormalDist
from typing import Sequence

import numpy as np

SEED, RESAMPLES = 32025, 100_000


def _bca_numpy(x: np.ndarray, resamples: int, seed: int, level: float) -> tuple[float, float]:
    n = len(x)
    theta = x.mean()
    rng = np.random.default_rng(seed)
    boot = np.empty(resamples)
    step = max(1, 2_000_000 // n)
    for s in range(0, resamples, step):
        k = min(step, resamples - s)
        boot[s:s + k] = x[rng.integers(0, n, size=(k, n))].mean(axis=1)
    nd = NormalDist()
    prop = (np.sum(boot < theta) + 0.5 * np.sum(boot == theta)) / resamples
    prop = min(max(prop, 1 / resamples), 1 - 1 / resamples)
    z0 = nd.inv_cdf(prop)
    jack = (x.sum() - x) / (n - 1)
    d = jack.mean() - jack
    denom = 6.0 * (np.sum(d ** 2) ** 1.5)
    a = float(np.sum(d ** 3) / denom) if denom > 0 else 0.0
    out = []
    for q in ((1 - level) / 2, (1 + level) / 2):
        z = nd.inv_cdf(q)
        adj = nd.cdf(z0 + (z0 + z) / (1 - a * (z0 + z)))
        out.append(float(np.quantile(boot, adj)))
    return out[0], out[1]


def bca_interval(values: Sequence[float], *, resamples: int = RESAMPLES, seed: int = SEED, level: float = 0.95,
                 use_scipy: bool = True) -> tuple[float, float]:
    """95% BCa interval for the mean of per-pair values (1/0 hits -> accuracy)."""
    x = np.asarray(values, dtype=float)
    if x.min() == x.max():
        return float(x[0]), float(x[0])
    if use_scipy:
        try:
            from scipy.stats import bootstrap

            res = bootstrap((x,), np.mean, n_resamples=resamples, method="BCa", confidence_level=level,
                            random_state=np.random.default_rng(seed), vectorized=True, axis=-1)
            return float(res.confidence_interval.low), float(res.confidence_interval.high)
        except ImportError:
            pass
    return _bca_numpy(x, resamples, seed, level)


def paired_bca_interval(a: Sequence[float], b: Sequence[float], **kw) -> tuple[float, tuple[float, float]]:
    """Mean paired difference a - b over the same pairs, with its BCa interval."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    return float(d.mean()), bca_interval(d, **kw)
