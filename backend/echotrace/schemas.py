"""WebSocket message contract (mirrored by frontend/src/types.ts). Do not change without agreement.

All messages: {type, data}. Every data object carries source, t (s since session start) and wall (ISO time).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Source = Literal["LIVE", "RECORDED", "SIMULATED"]
Zone = Literal["LEFT", "CENTRE", "RIGHT", "UNKNOWN"]
Risk = Literal["GREEN", "AMBER", "RED"]


class Base(BaseModel):
    source: Source
    t: float
    wall: str


class TopLabel(BaseModel):
    label: str
    p: float


class FrameData(Base):
    top: list[TopLabel]
    categories: dict[str, float]
    rms_db: list[float]


class EventData(Base):
    id: str
    t_start: float
    t_end: float
    category: str
    label: str
    confidence: float
    zone: Zone
    angle_deg: float | None


class SequenceData(Base):
    id: str
    event_ids: list[str]
    pattern: str
    risk: Risk
    explanation: list[str]
    summary: str
    trajectory: list[Zone]


class StatusData(Base):
    risk: Risk
    latency_ms: float              # last measured event latency; 0.0 until the first event is sent
    device: str
    host_api: str
    sample_rate: int
    channels: int
    localization: Literal["ON", "OFF"]
    model_device: Literal["cpu", "cuda"]
    dropped_blocks: int
    sensitivity: Literal["normal", "high"]   # detection threshold profile (config.SENSITIVITY_PROFILES)


class FrameMsg(BaseModel):
    type: Literal["frame"] = "frame"
    data: FrameData


class EventMsg(BaseModel):
    type: Literal["event"] = "event"
    data: EventData


class SequenceMsg(BaseModel):
    type: Literal["sequence"] = "sequence"
    data: SequenceData


class StatusMsg(BaseModel):
    type: Literal["status"] = "status"
    data: StatusData


# --------------------------------------------------------------------------- GET /api/metrics
# docs/metrics.json is written by Person C's eval and served AS-IS ({} when missing). This model documents
# and checks the agreed shape; the server does not rewrite the file.
class FalseAlerts(BaseModel):
    echotrace: int
    baseline: int
    reduction_pct: float | None        # null when the baseline raised no alerts (undefined, not 100%)


class LatencyStats(BaseModel):
    mean: float | None                 # null = not measured (only live runs count; never estimated)
    p95: float | None


class ClipResult(BaseModel):
    clip: str
    expected: str
    got: str
    ok: bool


class Metrics(BaseModel):
    generated_at: str
    clips: int
    sequence_accuracy: float | None
    false_alerts: FalseAlerts
    lcr_accuracy: float | None
    latency_ms: LatencyStats
    per_clip: list[ClipResult]


MESSAGE_TYPES = {"frame": FrameMsg, "event": EventMsg, "sequence": SequenceMsg, "status": StatusMsg}


def validate(msg: dict) -> BaseModel:
    """Parse a {type, data} dict against the contract (raises on any mismatch)."""
    return MESSAGE_TYPES[msg["type"]].model_validate(msg)
