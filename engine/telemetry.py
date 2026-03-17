"""
telemetry.py - The Feed-First Engine

Every interaction MUST be logged as structured data before any processing.
This enforces the first stage of the Invariant Pipeline.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from engine.profile import get_telemetry_path


def create_event(
    source: str,
    raw_transcript: str,
    zone_context: str = "green",
    inferred: Optional[dict] = None
) -> dict:
    """
    Create a telemetry event conforming to the required schema.

    Schema:
        - id: UUID v4
        - timestamp: ISO-8601 format
        - source: Origin of the event (e.g., 'operator_session')
        - raw_transcript: The raw user input or system message
        - inferred: Dict of inferred data (default empty)
        - zone_context: Current zone classification
    """
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "raw_transcript": raw_transcript,
        "inferred": inferred if inferred is not None else {},
        "zone_context": zone_context
    }


def log_event(
    source: str,
    raw_transcript: str,
    zone_context: str = "green",
    inferred: Optional[dict] = None
) -> dict:
    """
    Append a telemetry event to the JSONL file.

    Returns the logged event for pipeline continuity.
    """
    event = create_event(
        source=source,
        raw_transcript=raw_transcript,
        zone_context=zone_context,
        inferred=inferred
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
