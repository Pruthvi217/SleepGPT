"""ML configuration — every tunable comes from environment variables (see .env.example)."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _f(name, default):
    v = os.environ.get(name, "")
    return float(v) if v.strip() else default


def _i(name, default):
    v = os.environ.get(name, "")
    return int(v) if v.strip() else default


# --- Fixed by the supplied notebook (Binary_spo2.ipynb): NOT configurable ---
MODEL_NAME = "SomnNET-SpO2-Binary"
MODEL_VERSION = "best_weights_spo2_32layer_binary"
WINDOW_SAMPLES = 88          # BatchNormalization(input_shape=(88,1))
SAMPLE_RATE_HZ = 8           # notebook: 1408 samples @128 Hz, decimated [0::16] -> 88 @ 8 Hz
WINDOW_SECONDS = WINDOW_SAMPLES / SAMPLE_RATE_HZ  # 11 s
BN_EPSILON = 1e-3            # tf.keras BatchNormalization default used in the notebook


@dataclass(frozen=True)
class MLSettings:
    weights_path: Path
    normalization_mode: str          # "global" | "window"
    train_mean: float | None
    train_std: float | None
    apnea_class_index: int
    apnea_threshold: float
    window_stride_samples: int
    min_event_windows: int
    spo2_valid_min: float
    spo2_valid_max: float
    max_invalid_fraction: float
    max_sample_interval_s: float
    max_gap_s: float
    min_duration_minutes: float
    reliable_duration_minutes: float
    ubidots_token: str
    ubidots_base_url: str
    ubidots_device_label: str
    ubidots_timeout_s: float
    ubidots_max_points: int


def load_settings() -> MLSettings:
    mean = os.environ.get("SOMNNET_TRAIN_MEAN", "").strip()
    std = os.environ.get("SOMNNET_TRAIN_STD", "").strip()
    mean_v = float(mean) if mean else None
    std_v = float(std) if std else None
    mode = os.environ.get("SOMNNET_NORMALIZATION_MODE", "").strip().lower()
    if not mode:
        mode = "global" if (mean_v is not None and std_v is not None) else "window"
    if mode not in ("global", "window"):
        raise ValueError("SOMNNET_NORMALIZATION_MODE must be 'global' or 'window'")
    if mode == "global" and (mean_v is None or std_v is None or std_v <= 0):
        raise ValueError("SOMNNET_NORMALIZATION_MODE=global requires SOMNNET_TRAIN_MEAN and a positive SOMNNET_TRAIN_STD")
    return MLSettings(
        weights_path=Path(os.environ.get("SOMNNET_WEIGHTS_PATH") or _HERE / "weights" / "best_weights_spo2_32layer_binary.hdf5"),
        normalization_mode=mode, train_mean=mean_v, train_std=std_v,
        apnea_class_index=_i("SOMNNET_APNEA_CLASS_INDEX", 1),
        apnea_threshold=_f("SOMNNET_APNEA_THRESHOLD", 0.5),
        window_stride_samples=_i("SOMNNET_WINDOW_STRIDE_SAMPLES", WINDOW_SAMPLES),
        min_event_windows=_i("SOMNNET_MIN_EVENT_WINDOWS", 1),
        spo2_valid_min=_f("SPO2_VALID_MIN", 50.0), spo2_valid_max=_f("SPO2_VALID_MAX", 100.0),
        max_invalid_fraction=_f("SPO2_MAX_INVALID_FRACTION", 0.5),
        max_sample_interval_s=_f("SPO2_MAX_SAMPLE_INTERVAL_S", 5.0),
        max_gap_s=_f("SPO2_MAX_GAP_S", 10.0),
        min_duration_minutes=_f("ML_MIN_DURATION_MINUTES", 5.0),
        reliable_duration_minutes=_f("ML_RELIABLE_DURATION_MINUTES", 60.0),
        ubidots_token=os.environ.get("UBIDOTS_TOKEN", "").strip(),
        ubidots_base_url=os.environ.get("UBIDOTS_BASE_URL", "https://industrial.api.ubidots.com").rstrip("/"),
        ubidots_device_label=os.environ.get("UBIDOTS_DEVICE_LABEL", "esp32_health_monitor").strip(),
        ubidots_timeout_s=_f("UBIDOTS_TIMEOUT_S", 20.0),
        ubidots_max_points=_i("UBIDOTS_MAX_POINTS", 200000),
    )
