"""
test_telemetry_schema.py - Tests for Telemetry Schema Validation

Sprint 6: Portability, Polish, and The Final Seal

The telemetry layer must enforce a strict schema contract so the Cortex
never ingests malformed data. Every event MUST have required fields.
"""

import pytest
import json
from datetime import datetime


class TestTelemetryEventSchema:
    """Tests for TelemetryEvent dataclass schema."""

    def test_telemetry_event_has_required_fields(self):
        """Assert TelemetryEvent enforces required fields."""
        from engine.telemetry import TelemetryEvent

        event = TelemetryEvent(
            source="operator_session",
            raw_transcript="test input",
            zone_context="green"
        )

        # Required fields must be present
        assert event.id is not None
        assert event.timestamp is not None
        assert event.source == "operator_session"
        assert event.raw_transcript == "test input"
        assert event.zone_context == "green"

    def test_telemetry_event_auto_generates_id(self):
        """Assert TelemetryEvent auto-generates UUID if not provided."""
        from engine.telemetry import TelemetryEvent

        event = TelemetryEvent(
            source="test",
            raw_transcript="test",
            zone_context="green"
        )

        # ID should be a valid UUID string
        assert len(event.id) == 36  # UUID format
        assert event.id.count("-") == 4

    def test_telemetry_event_auto_generates_timestamp(self):
        """Assert TelemetryEvent auto-generates ISO timestamp if not provided."""
        from engine.telemetry import TelemetryEvent

        event = TelemetryEvent(
            source="test",
            raw_transcript="test",
            zone_context="green"
        )

        # Timestamp should be ISO format
        assert "T" in event.timestamp
        # Should be parseable
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))

    def test_telemetry_event_to_dict(self):
        """Assert TelemetryEvent converts to dict for JSON serialization."""
        from engine.telemetry import TelemetryEvent

        event = TelemetryEvent(
            source="operator_session",
            raw_transcript="hello world",
            zone_context="yellow"
        )

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict["source"] == "operator_session"
        assert event_dict["raw_transcript"] == "hello world"
        assert event_dict["zone_context"] == "yellow"
        assert "id" in event_dict
        assert "timestamp" in event_dict


class TestTelemetrySchemaValidation:
    """Tests for strict schema validation in create_event and log_event."""

    def test_create_event_validates_source_required(self):
        """Assert create_event raises error if source is missing."""
        from engine.telemetry import create_event, TelemetryValidationError

        with pytest.raises(TelemetryValidationError) as exc_info:
            create_event(
                source="",  # Empty source
                raw_transcript="test",
                zone_context="green"
            )

        assert "source" in str(exc_info.value).lower()

    def test_create_event_validates_raw_transcript_required(self):
        """Assert create_event raises error if raw_transcript is missing."""
        from engine.telemetry import create_event, TelemetryValidationError

        with pytest.raises(TelemetryValidationError) as exc_info:
            create_event(
                source="test",
                raw_transcript="",  # Empty transcript
                zone_context="green"
            )

        assert "raw_transcript" in str(exc_info.value).lower()

    def test_create_event_validates_zone_context_required(self):
        """Assert create_event raises error if zone_context is missing."""
        from engine.telemetry import create_event, TelemetryValidationError

        with pytest.raises(TelemetryValidationError) as exc_info:
            create_event(
                source="test",
                raw_transcript="test",
                zone_context=""  # Empty zone
            )

        assert "zone_context" in str(exc_info.value).lower()

    def test_create_event_validates_zone_context_values(self):
        """Assert create_event only accepts valid zone values."""
        from engine.telemetry import create_event, TelemetryValidationError

        with pytest.raises(TelemetryValidationError) as exc_info:
            create_event(
                source="test",
                raw_transcript="test",
                zone_context="purple"  # Invalid zone
            )

        assert "zone_context" in str(exc_info.value).lower()

    def test_create_event_accepts_valid_zones(self):
        """Assert create_event accepts green, yellow, red zones."""
        from engine.telemetry import create_event

        for zone in ["green", "yellow", "red"]:
            event = create_event(
                source="test",
                raw_transcript="test",
                zone_context=zone
            )
            assert event["zone_context"] == zone


