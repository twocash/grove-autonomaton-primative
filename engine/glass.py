"""
glass.py - Glass Pipeline Display

Renders pipeline stage annotations to terminal for architecture-literate
audiences. Pure observer — reads PipelineContext metadata only. Does not
modify or probe the pipeline. This is presentation, not instrumentation.

The glass pipeline is enabled via profile.yaml display flags or --glass CLI.
"""

import sys
import os
from typing import Optional

from engine.pipeline import PipelineContext


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


def get_ratchet_announcement(context: PipelineContext) -> Optional[str]:
    """
    Check if this is the first cache hit of the session and return announcement.

    Returns the Ratchet announcement string on first cache hit, None otherwise.
    """
    global _ratchet_announced

    if _ratchet_announced:
        return None

    routing = context.entities.get("routing", {})
    llm_metadata = routing.get("llm_metadata", {})

    if llm_metadata.get("source") == "pattern_cache":
        _ratchet_announced = True
        return (
            f"  {_c.MAGENTA}{_c.BOLD}THE RATCHET:{_c.RESET} "
            f"{_c.DIM}Classified by LLM last time → cache this time.{_c.RESET}\n"
            f"     {_c.DIM}Tier 0, $0.00. The system got cheaper because you used it.{_c.RESET}"
        )

    return None


def _extract_glass_data(context: PipelineContext) -> dict:
    """Extract all data needed for glass display from PipelineContext."""

    # Stage 1: Telemetry
    telemetry_event = context.telemetry_event or {}
    event_id = telemetry_event.get("id", "unknown")[:8]
    source = context.source

    # Stage 2: Recognition
    routing = context.entities.get("routing", {})
    intent_type = routing.get("intent_type", "unknown")
    llm_metadata = routing.get("llm_metadata", {})

    # Use flat telemetry fields when available (Purity v2)
    tier = telemetry_event.get("tier", routing.get("tier", 0))
    confidence = telemetry_event.get("confidence", routing.get("confidence", 0.0))
    cost_usd = telemetry_event.get("cost_usd")

    # Determine classification method
    if llm_metadata.get("source") == "pattern_cache":
        method = "cache HIT"
        cost_str = "$0.00"
        is_cache_hit = True
    elif tier >= 2 and not llm_metadata.get("forced_route"):
        method = "LLM"
        cost_str = f"${cost_usd:.4f}" if cost_usd else "~$0.003"
        is_cache_hit = False
    elif llm_metadata.get("forced_route"):
        method = "forced"
        cost_str = "$0.00"
        is_cache_hit = False
    else:
        method = "keyword"
        cost_str = "$0.00"
        is_cache_hit = False

    # Stage 3: Compilation
    if intent_type == "conversational":
        compilation_str = "Skipped — conversational intent"
    elif not context.dock_context or (context.dock_context and not context.dock_context[0]):
        compilation_str = "Dock query: [empty — no context loaded]"
    else:
        compilation_str = f"Dock query: {len(context.dock_context)} chunk(s)"

    # Stage 4: Approval
    zone = context.zone or "green"
    if not context.approved and context.result and context.result.get("status") == "cancelled":
        approval_str = "CANCELLED"
    elif zone == "green":
        if not routing.get("action_required", True):
            approval_str = "GREEN auto-approve | no action required"
        else:
            approval_str = "GREEN auto-approve"
    elif zone == "yellow":
        approval_str = "YELLOW — requires confirmation"
    elif zone == "red":
        approval_str = "RED — explicit approval required"
    else:
        approval_str = f"{zone.upper()}"

    # Stage 5: Execution
    handler = routing.get("handler", "passthrough")

    return {
        "event_id": event_id,
        "source": source,
        "intent": context.intent,
        "tier": tier,
        "confidence": confidence,
        "method": method,
        "cost_str": cost_str,
        "is_cache_hit": is_cache_hit,
        "compilation": compilation_str,
        "zone": zone,
        "approval": approval_str,
        "handler": handler,
        "executed": context.executed,
    }


def _get_zone_color(zone: str) -> str:
    """Get ANSI color for a zone name."""
    if zone == "green":
        return _c.GREEN
    elif zone == "yellow":
        return _c.YELLOW
    elif zone == "red":
        return _c.RED
    return _c.WHITE


