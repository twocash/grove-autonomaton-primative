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
                   "approval": 4, "approval_jidoka": 4, "execution": 5}
    pipeline_events.sort(
        key=lambda e: stage_order.get(
            e.get("inferred", {}).get("stage", ""), 99
        )
    )
    return pipeline_events


def _render_stage_from_event(lines: list, event: dict,
                              stage: str, level: str) -> None:
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
        lines.append(
            f"  {_c.DIM}│{_c.RESET} {_c.CYAN}2{_c.RESET} Recognition "
            f"{_c.DIM}intent:{_c.RESET}{intent} "
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

    elif stage == "approval":
        zone = event.get("zone_context", "green")
        feedback = event.get("human_feedback", "")
        zc = _get_zone_color(zone)
        if feedback == "rejected":
            app = "CANCELLED"
        elif zone == "green":
            app = "GREEN auto-approve"
        elif zone == "yellow":
            app = "YELLOW — confirmed"
        elif zone == "red":
            app = "RED — explicit approval"
        else:
            app = zone.upper()
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

    lines = []
    width = 58
    border = f"{_c.DIM}{'─' * width}{_c.RESET}"
    lines.append(f"  {border}")
    lines.append(f"  {_c.DIM}│{_c.RESET} {_c.CYAN}GLASS PIPELINE{_c.RESET}")
    lines.append(f"  {border}")

    for event in events:
        stage = event.get("inferred", {}).get("stage", "")
        _render_stage_from_event(lines, event, stage, level)

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
# Tip Engine (refactored to take dict, not PipelineContext)
# =========================================================================

class TipEngine:
    """Declarative contextual tip system.

    Loads tip definitions from config/tips.yaml.
    Tracks shown tips in-memory (session-scoped, not persisted).
    Evaluates triggers against pipeline data after each run.
    Returns at most one tip per interaction.
    """

    def __init__(self):
        self.tips = []
        self.shown_ids = set()
        self._loaded = False

    def load(self) -> None:
        """Load tips.yaml from active profile."""
        import yaml
        from engine.profile import get_config_dir

        tips_path = get_config_dir() / "tips.yaml"
        if not tips_path.exists():
            self._loaded = True
            return

        try:
            with open(tips_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.tips = data.get("tips", [])
        except Exception:
            self.tips = []
        self._loaded = True

    def evaluate(self, pipeline_data) -> Optional[str]:
        """Evaluate tip triggers against pipeline data.

        Args:
            pipeline_data: Dict or PipelineContext with intent, zone, entities

        Returns:
            Tip text string or None.
        """
        if not self._loaded:
            self.load()

        # Handle both dict and PipelineContext for backwards compatibility
        if hasattr(pipeline_data, 'entities'):
            # PipelineContext object
            routing = pipeline_data.entities.get("routing", {})
            intent = pipeline_data.intent or ""
            zone = pipeline_data.zone or "green"
        else:
            # Dict
            routing = pipeline_data.get("entities", {}).get("routing", {})
            intent = pipeline_data.get("intent", "")
            zone = pipeline_data.get("zone", "green")

        llm_meta = routing.get("llm_metadata", {})

        for tip in self.tips:
            tip_id = tip.get("id", "")
            if tip_id in self.shown_ids:
                continue

            trigger = tip.get("trigger", {})
            if self._matches(trigger, intent, zone, routing, llm_meta):
                self.shown_ids.add(tip_id)
                return tip.get("text", "")

        return None

    def _matches(self, trigger: dict, intent: str, zone: str,
                 routing: dict, llm_meta: dict) -> bool:
        """Check if all trigger conditions are met."""
        if "after_intent" in trigger:
            if intent != trigger["after_intent"]:
                return False

        if "after_tier" in trigger:
            tier = routing.get("tier", 0)
            if tier != trigger["after_tier"]:
                return False

        if "after_cache_hit" in trigger:
            is_cache_hit = llm_meta.get("source") == "pattern_cache"
            if is_cache_hit != trigger["after_cache_hit"]:
                return False

        if "after_zone" in trigger:
            if zone != trigger["after_zone"]:
                return False

        return True
