"""Reporting package public API."""

from __future__ import annotations

from dgpforge.reporting.labels import ESTIMATOR_LABELS
from dgpforge.reporting.render import generate_report


__all__ = ["ESTIMATOR_LABELS", "generate_report"]