def format_glass_box(data: dict, level: str = "medium") -> str:
    """
    Build the bordered glass pipeline box.

    Args:
        data: Extracted glass data from _extract_glass_data()
        level: Display level (minimal, medium, full)

    Returns:
        Formatted box string with ANSI colors
    """
    lines = []
    width = 58
    border = f"{_c.DIM}{'─' * width}{_c.RESET}"

    lines.append(f"  {border}")
    lines.append(f"  {_c.DIM}│{_c.RESET} {_c.CYAN}GLASS PIPELINE{_c.RESET}")
    lines.append(f"  {border}")

    # Stage 1: Telemetry
    lines.append(
        f"  {_c.DIM}│{_c.RESET} {_c.CYAN}1{_c.RESET} Telemetry   "
        f"{_c.DIM}id:{_c.RESET}{data['event_id']} "
        f"{_c.DIM}src:{_c.RESET}{data['source']}"
    )

    # Stage 2: Recognition
    cache_marker = f" {_c.GREEN}✓{_c.RESET}" if data['is_cache_hit'] else ""
    lines.append(
        f"  {_c.DIM}│{_c.RESET} {_c.CYAN}2{_c.RESET} Recognition "
        f"{_c.DIM}intent:{_c.RESET}{data['intent']} "
        f"{_c.DIM}T{data['tier']}{_c.RESET} {data['method']}{cache_marker} "
        f"{_c.DIM}{data['cost_str']}{_c.RESET}"
    )

    if level in ("medium", "full") and data['confidence'] > 0:
        lines.append(
            f"  {_c.DIM}│{_c.RESET}             "
            f"{_c.DIM}confidence:{_c.RESET} {data['confidence']:.0%}"
        )

    # Stage 3: Compilation
    lines.append(
        f"  {_c.DIM}│{_c.RESET} {_c.CYAN}3{_c.RESET} Compilation "
        f"{data['compilation']}"
    )

    # Stage 4: Approval
    zone_color = _get_zone_color(data['zone'])
    lines.append(
        f"  {_c.DIM}│{_c.RESET} {_c.CYAN}4{_c.RESET} Approval    "
        f"{zone_color}{data['approval']}{_c.RESET}"
    )

    # Stage 5: Execution
    exec_status = "executed" if data['executed'] else "skipped"
    lines.append(
        f"  {_c.DIM}│{_c.RESET} {_c.CYAN}5{_c.RESET} Execution   "
        f"{_c.DIM}handler:{_c.RESET}{data['handler']} "
        f"{_c.DIM}[{exec_status}]{_c.RESET}"
    )

    lines.append(f"  {border}")

    return "\n".join(lines)


def display_glass_pipeline(context: PipelineContext, level: str = "medium") -> Optional[str]:
    """
    Display the glass pipeline box and return any Ratchet announcement.

    Args:
        context: PipelineContext from run_pipeline()
        level: Display level (minimal, medium, full)

    Returns:
        Ratchet announcement string if first cache hit, None otherwise
    """
    data = _extract_glass_data(context)
    box = format_glass_box(data, level)
    print(box)

    return get_ratchet_announcement(context)


def display_ratchet_announcement(announcement: str) -> None:
    """Display the Ratchet announcement below the glass box."""
    if announcement:
        print(f"\n{announcement}\n")


def display_tip(tip_text: str) -> None:
    """Display a contextual tip line."""
    if tip_text:
        print(f"\n  {_c.DIM}💡 {tip_text}{_c.RESET}")


# =========================================================================
# Tip Engine (moved to glass.py to keep presentation concerns together)
# =========================================================================

class TipEngine:
    """Declarative contextual tip system.

    Loads tip definitions from config/tips.yaml.
    Tracks shown tips in-memory (session-scoped, not persisted).
    Evaluates triggers against PipelineContext after each run.
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

    def evaluate(self, context: PipelineContext) -> Optional[str]:
        """Evaluate tip triggers against PipelineContext.

        Returns tip text string or None.
        """
        if not self._loaded:
            self.load()

        routing = context.entities.get("routing", {})
        llm_meta = routing.get("llm_metadata", {})

        for tip in self.tips:
            tip_id = tip.get("id", "")
            if tip_id in self.shown_ids:
                continue

            trigger = tip.get("trigger", {})
            if self._matches(trigger, context, routing, llm_meta):
                self.shown_ids.add(tip_id)
                return tip.get("text", "")

        return None

    def _matches(self, trigger: dict, context: PipelineContext, routing: dict, llm_meta: dict) -> bool:
        """Check if all trigger conditions are met."""
        if "after_intent" in trigger:
            if context.intent != trigger["after_intent"]:
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
            if context.zone != trigger["after_zone"]:
                return False

        return True
