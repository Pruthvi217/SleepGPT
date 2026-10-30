"""THE single ML pipeline used by both manual CSV and Ubidots sources."""
from __future__ import annotations
import io
import numpy as np
from . import config as C
from .events import aggregate_events, estimated_ahi
from .preprocessing import (SpO2ValidationError, clean_series, make_windows, normalise,
                            resample_8hz, to_epoch_seconds)
from .somnnet import get_model

AHI_LABEL = "Estimated AHI — Unvalidated"
DISCLAIMER = ("Research/informational use only. Not a clinical diagnosis. This ML-derived estimate is for research/informational use and is not a clinical diagnosis. "
              "Model normalization requires validation against the original training-data statistics and real sensor data.")


def parse_csv(content: bytes | str):
    """CSV with header 'timestamp,spo2' -> (t_epoch_s, spo2). Raises SpO2ValidationError with details."""
    import pandas as pd
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise SpO2ValidationError("File is not valid UTF-8 text.")
    if not content.strip():
        raise SpO2ValidationError("The CSV file is empty.")
    try:
        df = pd.read_csv(io.StringIO(content), skipinitialspace=True)
    except Exception as exc:
        raise SpO2ValidationError("Could not parse the file as CSV.", [str(exc)])
    df.columns = [str(c).strip().lower() for c in df.columns]
    miss = [c for c in ("timestamp", "spo2") if c not in df.columns]
    if miss:
        raise SpO2ValidationError(f"CSV must have the columns 'timestamp,spo2'; missing: {', '.join(miss)}.",
                                  [f"Found columns: {list(df.columns)}"])
    t = to_epoch_seconds(df["timestamp"].tolist())
    v = pd.to_numeric(df["spo2"], errors="coerce").to_numpy(dtype="float64")
    return t, v


def run_pipeline(t, v, settings: C.MLSettings | None = None) -> dict:
    s = settings or C.load_settings()
    cs = clean_series(t, v, s)
    grid, y, valid = resample_8hz(cs, s.max_gap_s)
    starts, wins, ok = make_windows(grid, y, valid, s.window_stride_samples)
    n_valid = int(ok.sum())
    if n_valid == 0:
        raise SpO2ValidationError("No complete 11 s windows without data gaps; check the sampling continuity.")
    probs = get_model(s.weights_path).predict_proba(normalise(wins[ok], s))
    p_apnea = np.zeros(len(starts), dtype=np.float32)
    p_apnea[ok] = probs[:, s.apnea_class_index]
    is_apnea = p_apnea >= s.apnea_threshold
    events = aggregate_events(starts, is_apnea, ok, grid[0], s.min_event_windows, s.window_stride_samples)
    hours = n_valid * s.window_stride_samples / C.SAMPLE_RATE_HZ / 3600.0
    hours = min(hours, (cs.t[-1] - cs.t[0]) / 3600.0)
    ahi = estimated_ahi(len(events), hours)
    warnings = []
    if hours * 60 < s.reliable_duration_minutes:
        warnings.append(f"Only {hours*60:.0f} min analysed; an AHI from under {s.reliable_duration_minutes:g} min is not reliable.")
    if s.normalization_mode == "window":
        warnings.append("Per-window normalisation fallback in use (original training mean/std not supplied); "
                        "set SOMNNET_TRAIN_MEAN/STD for global normalisation as in the notebook.")
    if cs.median_interval_s > 2.0 / C.SAMPLE_RATE_HZ:
        warnings.append(f"Input sampled at ~{1/cs.median_interval_s:.2f} Hz was linearly upsampled to the model's "
                        f"{C.SAMPLE_RATE_HZ} Hz; the model was trained on decimated 8 Hz data, so fidelity on this sensor is unverified.")
    if n_valid < len(starts):
        warnings.append(f"{len(starts) - n_valid} of {len(starts)} windows skipped because of data gaps.")
    if any(cs.dropped.values()):
        warnings.append("Rows dropped during validation: " + ", ".join(f"{k}={c}" for k, c in cs.dropped.items() if c))
    return {
        "model_name": C.MODEL_NAME, "model_version": C.MODEL_VERSION,
        "estimated_ahi": round(float(ahi), 2), "detected_events": len(events),
        "sleep_duration_hours": round(float(hours), 3),
        "average_spo2": round(float(cs.v.mean()), 1), "minimum_spo2": round(float(cs.v.min()), 1),
        "maximum_spo2": round(float(cs.v.max()), 1),
        "input_start_time": float(cs.t[0]), "input_end_time": float(cs.t[-1]),
        "windows_total": int(len(starts)), "windows_analysed": n_valid, "windows_apnea": int(is_apnea.sum()),
        "normalization_mode": s.normalization_mode, "validation_status": "unvalidated",
        "config": {"normalization_mode": s.normalization_mode, "train_mean": s.train_mean, "train_std": s.train_std,
                   "apnea_class_index": s.apnea_class_index, "apnea_threshold": s.apnea_threshold,
                   "window_stride_samples": s.window_stride_samples, "min_event_windows": s.min_event_windows,
                   "source_median_interval_s": round(cs.median_interval_s, 4),
                   "sampling_rate_hz": C.SAMPLE_RATE_HZ, "window_samples": C.WINDOW_SAMPLES,
                   "input_samples": int(len(cs.t)), "analysed_samples": int(n_valid * s.window_stride_samples),
                   "windows_total": int(len(starts)), "windows_analysed": n_valid, "windows_apnea": int(is_apnea.sum())},
        "warnings": warnings, "events": events[:500],
        "disclaimer": DISCLAIMER,
    }
