"""
cortex.py - The Analytical Engine (Layer 3)

The Cortex runs a "tail-pass" after each Operator interaction,
extracting knowledge without slowing down the conversation.

Functions:
    - Entity extraction from transcripts
    - Kaizen proposal generation
    - Knowledge graph updates (future)

Sprint 4: Local mock implementations.
Future: LLM-powered analysis.
"""

import re
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from engine.profile import (
    get_telemetry_path,
    get_entities_dir,
    get_queue_dir,
    get_pending_queue_path
)


@dataclass
class ExtractedEntity:
    """An entity extracted from a transcript."""
    name: str
    entity_type: str  # player, parent, client, venue
    source_event_id: str
    confidence: float = 0.5
    context: str = ""


@dataclass
class KaizenProposal:
    """A continuous improvement proposal."""
    id: str
    proposal: str
    trigger: str
    source_event_id: str
    created_at: str
    status: str = "pending"


class Cortex:
    """
    The Analytical Engine that processes telemetry in the background.

    The Cortex runs after each interaction to:
    1. Extract entities (players, parents, venues)
    2. Generate Kaizen proposals for improvement
    3. Update knowledge graphs (future)

    Usage:
        cortex = Cortex()
        cortex.run_analysis_pass()  # Process latest telemetry
    """

    def __init__(self):
        self.processed_event_ids: set[str] = set()
        self._load_processed_ids()

    def _load_processed_ids(self) -> None:
        """Load IDs of previously processed events to avoid duplicates."""
        queue_dir = get_queue_dir()
        processed_file = queue_dir / ".processed_events"
        if processed_file.exists():
            self.processed_event_ids = set(
                processed_file.read_text(encoding="utf-8").strip().split("\n")
            )

    def _save_processed_id(self, event_id: str) -> None:
        """Mark an event as processed."""
        self.processed_event_ids.add(event_id)
        queue_dir = get_queue_dir()
        processed_file = queue_dir / ".processed_events"
        processed_file.parent.mkdir(parents=True, exist_ok=True)
        with open(processed_file, "a", encoding="utf-8") as f:
            f.write(event_id + "\n")

    def run_analysis_pass(self, telemetry_file: Optional[str] = None) -> dict:
        """
        Run a tail-pass analysis on recent telemetry.

        Args:
            telemetry_file: Path to telemetry JSONL (default: profile's telemetry.jsonl)

        Returns:
            Summary of extraction results
        """
        telemetry_path = Path(telemetry_file) if telemetry_file else get_telemetry_path()

        if not telemetry_path.exists():
            return {"status": "no_telemetry", "entities": 0, "kaizen": 0}

        # Read recent events
        events = self._read_recent_events(telemetry_path, limit=10)

        # Filter to unprocessed operator_session events
        new_events = [
            e for e in events
            if e.get("id") not in self.processed_event_ids
            and e.get("source") == "operator_session"
        ]

        if not new_events:
            return {"status": "no_new_events", "entities": 0, "kaizen": 0}

        entities_created = 0
        kaizen_created = 0

        for event in new_events:
            # Run entity extraction
            entities = self._extract_entities(event)
            for entity in entities:
                if self._create_entity_profile(entity):
                    entities_created += 1

            # Run Kaizen analysis
            proposals = self._generate_kaizen(event)
            for proposal in proposals:
                if self._queue_kaizen(proposal):
                    kaizen_created += 1

            # Mark as processed
            self._save_processed_id(event.get("id", ""))

        return {
            "status": "complete",
            "events_processed": len(new_events),
            "entities": entities_created,
            "kaizen": kaizen_created
        }

    def _read_recent_events(self, path: Path, limit: int = 10) -> list[dict]:
        """Read the most recent telemetry events."""
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events[-limit:]

    # =========================================================================
    # Entity Extraction
    # =========================================================================

    def _extract_entities(self, event: dict) -> list[ExtractedEntity]:
        """
        Extract entities from a telemetry event.

        Sprint 4: Mock implementation using regex for capitalized names.
        Future: LLM-powered NER.
        """
        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        entities = []

        # Pattern: Capitalized words that look like names
        # Matches: "Henderson", "Marcus", "St. Mary's"
        # Excludes: Common words, single letters, all-caps
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'

        # Common words to exclude (sentence starters, days, months, domain terms)
        exclude_words = {
            # Sentence starters / common words
            "The", "This", "That", "What", "When", "Where", "Why", "How",
            "Need", "Want", "Help", "Show", "Get", "Make", "Take", "Give",
            "Let", "Can", "Will", "Would", "Could", "Should", "May", "Might",
            "Have", "Has", "Had", "Been", "Being", "Are", "Was", "Were",
            "Just", "Also", "Still", "Even", "Only", "Very", "Really",
            # Days and months
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
            "January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December",
            # Domain-specific terms
            "Coach", "Player", "Parent", "Client", "Venue", "Session",
            "Green", "Yellow", "Red", "Zone", "Dock", "Action", "Status",
            "Practice", "Lesson", "Tournament", "Team", "Golf", "Swing",
            "Revenue", "Goal", "Target", "Content", "Email", "Call",
            # Common verbs that might be capitalized
            "Schedule", "Send", "Create", "Update", "Delete", "Draft"
        }

        matches = re.findall(name_pattern, transcript)

        for match in matches:
            if match not in exclude_words and len(match) > 2:
                # Extract surrounding context
                context_match = re.search(
                    rf'.{{0,30}}{re.escape(match)}.{{0,30}}',
                    transcript
                )
                context = context_match.group(0) if context_match else ""

                entities.append(ExtractedEntity(
                    name=match,
                    entity_type="player",  # Default to player for this sprint
                    source_event_id=event_id,
                    confidence=0.6,
                    context=context
                ))

        return entities

    def _create_entity_profile(self, entity: ExtractedEntity) -> bool:
        """
        Create a Markdown profile for an extracted entity.

        Returns True if a new profile was created.
        """
        # Determine the correct subfolder
        type_map = {
            "player": "players",
            "parent": "parents",
            "client": "clients",
            "venue": "venues"
        }
        subfolder = type_map.get(entity.entity_type, "players")
        entities_dir = get_entities_dir()
        entity_dir = entities_dir / subfolder

        # Create directory if needed
        entity_dir.mkdir(parents=True, exist_ok=True)

        # Normalize filename
        filename = re.sub(r'[^\w\s-]', '', entity.name).strip().replace(' ', '-').lower()
        filepath = entity_dir / f"{filename}.md"

        # Don't overwrite existing profiles
        if filepath.exists():
            return False

        # Create the profile
        profile_content = f"""# {entity.name}

## Profile
- **Type:** {entity.entity_type.title()}
- **First Seen:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
- **Source Event:** {entity.source_event_id[:8]}...
- **Confidence:** {entity.confidence:.0%}

## Context
> {entity.context}

## Notes
_Auto-generated by Cortex. Review and enrich this profile._

## History
- {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: Profile created via entity extraction
"""

        filepath.write_text(profile_content, encoding="utf-8")
        return True

    # =========================================================================
    # Kaizen Generation
    # =========================================================================

    def _generate_kaizen(self, event: dict) -> list[KaizenProposal]:
        """
        Generate Kaizen proposals from a telemetry event.

        Sprint 4: Mock implementation using keyword triggers.
        Future: LLM-powered insight generation.
        """
        transcript = event.get("raw_transcript", "").lower()
        event_id = event.get("id", "unknown")

        proposals = []

        # Trigger: Frustration or struggle
        if "frustrated" in transcript or "struggling" in transcript:
            proposals.append(KaizenProposal(
                id=f"kaizen-{event_id[:8]}",
                proposal="Draft content seed about overcoming frustration on the course?",
                trigger="frustration_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        # Trigger: Practice or drill mention
        if "practice" in transcript and ("need" in transcript or "help" in transcript):
            proposals.append(KaizenProposal(
                id=f"kaizen-practice-{event_id[:8]}",
                proposal="Create a new drill sequence for the mentioned skill gap?",
                trigger="practice_need_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        # Trigger: Parent mention
        if "parent" in transcript and ("talk" in transcript or "email" in transcript or "call" in transcript):
            proposals.append(KaizenProposal(
                id=f"kaizen-parent-{event_id[:8]}",
                proposal="Schedule parent communication touchpoint?",
                trigger="parent_outreach_detected",
                source_event_id=event_id,
                created_at=datetime.now(timezone.utc).isoformat()
            ))

        return proposals

    def _queue_kaizen(self, proposal: KaizenProposal) -> bool:
        """
        Add a Kaizen proposal to the pending queue.

        Returns True if the proposal was added.
        """
        queue_dir = get_queue_dir()
        pending_path = get_pending_queue_path()
        queue_dir.mkdir(parents=True, exist_ok=True)

        # Load existing queue
        pending = []
        if pending_path.exists():
            content = pending_path.read_text(encoding="utf-8")
            if content.strip():
                pending = yaml.safe_load(content) or []

        # Check for duplicates by ID
        existing_ids = {p.get("id") for p in pending}
        if proposal.id in existing_ids:
            return False

        # Add the proposal
        pending.append({
            "id": proposal.id,
            "proposal": proposal.proposal,
            "trigger": proposal.trigger,
            "source_event_id": proposal.source_event_id,
            "created_at": proposal.created_at,
            "status": proposal.status
        })

        # Save the queue
        with open(pending_path, "w", encoding="utf-8") as f:
            yaml.dump(pending, f, default_flow_style=False, sort_keys=False)

        return True


# =========================================================================
# Queue Management
# =========================================================================

def load_pending_queue() -> list[dict]:
    """Load pending Kaizen items from the queue."""
    pending_path = get_pending_queue_path()

    if not pending_path.exists():
        return []

    content = pending_path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    return yaml.safe_load(content) or []


def clear_pending_queue() -> None:
    """Clear all items from the pending queue."""
    pending_path = get_pending_queue_path()
    if pending_path.exists():
        pending_path.write_text("", encoding="utf-8")


def remove_from_queue(item_id: str) -> bool:
    """Remove a specific item from the pending queue."""
    pending_path = get_pending_queue_path()
    pending = load_pending_queue()
    updated = [p for p in pending if p.get("id") != item_id]

    if len(updated) == len(pending):
        return False  # Item not found

    with open(pending_path, "w", encoding="utf-8") as f:
        if updated:
            yaml.dump(updated, f, default_flow_style=False, sort_keys=False)
        else:
            f.write("")

    return True


# Module-level singleton
_cortex_instance: Optional[Cortex] = None


def get_cortex() -> Cortex:
    """Get the shared Cortex instance."""
    global _cortex_instance
    if _cortex_instance is None:
        _cortex_instance = Cortex()
    return _cortex_instance


def run_tail_pass() -> dict:
    """
    Run a tail-pass analysis on recent telemetry.

    This is the primary interface for the pipeline integration.
    """
    cortex = get_cortex()
    return cortex.run_analysis_pass()
