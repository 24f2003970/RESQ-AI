"""Small shared helpers for deterministic evaluation summaries."""
from __future__ import annotations

from decimal import Decimal


OBJECTIVE_DELTA_TOLERANCE = Decimal("0.01")


def classify_objective_delta(delta: Decimal | float | str) -> str:
    """Return one exclusive objective outcome using a symmetric 0.01 deadband.

    Decimal(str(value)) avoids binary-float boundary surprises for recorded
    decimal scores. Values exactly at either threshold are ties.
    """
    value = delta if isinstance(delta, Decimal) else Decimal(str(delta))
    if not value.is_finite():
        raise ValueError("objective delta must be finite")
    if value > OBJECTIVE_DELTA_TOLERANCE:
        return "improved"
    if value < -OBJECTIVE_DELTA_TOLERANCE:
        return "lower"
    return "tied"
