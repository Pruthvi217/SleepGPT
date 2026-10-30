"""Shared SpO2 preprocessing: parse/validate a (timestamp, spo2) series, resample to the
model's 8 Hz grid, cut 88-sample (11 s) windows, normalise.

Only the 88-sample/8 Hz/11 s window and the z-score normalisation come from the notebook.
Resampling an arbitrary-rate sensor stream onto 8 Hz (linear interpolation, gap masking) is an
inference-time necessity that the notebook does not define - it is documented, not hidden."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from . import config as C


class SpO2ValidationError(ValueError):
    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = details or []


@dataclass
class CleanSeries:
    t: np.ndarray            # epoch seconds, strictly increasing, float64
    v: np.ndarray            # SpO2 %, float64
    dropped: dict = field(default_factory=dict)
    median_interval_s: float = 0.0


def to_epoch_seconds(values) -> np.ndarray:
    """ISO-8601 strings, epoch seconds or epoch milliseconds -> float epoch seconds. Naive times = UTC."""
    import pandas as pd
    s = pd.Series(list(values))
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().all():
        a = num.to_numpy(dtype="float64")
        return np.where(np.abs(a) > 1e11, a / 1000.0, a)
    dt = pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
    out = np.full(len(s), np.nan)
    ok = dt.notna().to_numpy()
    out[ok] = dt[ok].astype("int64").to_numpy() / 1e9 if str(dt.dtype).endswith("[ns, UTC]") else dt[ok].map(lambda x: x.timestamp()).to_numpy()
    return out


def clean_series(t, v, s: C.MLSettings | None = None) -> CleanSeries:
    from .config import load_settings
    s = s or load_settings()
    t = np.asarray(t, dtype="float64"); v = np.asarray(v, dtype="float64")
    n0 = len(t)
    if n0 == 0:
        raise SpO2ValidationError("No SpO2 samples were provided.")
    bad_ts = ~np.isfinite(t)
    bad_val = ~np.isfinite(v)
    out_of_range = np.isfinite(v) & ((v < s.spo2_valid_min) | (v > s.spo2_valid_max))
    keep = ~(bad_ts | bad_val | out_of_range)
    dropped = {"unparseable_timestamp": int(bad_ts.sum()), "missing_or_non_numeric_spo2": int((bad_val & ~bad_ts).sum()),
               "impossible_spo2": int(out_of_range.sum())}
    if keep.sum() == 0 or (n0 - keep.sum()) / n0 > s.max_invalid_fraction:
        raise SpO2ValidationError(
            f"Too many invalid rows ({n0 - int(keep.sum())} of {n0}).",
            [f"{k}: {c}" for k, c in dropped.items() if c] +
            [f"Valid SpO2 range is {s.spo2_valid_min:g}-{s.spo2_valid_max:g} %."])
    t, v = t[keep], v[keep]
    order = np.argsort(t, kind="stable"); t, v = t[order], v[order]
    uniq = np.concatenate(([True], np.diff(t) > 0))
    dropped["duplicate_timestamps"] = int((~uniq).sum())
    t, v = t[uniq], v[uniq]
    if len(t) < 2:
        raise SpO2ValidationError("At least two valid samples with distinct timestamps are required.")
    med = float(np.median(np.diff(t)))
    if med > s.max_sample_interval_s:
        raise SpO2ValidationError(
            f"Sampling interval too coarse: median {med:.1f} s between samples (max {s.max_sample_interval_s:g} s). "
            "The model needs a continuous SpO2 time series, not sparse readings.")
    dur = t[-1] - t[0]
    if dur < s.min_duration_minutes * 60:
        raise SpO2ValidationError(
            f"Recording too short: {dur/60:.1f} min (minimum {s.min_duration_minutes:g} min; "
            f"at least one {C.WINDOW_SECONDS:g} s window is always required).")
    return CleanSeries(t=t, v=v, dropped=dropped, median_interval_s=med)


def resample_8hz(cs: CleanSeries, max_gap_s: float):
    """Linear interpolation onto a uniform 8 Hz grid; grid points inside gaps > max_gap_s are invalid."""
    step = 1.0 / C.SAMPLE_RATE_HZ
    grid = np.arange(cs.t[0], cs.t[-1] + 1e-9, step)
    y = np.interp(grid, cs.t, cs.v)
    idx = np.searchsorted(cs.t, grid, side="right") - 1
    idx = np.clip(idx, 0, len(cs.t) - 2)
    gap = cs.t[idx + 1] - cs.t[idx]
    valid = gap <= max_gap_s
    return grid, y.astype(np.float32), valid


def make_windows(grid, y, valid, stride: int):
    W = C.WINDOW_SAMPLES
    starts = np.arange(0, len(y) - W + 1, stride)
    if len(starts) == 0:
        raise SpO2ValidationError(f"Not enough data for one {W}-sample ({C.WINDOW_SECONDS:g} s @ {C.SAMPLE_RATE_HZ} Hz) window.")
    idx = starts[:, None] + np.arange(W)[None, :]
    wins, ok = y[idx], valid[idx].all(axis=1)
    return starts, wins, ok


def normalise(wins: np.ndarray, s: C.MLSettings) -> np.ndarray:
    if s.normalization_mode == "global":
        return (wins - s.train_mean) / s.train_std
    mu = wins.mean(axis=1, keepdims=True)
    sd = wins.std(axis=1, keepdims=True)
    return np.where(sd > 1e-6, (wins - mu) / np.maximum(sd, 1e-6), 0.0).astype(np.float32)
