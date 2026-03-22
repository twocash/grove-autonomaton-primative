"""
flywheel.py - Skill Flywheel Detection (Stage 2)

White Paper Part III S3: "Same intent pattern 3+ times in 14 days
-> surface as potential skill."

The Flywheel reads telemetry completion traces, groups by pattern_hash,
and surfaces recurring patterns as skill candidates. This is the
structural prerequisite for "authors its own evolution."

Stages implemented:
  1. OBSERVE - feed-first telemetry (telemetry.py)
  2. DETECT  - this module
  3-6: Future sprints
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