class TestTelemetrySchemaIntegrity:
    """Tests for schema integrity in logged events."""

    def test_log_event_enforces_schema(self, tmp_path, monkeypatch):
        """Assert log_event validates before writing."""
        from engine.telemetry import log_event, TelemetryValidationError

        # Use temp telemetry file
        test_telemetry = tmp_path / "telemetry.jsonl"
        monkeypatch.setattr(
            "engine.telemetry.get_telemetry_path",
            lambda: test_telemetry
        )

        # Valid event should succeed
        event = log_event(
            source="test_source",
            raw_transcript="test transcript",
            zone_context="green"
        )

        assert event["source"] == "test_source"
        assert test_telemetry.exists()

    def test_log_event_rejects_invalid_schema(self, tmp_path, monkeypatch):
        """Assert log_event does not write malformed events."""
        from engine.telemetry import log_event, TelemetryValidationError
        from engine import profile

        # Use temp telemetry file
        test_telemetry = tmp_path / "telemetry.jsonl"
        monkeypatch.setattr(
            "engine.telemetry.get_telemetry_path",
            lambda: test_telemetry
        )

        # Invalid event should raise and NOT write
        with pytest.raises(TelemetryValidationError):
            log_event(
                source="",  # Invalid
                raw_transcript="test",
                zone_context="green"
            )

        # File should not exist or be empty
        if test_telemetry.exists():
            assert test_telemetry.read_text() == ""

    def test_logged_event_json_parseable(self, tmp_path, monkeypatch):
        """Assert logged events are valid JSON."""
        from engine.telemetry import log_event
        from engine import profile

        test_telemetry = tmp_path / "telemetry.jsonl"
        monkeypatch.setattr(
            "engine.telemetry.get_telemetry_path",
            lambda: test_telemetry
        )

        log_event(
            source="test",
            raw_transcript="hello world",
            zone_context="yellow"
        )

        # Read and parse
        content = test_telemetry.read_text().strip()
        event = json.loads(content)

        # Verify all required fields
        assert "id" in event
        assert "timestamp" in event
        assert "source" in event
        assert "raw_transcript" in event
        assert "zone_context" in event


class TestFlatRoutingFields:
    """Tests for flat routing fields (Purity v2)."""

    def test_telemetry_event_flat_routing_fields(self):
        """Flat routing fields appear in output when set."""
        from engine.telemetry import TelemetryEvent
        event = TelemetryEvent(
            source="test",
            raw_transcript="hello",
            zone_context="green",
            intent="strategy_session",
            tier=2,
            confidence=0.85,
            cost_usd=0.012,
            human_feedback="approved"
        )
        d = event.to_dict()
        assert d["intent"] == "strategy_session"
        assert d["tier"] == 2
        assert d["confidence"] == 0.85
        assert d["cost_usd"] == 0.012
        assert d["human_feedback"] == "approved"

    def test_telemetry_event_omits_none_fields(self):
        """None routing fields are omitted from dict output."""
        from engine.telemetry import TelemetryEvent
        event = TelemetryEvent(
            source="test",
            raw_transcript="hello",
            zone_context="green"
        )
        d = event.to_dict()
        assert "intent" not in d
        assert "tier" not in d
        assert "confidence" not in d
        assert "cost_usd" not in d
        assert "human_feedback" not in d

    def test_log_event_accepts_flat_fields(self):
        """log_event() accepts and persists flat routing fields."""
        from engine.telemetry import create_event
        event = create_event(
            source="test",
            raw_transcript="hello",
            zone_context="green",
            intent="general_chat",
            tier=1,
            confidence=0.95
        )
        assert event["intent"] == "general_chat"
        assert event["tier"] == 1
        assert event["confidence"] == 0.95


class TestTelemetryInferredField:
    """Tests for the optional inferred field."""

    def test_inferred_defaults_to_empty_dict(self):
        """Assert inferred field defaults to empty dict."""
        from engine.telemetry import create_event

        event = create_event(
            source="test",
            raw_transcript="test",
            zone_context="green"
        )

        assert event["inferred"] == {}

    def test_inferred_accepts_dict(self):
        """Assert inferred field accepts dict data."""
        from engine.telemetry import create_event

        event = create_event(
            source="test",
            raw_transcript="test",
            zone_context="green",
            inferred={"intent": "dock_status", "confidence": 0.95}
        )

        assert event["inferred"]["intent"] == "dock_status"
        assert event["inferred"]["confidence"] == 0.95

    def test_inferred_rejects_non_dict(self):
        """Assert inferred field rejects non-dict values."""
        from engine.telemetry import create_event, TelemetryValidationError

        with pytest.raises(TelemetryValidationError) as exc_info:
            create_event(
                source="test",
                raw_transcript="test",
                zone_context="green",
                inferred="not a dict"  # Invalid type
            )

        assert "inferred" in str(exc_info.value).lower()
