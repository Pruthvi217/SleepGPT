"""Event aggregation + Estimated AHI. The network output is a per-window apnea probability, NOT an AHI."""
from __future__ import annotations
import numpy as np
from . import config as C


def aggregate_events(starts, is_apnea, is_valid, grid_t0, min_event_windows=1, stride=C.WINDOW_SAMPLES):
    """Consecutive positive, valid windows are merged into one event. An invalid window ends a run."""
    events, run = [], []
    def flush():
        if run and len(run) >= min_event_windows:
            a, b = run[0], run[-1]
            events.append({"start_s": float(grid_t0 + starts[a] / C.SAMPLE_RATE_HZ),
                           "end_s": float(grid_t0 + (starts[b] + C.WINDOW_SAMPLES) / C.SAMPLE_RATE_HZ),
                           "windows": len(run)})
        run.clear()
    prev = None
    for i in range(len(starts)):
        pos = bool(is_apnea[i] and is_valid[i])
        contiguous = prev is not None and starts[i] - starts[prev] == stride
        if pos and (not run or contiguous):
            run.append(i)
        else:
            flush()
            if pos:
                run.append(i)
        prev = i
    flush()
    return events


def estimated_ahi(n_events: int, analysed_hours: float) -> float:
    """AHI = qualifying respiratory events / hours. analysed_hours is the *analysed recording time*
    (no sleep staging is available from SpO2 alone), so it is a sleep-time proxy."""
    if analysed_hours <= 0:
        raise ValueError("analysed duration must be > 0")
    return n_events / analysed_hours
