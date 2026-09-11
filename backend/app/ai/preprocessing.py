"""Numeric preprocessing / index math shared by the AI pipelines.

Everything here is pure numpy and deliberately dependency-light -- these
routines operate on *area-mean* reflectance statistics (as emitted by the
Sentinel Hub Statistical API through app.satellite) so the MVP pipelines
can run in the RQ worker with no GPU, heavy ML stacks, or raster I/O.

When pixel-level processing is added later (autonomous robotics, planetary
surface mapping), this module is still the right home for the pure band
math; new stages just receive actual imagery arrays instead of scalars.
"""

from typing import List, Optional, Sequence

import numpy as np

EPSILON = 1e-8


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Float division that returns `default` for zero/NaN denominators."""
    if denominator is None or not np.isfinite(denominator) or abs(denominator) < EPSILON:
        return default
    result = numerator / denominator
    if not np.isfinite(result):
        return default
    return float(result)


def clip01(value: float) -> float:
    """Clamp a value into the [0, 1] range."""
    return float(min(1.0, max(0.0, value)))


# --- Band indices (area-mean values; scalar band inputs) --------------------


def ndvi_from_bands(nir: float, red: float) -> float:
    """Normalized Difference Vegetation Index over an area mean."""
    return safe_divide(nir - red, nir + red)


def ndwi_from_bands(green: float, nir: float) -> float:
    """McFeeters Normalized Difference Water Index (green/NIR)."""
    return safe_divide(green - nir, green + nir)


def evi_from_bands(blue: float, red: float, nir: float) -> float:
    """Enhanced Vegetation Index 2.5*(NIR-RED)/(NIR + 6RED - 7.5BLUE + 1)."""
    return safe_divide(2.5 * (nir - red), nir + 6 * red - 7.5 * blue + 1)


def bsi_from_bands(blue: float, red: float, swir2: float, nir: float) -> float:
    """Bare Soil Index (built-up / exposed-land proxy)."""
    return safe_divide((swir2 + red) - (nir + blue), (swir2 + red) + (nir + blue)) + 0.5


# --- Area-level severity transforms -----------------------------------------


def ndvi_stress_severity(ndvi: float) -> float:
    """Maps NDVI onto a 0..1 vegetation-stress severity.

    Assumes roughly NDVI >= 0.65 = healthy (severity 0) down to NDVI ~ 0
    = fully stressed (severity 1). This is a practical band-math threshold,
    not a ground-validated agronomy model, so it is marked prototype until
    validated against field data.
    """
    return clip01((0.65 - clip01(ndvi)) / 0.65)


def deviation_severity(value: float, expected: float, scale: float = 0.4, floor: float = 0.15) -> float:
    """Severity from how far `value` deviates from an expected baseline.

    `floor` ensures structural changes (large but genuinely new activity)
    still register instead of being smoothed to zero by a noisy baseline.
    """
    delta = abs(float(value) - float(expected))
    return clip01(min(delta / max(scale, EPSILON) + floor, 1.0))


def robust_zscore(
    value: float,
    series: Sequence[float],
    mad_scale: float = 1.4826,
) -> float:
    """Robust z-score (median/MAD) of `value` against a reference series.

    Uses median and MAD instead of mean/std so a few outliers in the
    baseline history don't inflate the threshold and hide the anomaly
    being tested for. Returns 0 when the series carries no dispersion.
    """
    if not series or len(series) < 2:
        return 0.0
    arr = np.asarray(series, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median))) or 0.0
    if mad < EPSILON:
        return 0.0
    return float(abs(value - median) / (mad_scale * mad))


def anomaly_severity_from_zscores(
    zscores: Sequence[float], threshold: float = 2.5, max_severity: float = 3.5
) -> float:
    """Turn one or more robust z-scores into a single 0..1 severity.

    Any score above `threshold` counts; the strength scales linearly up to
    `max_severity` where it saturates at 1.0.
    """
    peak = max(zscores) if zscores else 0.0
    if peak <= threshold:
        return clip01(peak / threshold * 0.5)  # below threshold, still informative but low
    return clip01((peak - threshold) / (max_severity - threshold))


def average_bands(observation_bands: Optional[dict]) -> float:
    """Mean reflectance across provided bands (used as a texture proxy)."""
    if not observation_bands:
        return 0.0
    return float(np.mean([float(v) for v in observation_bands.values()]))


def require_valued(*values: Optional[float]) -> bool:
    """True when every provided value is present and finite."""
    for value in values:
        if value is None or not np.isfinite(float(value)):
            return False
    return True