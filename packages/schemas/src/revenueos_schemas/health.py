"""Health/readiness contract schemas (V1A-0 bootstrap only)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

VerificationState = Literal[
    "UNVERIFIED",
    "CONTRACT_VERIFIED",
    "FIXTURE_VERIFIED",
    "LIVE_VERIFIED",
    "PRODUCTION_VERIFIED",
    "NOT_APPLICABLE",
]


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    phase: str
    time: datetime


class ServiceCheck(BaseModel):
    name: str
    status: Literal["up", "down", "unknown"]
    latency_ms: float | None = None
    required_for_ready: bool = False
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    ready: bool
    service: str
    version: str
    environment: str
    phase: str
    checks: list[ServiceCheck] = Field(default_factory=list)
    time: datetime
