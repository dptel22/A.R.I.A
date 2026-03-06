"""
core/models.py — Data structures and Enums for the Core A.R.I.A. layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class SeverityLevel(str, Enum):
    """Native severity classes outputted by the YOLOv11 model."""
    LOW = "damage_low"
    MEDIUM = "damage_medium"
    HIGH = "damage_high"


class ActionType(str, Enum):
    """Business actions determined by severity."""
    LOG_ONLY = "LOG_ONLY"
    FLAG_INSPECTOR = "FLAG_INSPECTOR"
    ENFORCE = "ENFORCE"


@dataclass(frozen=True)
class DetectionMetadata:
    """Metadata for a specific road damage detection."""
    gps_lat: float
    gps_lon: float
    severity: SeverityLevel
    confidence: float = 0.0


@dataclass(frozen=True)
class ContractStatus:
    """Active contract details and DLP compliance status for a road segment."""
    segment_id: int
    segment_name: str
    contract_id: int
    contractor_name: str
    contractor_email: str
    dlp_end_date: date | None
    is_dlp_active: bool
