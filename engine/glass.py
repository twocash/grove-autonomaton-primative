"""
glass.py - Glass Pipeline Display

Renders pipeline stage annotations to terminal for architecture-literate
audiences. Reads telemetry events only — no PipelineContext passthrough.
This is presentation, not instrumentation.

The glass pipeline is enabled via profile.yaml display flags or --glass CLI.
"""

import sys
import os
from typing import Optional


class _Colors:
    """ANSI color codes (matches autonomaton.py and ux.py patterns)."""
    ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"
    RESET = "\033[0m" if ENABLED else ""
    BOLD = "\033[1m" if ENABLED else ""
    DIM = "\033[2m" if ENABLED else ""
    GREEN = "\033[92m" if ENABLED else ""
    YELLOW = "\033[93m" if ENABLED else ""
    RED = "\033[91m" if ENABLED else ""
    CYAN = "\033[96m" if ENABLED else ""
    WHITE = "\033[97m" if ENABLED else ""
    MAGENTA = "\033[95m" if ENABLED else ""


_c = _Colors

# Session-scoped Ratchet announcement tracking
_ratchet_announced = False


def reset_ratchet_announcement() -> None:
    """Reset Ratchet announcement flag (for testing or new sessions)."""
    global _ratchet_announced
    _ratchet_announced = False


def _get_zone_color(zone: str) -> str:
    """Get ANSI color for a zone name."""
    if zone == "green":
        return _c.GREEN
    elif zone == "yellow":
        return _c.YELLOW
    elif zone == "red":
        return _c.RED
    return _c.WHITE


# =========================================================================
# Telemetry-Based Glass (Architecturally Correct)
# =========================================================================

def read_pipeline_events(pipeline_id: str) -> list[dict]:
    """Read telemetry events for a specific pipeline traversal.

    Returns events ordered by stage for glass rendering.
    The pipeline_id is the Stage 1 event id.
    """
    from engine.telemetry import read_recent_events

    events = read_recent_events(limit=50)

    pipeline_events = []
    for event in events:
        if event.get("id") == pipeline_id:
            pipeline_events.append(event)
        elif event.get("inferred", {}).get("pipeline_id") == pipeline_id:
            pipeline_events.append(event)

    # Sort by stage order
    stage_order = {"telemetry": 1, "recognition": 2, "compilation": 3,
                   "approval": 4, "approval_jidoka": 4,
                   "approval_kaizen": 4, "execution": 5}
    pipeline_events.sort(
        key=lambda e: stage_order.get(
            e.get("inferred", {}).get("stage", ""), 99
        )
    )
    return pipeline_events


def _render_stage_from_event(lines: list, event: dict,
                              stage: str, level: str,
                              reclassified_intent: str = None) -> None:
    """Render one stage line from a telemetry event."""
    inf = event.get("inferred", {})

    if stage == "telemetry":
        eid = event.get("id", "unknown")[:8]
        src = event.get("source", "unknown")
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}1{_c.RESET} Telemetry   "
            f"{_c.DIM}id:{_c.RESET}{eid} "
            f"{_c.DIM}src:{_c.RESET}{src}")

    elif stage == "recognition":
        intent = event.get("intent", "unknown")
        tier = event.get("tier", 0)
        conf = event.get("confidence", 0.0)
        method = inf.get("method", "unknown")
        is_cache = method == "cache"
        cost = "$0.00" if tier < 2 or is_cache else "~$0.003"
        cache_marker = f" {_c.GREEN}✓{_c.RESET}" if is_cache else ""
        # V-010: Show reclassification arrow if Kaizen changed the intent
        if reclassified_intent and reclassified_intent != intent:
            intent_display = f"{intent} {_c.DIM}→{_c.RESET} {reclassified_intent}"
        else:
            intent_display = intent
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}2{_c.RESET} Recognition "
            f"{_c.DIM}intent:{_c.RESET}{intent_display} "
            f"{_c.DIM}T{tier}{_c.RESET} {method}{cache_marker} "
            f"{_c.DIM}{cost}{_c.RESET}")
        if level in ("medium", "full") and conf > 0:
            lines.append(
                f"  {_c.DIM}│{_c.RESET}             "
                f"{_c.DIM}confidence:{_c.RESET} {conf:.0%}")

    elif stage == "compilation":
        skipped = inf.get("skipped", False)
        chunks = inf.get("dock_chunks", 0)
        comp = "Skipped — conversational" if skipped else f"Dock: {chunks} chunk(s)"
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}3{_c.RESET} Compilation {comp}")

    elif stage in ("approval", "approval_jidoka", "approval_kaizen"):
        zone = event.get("zone_context", "green")
        feedback = event.get("human_feedback", "")
        zc = _get_zone_color(zone)
        # Read label from pipeline (set by _log_approval_trace)
        label = inf.get("label")
        if feedback == "rejected":
            app = "CANCELLED"
        elif label:
            app = label
        else:
            # Fallback for older events without label
            app = f"{zone.upper()} auto-approve" if zone == "green" else zone.upper()
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}4{_c.RESET} Approval    "
            f"{zc}{app}{_c.RESET}")

    elif stage == "execution":
        handler = inf.get("handler", "passthrough")
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}5{_c.RESET} Execution   "
            f"{_c.DIM}handler:{_c.RESET}{handler} "
            f"{_c.DIM}[executed]{_c.RESET}")


