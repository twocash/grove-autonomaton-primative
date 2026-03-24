"""
flywheel.py - Skill Flywheel (DETECT + PROPOSE + APPROVE)

White Paper Part III S3: "Same intent pattern 3+ times in 14 days
-> surface as potential skill."

The Flywheel reads telemetry completion traces, groups by pattern_hash,
and surfaces recurring patterns as skill candidates. This is the
structural prerequisite for "authors its own evolution."

Stages implemented:
  1. OBSERVE - feed-first telemetry (telemetry.py)
  2. DETECT  - detect_patterns() in this module
  3. PROPOSE - propose_skills() in this module (V-016)
  4. APPROVE - approve_skill() in this module (V-019)
  5. EXECUTE - implicit via pattern cache (Tier 0 resolution)
  6. REFINE  - future sprint
"""

import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional

from engine.profile import get_telemetry_path, get_config_dir


def _load_detection_config() -> dict:
    """Load Flywheel detection thresholds from routing.config.

    Config Over Code: thresholds live in config, not hardcoded.
    Falls back to spec defaults if missing.
    """
    import yaml
    try:
        config_path = get_config_dir() / "routing.config"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data.get("flywheel", {})
    except Exception:
        pass
    return {}


def detect_patterns(days: Optional[int] = None, min_count: Optional[int] = None) -> list[dict]:
    """
    Flywheel Stage 2: DETECT.

    Reads telemetry completion traces, groups by pattern_hash,
    and returns patterns that exceed the occurrence threshold
    within the time window.

    Args:
        days: Rolling window in days (default from config, fallback 14)
        min_count: Minimum occurrences to surface (default from config, fallback 3)

    Returns:
        List of detected patterns, sorted by count descending:
        [
            {
                "pattern_hash": "a1b2c3d4e5f6",
                "intent": "explain_system",
                "domain": "system",
                "count": 5,
                "first_seen": "2026-03-20T...",
                "last_seen": "2026-03-22T...",
                "sample_inputs": ["how does the pipeline work", ...],
                "pattern_label": "architecture.pipeline",  # if available
                "is_candidate": True  # meets threshold
            }
        ]
    """
    config = _load_detection_config()
    if days is None:
        days = config.get("detection_window_days", 14)
    if min_count is None:
        min_count = config.get("detection_min_count", 3)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    telemetry_path = get_telemetry_path()

    if not telemetry_path.exists():
        return []

    # Read completion traces with pattern_hash
    patterns = defaultdict(lambda: {
        "count": 0,
        "intents": set(),
        "domains": set(),
        "timestamps": [],
        "sample_inputs": [],
        "pattern_labels": set(),
    })

    with open(telemetry_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only completion traces have pattern_hash
            ph = event.get("pattern_hash")
            if not ph:
                continue

            # Check time window
            ts_str = event.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                continue

            bucket = patterns[ph]
            bucket["count"] += 1
            if event.get("intent"):
                bucket["intents"].add(event["intent"])
            inferred = event.get("inferred", {})
            domain = inferred.get("domain") or event.get("zone_context") or "general"
            bucket["domains"].add(domain)
            bucket["timestamps"].append(ts_str)

            # Collect sample inputs (cap at 5)
            raw = event.get("raw_transcript", "")
            if raw and len(bucket["sample_inputs"]) < 5:
                if raw not in bucket["sample_inputs"]:
                    bucket["sample_inputs"].append(raw[:80])

            # Collect pattern labels from inferred metadata
            pl = inferred.get("pattern_label", "")
            if pl:
                bucket["pattern_labels"].add(pl)

    # Build result list
    results = []
    for ph, data in patterns.items():
        results.append({
            "pattern_hash": ph,
            "intent": ", ".join(sorted(data["intents"])) or "unknown",
            "domain": ", ".join(sorted(data["domains"])) or "general",
            "count": data["count"],
            "first_seen": min(data["timestamps"]) if data["timestamps"] else "",
            "last_seen": max(data["timestamps"]) if data["timestamps"] else "",
            "sample_inputs": data["sample_inputs"],
            "pattern_label": ", ".join(sorted(data["pattern_labels"])) or None,
            "is_candidate": data["count"] >= min_count,
        })

    # Sort by count descending
    results.sort(key=lambda x: x["count"], reverse=True)
    return results


def _get_route_description(intent: str) -> str:
    """Look up route description from routing.config.

    Config Over Code: descriptions live in config, used for proposals.
    Returns intent name if route not found.
    """
    import yaml
    try:
        config_path = get_config_dir() / "routing.config"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            route = data.get("routes", {}).get(intent, {})
            return route.get("description", intent)
    except Exception:
        pass
    return intent


def _get_proposal_dir():
    """Get the proposal directory path from config.

    Config Over Code: proposal_dir declared in routing.config flywheel section.
    """
    from engine.profile import get_profile_path
    config = _load_detection_config()
    propose_config = config.get("propose", {})
    proposal_dir = propose_config.get("proposal_dir", "queue/flywheel")
    return get_profile_path() / proposal_dir


def load_proposals() -> list[dict]:
    """Load existing proposals from the proposal directory.

    Returns list of proposal dicts with 'pattern_hash' and full YAML content.
    """
    import yaml
    proposal_dir = _get_proposal_dir()
    if not proposal_dir.exists():
        return []

    proposals = []
    for f in proposal_dir.glob("*.yaml"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            skill = data.get("skill", {})
            trigger = skill.get("trigger", {})
            proposals.append({
                "file": f.name,
                "pattern_hash": trigger.get("pattern_hash", f.stem),
                "name": skill.get("name", ""),
                "description": skill.get("description", ""),
                "data": data,
            })
        except Exception:
            continue
    return proposals


def propose_skills() -> list[dict]:
    """
    Flywheel Stage 3: PROPOSE.

    Reads detected patterns via detect_patterns(), generates
    structured YAML proposals for candidates without pending
    proposals.

    Every field is deterministic. No LLM. Tier 0.

    Returns list of newly created proposal dicts.
    """
    import yaml

    # Check if PROPOSE is enabled
    config = _load_detection_config()
    propose_config = config.get("propose", {})
    if not propose_config.get("enabled", True):
        return []

    # Get candidates from DETECT
    patterns = detect_patterns()
    candidates = [p for p in patterns if p.get("is_candidate")]

    if not candidates:
        return []

    # Load existing proposals to skip already-proposed patterns
    existing = load_proposals()
    existing_hashes = {p["pattern_hash"] for p in existing}

    # Ensure proposal directory exists
    proposal_dir = _get_proposal_dir()
    proposal_dir.mkdir(parents=True, exist_ok=True)

    new_proposals = []
    now = datetime.now(timezone.utc).isoformat()

    for candidate in candidates:
        ph = candidate["pattern_hash"]
        if ph in existing_hashes:
            continue  # Already proposed

        # Get the primary intent (first if multiple)
        intent = candidate["intent"].split(",")[0].strip()
        description = _get_route_description(intent)

        # Build proposal structure
        proposal = {
            "skill": {
                "name": intent,
                "description": description,
                "trigger": {
                    "pattern_hash": ph,
                    "pattern_label": candidate.get("pattern_label") or "",
                    "example_inputs": candidate.get("sample_inputs", []),
                },
                "response": {
                    "tier": 0,
                    "zone": "green",
                },
                "provenance": {
                    "occurrences": candidate["count"],
                    "first_seen": candidate.get("first_seen", ""),
                    "last_seen": candidate.get("last_seen", ""),
                    "proposed_at": now,
                    "proposed_by": "flywheel_stage_3",
                },
            }
        }

        # Write YAML file
        proposal_path = proposal_dir / f"{ph}.yaml"
        header = f"""# Proposed Skill: {intent}
# Flywheel Stage 3 (PROPOSE) — awaiting operator approval
# This file is a proposal. It changes nothing until approved.

"""
        with open(proposal_path, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.dump(proposal, f, default_flow_style=False, sort_keys=False)

        new_proposals.append({
            "pattern_hash": ph,
            "name": intent,
            "description": description,
            "file": proposal_path.name,
        })

    return new_proposals


def _load_single_proposal(pattern_hash: str) -> tuple[dict, str]:
    """Load a single proposal by pattern hash.

    Returns (proposal_dict, status) where status is one of:
      - "found": proposal exists in pending queue
      - "already_approved": proposal exists in approved/ directory
      - "not_found": proposal doesn't exist

    Config Over Code: reads from proposal_dir in routing.config.
    """
    import yaml
    proposal_dir = _get_proposal_dir()
    proposal_path = proposal_dir / f"{pattern_hash}.yaml"

    if proposal_path.exists():
        with open(proposal_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data, "found"

    # Check approved directory
    approved_dir = proposal_dir / "approved"
    approved_path = approved_dir / f"{pattern_hash}.yaml"
    if approved_path.exists():
        with open(approved_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data, "already_approved"

    return {}, "not_found"


def _get_route_metadata(intent: str) -> dict:
    """Look up full route metadata from routing.config.

    Returns dict with handler, handler_args, intent_type, zone, domain.
    Used by approve_skill() to populate cache entries.
    """
    import yaml
    try:
        config_path = get_config_dir() / "routing.config"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            route = data.get("routes", {}).get(intent, {})
            return {
                "handler": route.get("handler", intent),
                "handler_args": route.get("handler_args", {}),
                "intent_type": route.get("intent_type", "informational"),
                "zone": route.get("zone", "green"),
                "domain": route.get("domain", "system"),
            }
    except Exception:
        pass
    return {
        "handler": intent,
        "handler_args": {},
        "intent_type": "informational",
        "zone": "green",
        "domain": "system",
    }


def approve_skill(pattern_hash: str) -> dict:
    """
    Flywheel Stage 4: APPROVE.

    Reads proposal, writes example_inputs to pattern cache,
    archives proposal to approved/ directory.

    Yellow-zone: caller must have obtained operator confirmation
    before calling this function. The handler is a dumb pipe.
    Governance lives in the pipeline (Stage 4 Andon Gate).

    NOTE: This writes directly to pattern_cache.yaml, bypassing
    pipeline._write_to_pattern_cache(). That method gates on
    classification_source == "llm" (the Ratchet auto-cache path).
    Flywheel approval is a different write path with different
    semantics: the operator explicitly endorsed this pattern,
    so the source is "flywheel_approve", not "llm".
    Two write paths, same cache format, different provenance.

    Args:
        pattern_hash: The 12-char hash identifying the proposal

    Returns:
        dict with approval result:
        {
            "approved": True/False,
            "skill_name": str,
            "entries_written": int,
            "proposal_archived": True/False,
            "error": str or None
        }
    """
    import yaml
    import hashlib
    import shutil

    # Sanitize input: first token only, max 12 chars
    pattern_hash = pattern_hash.strip().split()[0][:12] if pattern_hash else ""

    if not pattern_hash:
        return {
            "approved": False,
            "skill_name": "",
            "entries_written": 0,
            "proposal_archived": False,
            "error": "No pattern hash provided",
        }

    # Load the proposal
    proposal, status = _load_single_proposal(pattern_hash)

    if status == "not_found":
        return {
            "approved": False,
            "skill_name": "",
            "entries_written": 0,
            "proposal_archived": False,
            "error": f"Proposal {pattern_hash} not found",
        }

    if status == "already_approved":
        skill_name = proposal.get("skill", {}).get("name", "unknown")
        return {
            "approved": False,
            "skill_name": skill_name,
            "entries_written": 0,
            "proposal_archived": False,
            "error": f"Proposal {pattern_hash} already approved",
        }

    # Extract skill metadata
    skill = proposal.get("skill", {})
    skill_name = skill.get("name", "unknown")
    trigger = skill.get("trigger", {})
    example_inputs = trigger.get("example_inputs", [])

    if not example_inputs:
        return {
            "approved": False,
            "skill_name": skill_name,
            "entries_written": 0,
            "proposal_archived": False,
            "error": "Proposal has no example inputs to cache",
        }

    # Get route metadata for cache entries
    route_meta = _get_route_metadata(skill_name)
    now = datetime.now(timezone.utc).isoformat()

    # Load existing cache
    from engine.profile import get_profile_path
    cache_path = get_profile_path() / "config" / "pattern_cache.yaml"
    try:
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = yaml.safe_load(f) or {}
        else:
            cache_data = {}
    except Exception:
        cache_data = {}

    if "cache" not in cache_data:
        cache_data["cache"] = {}

    # Write cache entries for each example input
    entries_written = 0
    for example in example_inputs:
        # Compute input_hash: sha256 of lowered/stripped input, first 16 hex chars
        normalized = example.lower().strip()
        input_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

        # Build cache entry — same format as Ratchet, different source
        cache_entry = {
            "intent": skill_name,
            "domain": route_meta["domain"],
            "zone": route_meta["zone"],
            "handler": route_meta["handler"],
            "handler_args": route_meta["handler_args"],
            "intent_type": route_meta["intent_type"],
            "confirmed_count": 1,
            "last_confirmed": now,
            "original_input": example,
            "confidence": 0.95,
            "pattern_label": trigger.get("pattern_label", ""),
            "source": "flywheel_approve",
            "proposal_hash": pattern_hash,
        }

        cache_data["cache"][input_hash] = cache_entry
        entries_written += 1

    # Write updated cache
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            yaml.dump(cache_data, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        return {
            "approved": False,
            "skill_name": skill_name,
            "entries_written": 0,
            "proposal_archived": False,
            "error": f"Failed to write cache: {e}",
        }

    # Archive the proposal
    proposal_dir = _get_proposal_dir()
    approved_dir = proposal_dir / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    proposal_path = proposal_dir / f"{pattern_hash}.yaml"
    archived_path = approved_dir / f"{pattern_hash}.yaml"

    try:
        shutil.move(str(proposal_path), str(archived_path))
        proposal_archived = True
    except Exception:
        proposal_archived = False

    # Invalidate router's in-memory cache so it picks up new entries
    try:
        from engine.cognitive_router import get_router
        get_router().load_cache()
    except Exception:
        pass  # Non-fatal — router will reload on next request

    return {
        "approved": True,
        "skill_name": skill_name,
        "entries_written": entries_written,
        "proposal_archived": proposal_archived,
        "error": None,
    }
