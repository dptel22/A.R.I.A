"""
aria/domain/models.py - Data structures and enums for A.R.I.A.'s domain layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class SeverityLevel(str, Enum):
    """Native severity classes outputted by the YOLOv11 model."""
    LOW = "damage_low"
    MEDIUM = "damage_medium"
    HIGH = "damage_high"
    CRITICAL = "damage_critical"

    @property
    def public_label(self) -> str:
        return self.name


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
    contractor_email: str = field(repr=False)   # PII — excluded from repr/logs
    dlp_end_date: date | None = None
    is_dlp_active: bool = False

    @property
    def masked_contractor_email(self) -> str:
        """Return a redacted email safe for logs and external serialisation."""
        if not self.contractor_email or "@" not in self.contractor_email:
            return "***"
        local, domain = self.contractor_email.split("@", 1)
        if not local:
            return f"***@{domain}"
        return f"{local[0]}***@{domain}"

    def to_public_dict(self) -> dict:
        """Return a dict safe for API responses / logging (email masked)."""
        return {
            "segment_id": self.segment_id,
            "segment_name": self.segment_name,
            "contract_id": self.contract_id,
            "contractor_name": self.contractor_name,
            "contractor_email": self.masked_contractor_email,
            "dlp_end_date": str(self.dlp_end_date) if self.dlp_end_date else None,
            "is_dlp_active": self.is_dlp_active,
        }