def _format_ratchet_from_event(event: dict) -> str:
    """Format Ratchet announcement from a recognition event."""
    global _ratchet_announced
    if _ratchet_announced:
        return ""
    _ratchet_announced = True
    return (
        f"  {_c.MAGENTA}{_c.BOLD}THE RATCHET:{_c.RESET} "
        f"{_c.DIM}Classified by LLM last time → cache this time.{_c.RESET}\n"
        f"     {_c.DIM}Tier 0, $0.00. The system got cheaper because you used it.{_c.RESET}"
    )


def display_glass_from_telemetry(pipeline_id: str,
                                 level: str = "medium") -> Optional[str]:
    """Render glass pipeline from telemetry events.

    This is the architecturally correct glass renderer.
    It reads from the same telemetry stream as Cortex, Ratchet,
    and Skill Flywheel. No PipelineContext needed.
    """
    events = read_pipeline_events(pipeline_id)
    if not events:
        return None

    # V-010: Check if Kaizen reclassified the intent
    reclassified_intent = None
    for event in events:
        inf = event.get("inferred", {})
        if inf.get("stage") == "approval_kaizen" and inf.get("resolved_intent"):
            reclassified_intent = inf["resolved_intent"]
            break

    lines = []
    width = 58
    border = f"{_c.DIM}{'─' * width}{_c.RESET}"
    lines.append(f"  {border}")
    lines.append(f"  {_c.DIM}│{_c.RESET} {_c.CYAN}GLASS PIPELINE{_c.RESET}")
    lines.append(f"  {border}")

    for event in events:
        stage = event.get("inferred", {}).get("stage", "")
        _render_stage_from_event(lines, event, stage, level, reclassified_intent)

    lines.append(f"  {border}")
    print("\n".join(lines))

    # Check for ratchet announcement
    for event in events:
        if event.get("inferred", {}).get("method") == "cache":
            return _format_ratchet_from_event(event)
    return None


def display_ratchet_announcement(announcement: str) -> None:
    """Display the Ratchet announcement below the glass box."""
    if announcement:
        print(f"\n{announcement}\n")


def display_tip(tip_text: str) -> None:
    """Display a contextual tip line."""
    if tip_text:
        print(f"\n  {_c.DIM}💡 {tip_text}{_c.RESET}")


# =========================================================================
# Tip Engine (event-based, reads from ux.yaml)
# =========================================================================

class TipEngine:
    """Event-based contextual tip system.

    Loads tip definitions from config/ux.yaml (tips.events section).
    Matches pipeline events to tip triggers.
    Returns at most one tip per interaction, highest priority wins.
    """

    def __init__(self):
        self.tips = {}  # event_name -> {priority, message}
        self.shown_events = set()
        self._loaded = False

    def load(self) -> None:
        """Load ux.yaml from active profile."""
        import yaml
        from engine.profile import get_config_dir

        ux_path = get_config_dir() / "ux.yaml"
        if not ux_path.exists():
            self._loaded = True
            return

        try:
            with open(ux_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            tips_config = data.get("tips", {})
            if tips_config.get("enabled", True):
                self.tips = tips_config.get("events", {})
        except Exception:
            self.tips = {}
        self._loaded = True

    def evaluate(self, pipeline_data: dict) -> Optional[str]:
        """Evaluate tip triggers against pipeline events.

        Args:
            pipeline_data: Dict with events list from pipeline context

        Returns:
            Tip text string or None.
        """
        if not self._loaded:
            self.load()

        if not self.tips:
            return None

        # Get events from pipeline data
        events = pipeline_data.get("events", [])
        if not events:
            return None

        # Find matching tips, sorted by priority (lower = higher priority)
        candidates = []
        for event_name in events:
            if event_name in self.shown_events:
                continue
            if event_name in self.tips:
                tip = self.tips[event_name]
                candidates.append((
                    tip.get("priority", 99),
                    event_name,
                    tip.get("message", "")
                ))

        if not candidates:
            return None

        # Sort by priority and return the highest priority (lowest number)
        candidates.sort(key=lambda x: x[0])
        _, event_name, message = candidates[0]
        self.shown_events.add(event_name)
        return message
