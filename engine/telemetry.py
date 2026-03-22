"""
telemetry.py - The Feed-First Engine

Every interaction MUST be logged as structured data before any processing.
This enforces the first stage of the Invariant Pipeline.

Sprint 6: Strict schema validation ensures the Cortex never ingests malformed data.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from engine.profile import get_telemetry_path


# =========================================================================
# Schema Validation
# =========================================================================

class TelemetryValidationError(Exception):
    """Raised when a telemetry event fails schema validation."""
    pass


VALID_ZONES = {"green", "yellow", "red"}


def _generate_id() -> str:
    """Generate a UUID v4 string."""
    return str(uuid.uuid4())


def _generate_timestamp() -> str:
    """Generate an ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


# =========================================================================
# Telemetry Event Schema
# =========================================================================

@dataclass
class TelemetryEvent:
    """
    Formal schema for telemetry events.

    All events MUST conform to this schema before being logged.
    This ensures the Cortex analytical engine never ingests malformed data.

    Required Fields:
        - id: UUID v4 (auto-generated if not provided)
        - timestamp: ISO-8601 format (auto-generated if not provided)
        - source: Origin of the event (e.g., 'operator_session')
        - raw_transcript: The raw user input or system message
        - zone_context: Current zone classification (green, yellow, red)

    Optional Fields:
        - inferred: Dict of inferred data (default empty dict)
        - intent: Classified intent name (first-class for auditability)
        - tier: LLM tier used (0=cache, 1=haiku, 2=sonnet, 3=opus)
        - confidence: Classification confidence (0.0-1.0)
        - cost_usd: LLM cost for this operation
        - human_feedback: Operator response ("approved", "rejected", "clarified")
    """
    source: str
    raw_transcript: str
    zone_context: str
    id: str = field(default_factory=_generate_id)
    timestamp: str = field(default_factory=_generate_timestamp)
    inferred: dict = field(default_factory=dict)

    # Routing metadata — first-class for auditability
    # These fields make routing decisions grep-able without parsing inferred.
    intent: Optional[str] = None
    tier: Optional[int] = None
    confidence: Optional[float] = None
    cost_usd: Optional[float] = None
    human_feedback: Optional[str] = None  # "approved", "rejected", "clarified"
    pattern_hash: Optional[str] = None  # Flywheel Stage 2: semantic pattern grouping

    def __post_init__(self):
        """Validate fields after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate all required fields."""
        if not self.source or not self.source.strip():
            raise TelemetryValidationError(
                "source is required and cannot be empty"
            )

        if not self.raw_transcript or not self.raw_transcript.strip():
            raise TelemetryValidationError(
                "raw_transcript is required and cannot be empty"
            )

        if not self.zone_context or not self.zone_context.strip():
            raise TelemetryValidationError(
                "zone_context is required and cannot be empty"
            )

        if self.zone_context not in VALID_ZONES:
            raise TelemetryValidationError(
                f"zone_context must be one of {VALID_ZONES}, got '{self.zone_context}'"
            )

        if not isinstance(self.inferred, dict):
            raise TelemetryValidationError(
                f"inferred must be a dict, got {type(self.inferred).__name__}"
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        event = {
            "id": self.id,
            "timestamp": self.timestamp,
            "source": self.source,
            "raw_transcript": self.raw_transcript,
            "zone_context": self.zone_context,
            "inferred": self.inferred
        }
        # Flat routing fields — included when set, omitted when None
        if self.intent is not None:
            event["intent"] = self.intent
        if self.tier is not None:
            event["tier"] = self.tier
        if self.confidence is not None:
            event["confidence"] = self.confidence
        if self.cost_usd is not None:
            event["cost_usd"] = self.cost_usd
        if self.human_feedback is not None:
            event["human_feedback"] = self.human_feedback
        if self.pattern_hash is not None:
            event["pattern_hash"] = self.pattern_hash
        return event


# =========================================================================
# Event Creation and Logging
# =========================================================================

def create_event(
    source: str,
    raw_transcript: str,
    zone_context: str = "green",
    inferred: Optional[dict] = None,
    intent: Optional[str] = None,
    tier: Optional[int] = None,
    confidence: Optional[float] = None,
    cost_usd: Optional[float] = None,
    human_feedback: Optional[str] = None,
    pattern_hash: Optional[str] = None,
) -> dict:
    """
    Create a telemetry event conforming to the required schema.

    Validates all fields before returning. Raises TelemetryValidationError
    if any required field is missing or malformed.

    Args:
        source: Origin of the event (e.g., 'operator_session')
        raw_transcript: The raw user input or system message
        zone_context: Zone classification (green, yellow, red)
        inferred: Dict of inferred data (default empty)
        intent: Classified intent name (flat field for auditability)
        tier: LLM tier used (0=cache, 1=haiku, 2=sonnet, 3=opus)
        confidence: Classification confidence (0.0-1.0)
        cost_usd: LLM cost for this operation
        human_feedback: Operator response ("approved", "rejected", "clarified")
        pattern_hash: Flywheel pattern grouping hash (12-char hex)

    Returns:
        Dict conforming to telemetry schema

    Raises:
        TelemetryValidationError: If validation fails
    """
    # Validate inferred type before creating event
    if inferred is not None and not isinstance(inferred, dict):
        raise TelemetryValidationError(
            f"inferred must be a dict, got {type(inferred).__name__}"
        )

    # Create and validate event
    event = TelemetryEvent(
        source=source,
        raw_transcript=raw_transcript,
        zone_context=zone_context,
        inferred=inferred if inferred is not None else {},
        intent=intent,
        tier=tier,
        confidence=confidence,
        cost_usd=cost_usd,
        human_feedback=human_feedback,
        pattern_hash=pattern_hash,
    )

    return event.to_dict()


def log_event(
    source: str,
    raw_transcript: str,
    zone_context: str = "green",
    inferred: Optional[dict] = None,
    intent: Optional[str] = None,
    tier: Optional[int] = None,
    confidence: Optional[float] = None,
    cost_usd: Optional[float] = None,
    human_feedback: Optional[str] = None,
    pattern_hash: Optional[str] = None,
) -> dict:
    """
    Append a telemetry event to the JSONL file.

    Validates the event BEFORE writing to ensure data integrity.
    If validation fails, raises TelemetryValidationError and does NOT write.

    Args:
        source: Origin of the event (e.g., 'operator_session')
        raw_transcript: The raw user input or system message
        zone_context: Zone classification (green, yellow, red)
        inferred: Dict of inferred data (default empty)
        intent: Classified intent name (flat field for auditability)
        tier: LLM tier used (0=cache, 1=haiku, 2=sonnet, 3=opus)
        confidence: Classification confidence (0.0-1.0)
        cost_usd: LLM cost for this operation
        human_feedback: Operator response ("approved", "rejected", "clarified")
        pattern_hash: Flywheel pattern grouping hash (12-char hex)

    Returns:
        The logged event dict for pipeline continuity

    Raises:
        TelemetryValidationError: If validation fails (no write occurs)
    """
    # Create and validate event (raises on failure)
    event = create_event(
        source=source,
        raw_transcript=raw_transcript,
        zone_context=zone_context,
        inferred=inferred,
        intent=intent,
        tier=tier,
        confidence=confidence,
        cost_usd=cost_usd,
        human_feedback=human_feedback,
        pattern_hash=pattern_hash,
    )

    # Get profile-aware telemetry path
    telemetry_path = get_telemetry_path()

    # Ensure parent directory exists
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    # Append to JSONL (one JSON object per line)
    with open(telemetry_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    return event


def read_recent_events(limit: int = 10) -> list[dict]:
    """
    Read the most recent telemetry events.
    Useful for context retrieval in later pipeline stages.
    """
    telemetry_path = get_telemetry_path()

    if not telemetry_path.exists():
        return []

    events = []
    with open(telemetry_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    return events[-limit:]
