"""
cortex.py - The LLM-Powered Analytical Engine (Layer 3)

The Cortex runs a "tail-pass" after each Operator interaction,
extracting knowledge without slowing down the conversation.

Lens 1: Entity Extraction
    - LLM-based NER using Tier 1 (Haiku)
    - New entities marked with is_new=True trigger Jidoka validation
    - Existing entities skip validation

Lens 2: Content Seed Mining
    - LLM identifies potential content moments
    - Seeds saved to entities/content-seeds/

Uses Tier 1 (Haiku) for speed/cost efficiency on every interaction.
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


def ask_entity_validation(
    entity_name: str,
    entity_type: str,
    context: str
) -> str:
    """
    Ask operator to validate a new entity (Jidoka).

    This is a Digital Jidoka halt - the system stops and asks
    the human operator to confirm before creating a new entity.

    Args:
        entity_name: The extracted entity name
        entity_type: The inferred entity type
        context: Surrounding context from transcript

    Returns:
        User choice: "1" (approve), "2" (reject), "3" (edit)
    """
    print(f"\n  [JIDOKA] New entity detected: {entity_name}")
    print(f"  Type: {entity_type}")
    print(f"  Context: ...{context}...")
    print()
    print("  Options:")
    print("    1. Approve - Create entity profile")
    print("    2. Reject - This is not a real entity")
    print("    3. Skip - Decide later")
    print()

    try:
        choice = input("  Choice [1/2/3]: ").strip()
        return choice if choice in ("1", "2", "3") else "3"
    except (KeyboardInterrupt, EOFError):
        return "3"


@dataclass
class ExtractedEntity:
    """An entity extracted from a transcript."""
    name: str
    entity_type: str  # player, parent, client, venue
    source_event_id: str
    confidence: float = 0.5
    context: str = ""
    is_new: bool = False  # New entities trigger Jidoka validation


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

    def _extract_entities_llm(self, event: dict) -> list[ExtractedEntity]:
        """
        Extract entities using Tier 1 LLM (Haiku).

        Lens 1: Named Entity Recognition that understands context
        and distinguishes real names from action words.

        Args:
            event: Telemetry event with raw_transcript

        Returns:
            List of extracted entities with is_new flag
        """
        try:
            from engine.llm_client import call_llm
        except ImportError:
            return []

        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        if not transcript.strip():
            return []

        # Build extraction prompt
        prompt = f"""Extract named entities from this transcript.
Return JSON with an "entities" array. Each entity should have:
- name: The full name (e.g., "Marcus Henderson")
- type: One of: player, parent, client, venue
- is_new: true if this appears to be a new person/place, false if existing

IMPORTANT:
- Only extract real person or place names
- Do NOT extract action words like "Generate", "Create", "Update", etc.
- Do NOT extract common nouns or verbs
- Focus on proper nouns that are actual names

Transcript: "{transcript}"

Return ONLY valid JSON, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=1,  # Haiku for speed/cost
                intent="cortex_extraction"
            )

            # Parse JSON response
            data = json.loads(response)
            entities_data = data.get("entities", [])

            entities = []
            for e in entities_data:
                name = e.get("name", "").strip()
                if not name:
                    continue

                entities.append(ExtractedEntity(
                    name=name,
                    entity_type=e.get("type", "player"),
                    source_event_id=event_id,
                    confidence=0.8,  # LLM extraction confidence
                    context=transcript[:100],
                    is_new=e.get("is_new", True)
                ))

            return entities

        except json.JSONDecodeError:
            # Malformed response - return empty list
            return []
        except Exception:
            # LLM failure - return empty list
            return []

    def _validate_new_entity(self, entity: ExtractedEntity) -> bool:
        """
        Validate a new entity with Jidoka approval.

        Only called for entities with is_new=True.

        Args:
            entity: The entity to validate

        Returns:
            True if approved, False if rejected/skipped
        """
        result = ask_entity_validation(
            entity_name=entity.name,
            entity_type=entity.entity_type,
            context=entity.context
        )

        if result == "1":
            # Approved - create the profile
            return self._create_entity_profile(entity)
        elif result == "2":
            # Rejected - do nothing
            return False
        else:
            # Skipped - defer for later
            return False

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
    # Lens 2: Content Seed Mining
    # =========================================================================

    def _mine_content_seeds(self, event: dict) -> list[dict]:
        """
        Mine content seeds using Tier 1 LLM (Haiku).

        Lens 2: Identifies moments worth sharing from transcripts.
        Seeds are saved for later compilation by the Content Engine.

        Args:
            event: Telemetry event with raw_transcript

        Returns:
            List of content seed dictionaries
        """
        try:
            from engine.llm_client import call_llm
        except ImportError:
            return []

        transcript = event.get("raw_transcript", "")
        event_id = event.get("id", "unknown")

        if not transcript.strip():
            return []

        # Build content mining prompt
        prompt = f"""Analyze this transcript for content-worthy moments.
Return JSON with a "content_seeds" array. Each seed should have:
- title: Short catchy title for the content
- content: The core message or insight
- pillar: One of: training, coaching, community, surrender
- suggested_platforms: Array of platforms (tiktok, instagram, x)

Look for:
- Moments of progress or breakthrough
- Coaching insights or wisdom
- Community building opportunities
- Stories of perseverance

Transcript: "{transcript}"

Return ONLY valid JSON with 0-3 content seeds, no explanations:"""

        try:
            response = call_llm(
                prompt=prompt,
                tier=1,  # Haiku for speed/cost
                intent="cortex_extraction"
            )

            # Parse JSON response
            data = json.loads(response)
            seeds = data.get("content_seeds", [])

            # Save each seed
            for seed in seeds:
                self._save_content_seed(seed, event_id)

            return seeds

        except json.JSONDecodeError:
            return []
        except Exception:
            return []

    def _save_content_seed(self, seed: dict, event_id: str) -> bool:
        """
        Save a content seed to entities/content-seeds/.

        Args:
            seed: Content seed dictionary with title, content, pillar
            event_id: Source event ID for tracing

        Returns:
            True if saved successfully
        """
        entities_dir = get_entities_dir()
        seeds_dir = entities_dir / "content-seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from title
        title = seed.get("title", "untitled")
        filename = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '-').lower()
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        filepath = seeds_dir / f"{timestamp}-{filename}.md"

        content = f"""# {seed.get('title', 'Untitled')}

**Pillar:** {seed.get('pillar', 'general')}
**Mined:** {datetime.now(timezone.utc).isoformat()}
**Source Event:** {event_id[:8]}...

## Content
{seed.get('content', '')}

## Suggested Platforms
{', '.join(seed.get('suggested_platforms', []))}

---
_Auto-generated by Cortex Lens 2. Review before compilation._
"""

        try:
            filepath.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False


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
