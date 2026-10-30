"""Unique Patient ID generation — format SGP-XXXXXX (6 digits)."""

import random

from utils.storage import patient_exists

_PREFIX = "SGP-"
_DIGITS = 6


def generate_patient_id() -> str:
    for _ in range(1000):
        candidate = f"{_PREFIX}{random.randint(0, 10**_DIGITS - 1):0{_DIGITS}d}"
        if not patient_exists(candidate):
            return candidate
    raise RuntimeError("Unable to generate a unique Patient ID after 1000 attempts")


def is_valid_patient_id_format(patient_id: str) -> bool:
    if not isinstance(patient_id, str):
        return False
    if not patient_id.startswith(_PREFIX):
        return False
    suffix = patient_id[len(_PREFIX):]
    return len(suffix) == _DIGITS and suffix.isdigit()
