#!/usr/bin/env python3
"""
autonomaton.py - The Invariant Engine Entry Point

The Autonomaton REPL - a domain-agnostic agentic system.
ALL user input passes through the Invariant Pipeline.
No direct function calls - everything is routed through the 5-stage pipeline.

Usage:
    python autonomaton.py                          # Uses default profile (reference)
    python autonomaton.py --profile reference      # Explicit profile selection
    python autonomaton.py --verbose                # Show dock context in responses
    python autonomaton.py --list-profiles          # List available profiles
"""

import sys
import os
import argparse
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Profile must be set BEFORE importing engine modules
from engine.profile import set_profile, list_available_profiles, get_profile


# =========================================================================
# Terminal Colors (ANSI escape codes)
# =========================================================================

class Colors:
    """ANSI color codes for terminal output."""
    # Check if colors are supported
    ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"

    # Colors
    RESET = "\033[0m" if ENABLED else ""
    BOLD = "\033[1m" if ENABLED else ""
    DIM = "\033[2m" if ENABLED else ""

    # Zone colors
    GREEN = "\033[92m" if ENABLED else ""
    YELLOW = "\033[93m" if ENABLED else ""
    RED = "\033[91m" if ENABLED else ""
    CYAN = "\033[96m" if ENABLED else ""
    WHITE = "\033[97m" if ENABLED else ""
    BLUE = "\033[94m" if ENABLED else ""
    MAGENTA = "\033[95m" if ENABLED else ""


def zone_color(zone: str) -> str:
    """Get the color for a zone."""
    zone_map = {
        "green": Colors.GREEN,
        "yellow": Colors.YELLOW,
        "red": Colors.RED
    }
    return zone_map.get(zone, Colors.WHITE)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="The Autonomaton - Domain-Agnostic Agentic System"
    )
    parser.add_argument(
        "--profile", "-p",
        default="reference",
        help="Profile to load (default: reference)"
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles and exit"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show dock context in responses"
    )
    parser.add_argument(
        "--skip-welcome",
        action="store_true",
        help="Skip the welcome card briefing at startup"
    )
    parser.add_argument(
        "--glass",
        action="store_true",
        help="Enable glass pipeline display for any profile"
    )
    return parser.parse_args()


def _load_profile_handlers():
    """
    Load domain handlers from the active profile's handlers.py.

    V-012: Profiles can provide handlers.py with a register(dispatcher) function.
    This keeps domain logic in profiles, not engine code.
    """
    import importlib.util
    from engine.profile import get_profile_path
    from engine.dispatcher import get_dispatcher

    handlers_path = get_profile_path() / "handlers.py"
    if not handlers_path.exists():
        return  # No profile handlers - using engine-core only

    spec = importlib.util.spec_from_file_location("profile_handlers", handlers_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "register"):
        dispatcher = get_dispatcher()
        module.register(dispatcher)


def _build_tier_display() -> str:
    """
    V-016: Build tier display string from models.yaml for banner.

    Reads the tier-to-model mapping and constructs a human-readable string.
    The watchman reports what's available — no Andon, no prompt.
    """
    import yaml
    from engine.profile import get_config_dir

    short_names = {
        "claude-haiku-4-5-20251001": "Haiku",
        "claude-sonnet-4-6": "Sonnet",
        "claude-opus-4-6": "Opus",
    }

    models_path = get_config_dir() / "models.yaml"
    if not models_path.exists():
        return "T0 cache · T1 Haiku · T2 Sonnet · T3 Opus"  # Fallback

    try:
        with open(models_path, encoding="utf-8") as f:
            models = yaml.safe_load(f) or {}
    except Exception:
        return "T0 cache · T1 Haiku · T2 Sonnet · T3 Opus"  # Fallback

    tier_map = models.get("tiers", {})
    if not tier_map:
        return "T0 cache · T1 Haiku · T2 Sonnet · T3 Opus"  # Fallback

    parts = ["T0 cache"]
    for tier_num in sorted(tier_map.keys()):
        model_id = tier_map[tier_num]
        short = short_names.get(model_id, model_id.split("-")[1].title() if "-" in model_id else model_id)
        parts.append(f"T{tier_num} {short}")

    return " · ".join(parts)


def _get_cortex_pending() -> int:
    """
    V-016: Count pending Kaizen items for banner display.

    The watchman reports the queue status — Jidoka awareness,
    not Andon mechanism.
    """
    from engine.profile import get_config_dir
    queue_dir = get_config_dir() / "queue"
    if not queue_dir.exists():
        return 0
    # Count YAML files in queue directory (Kaizen proposals)
    return len(list(queue_dir.glob("*.yaml")))


def _run_startup_mode_selection() -> bool:
    """
    V-015: Startup Kaizen for compute mode selection.

    Reads startup.yaml from the profile's config directory.
    If mode_selection.enabled is true, presents mode options via ask_jidoka().
    Returns True if Learning Mode is selected (enrichment enabled).

    This is UX infrastructure, not a pipeline traversal.
    White paper Part IV, Stage 01: "The system comes to the human."
    """
    import yaml
    from engine.profile import get_config_dir
    from engine.ux import ask_jidoka
    from engine.telemetry import log_event

    startup_path = get_config_dir() / "startup.yaml"
    if not startup_path.exists():
        return False  # No startup config — default to Free Mode

    try:
        with open(startup_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception:
        return False  # Config error — default to Free Mode

    startup = config.get("startup", {})
    mode_selection = startup.get("mode_selection", {})

    if not mode_selection.get("enabled", False):
        return False  # Mode selection disabled — default to Free Mode

    # Build options dict for ask_jidoka
    options_config = mode_selection.get("options", {})
    options = {k: v.get("label", k) for k, v in options_config.items()}

    if not options:
        return False  # No options configured

    # TPS framing
    jidoka_msg = startup.get("jidoka", {}).get("message", "The system has options available.")
    andon_msg = startup.get("andon", {}).get("message", "Choose before we begin.")

    # Build diagnostic for three-beat display
    diagnostic = {
        "summary": jidoka_msg,
        "confidence": 1.0,
        "cost": 0.00,
    }

    c = Colors
    print()
    print(f"  {c.CYAN}▰ JIDOKA{c.RESET} {'━' * 50}")
    print(f"  {jidoka_msg}")
    print()
    print(f"  {c.YELLOW}▰ ANDON{c.RESET} {'━' * 51}")
    print(f"  {andon_msg}")
    print()

    # Present choice
    choice = ask_jidoka(
        context_message=mode_selection.get("prompt", "Choose your mode:"),
        options=options
    )

    # Determine if Learning Mode was selected
    selected = options_config.get(choice, {})
    sets = selected.get("sets", {})
    enrichment_enabled = sets.get("router.enrichment.enabled", False)

    # Log the mode selection to telemetry (not a pipeline traversal)
    log_event(
        source="startup_mode_selection",
        raw_transcript=f"Mode selected: {selected.get('label', choice)}",
        zone_context="green",
        inferred={"mode": "learning" if enrichment_enabled else "free"}
    )

    return enrichment_enabled


def print_banner(
    profile: str,
    dock_info: str,
    glass_enabled: bool = False,
    cortex_pending: int = 0,
    compute_mode: str = "Free Mode (LLM on-demand with consent)",
    tier_info: str = ""
):
    """
    V-016: Display startup banner with full watchman status report.

    The watchman (Jidoka) reports system readiness: tiers available,
    dock loaded, Glass active, compute posture. No Andon, no prompt.
    Sovereignty starts at boot — the system arrives ready.
    """
    c = Colors
    print()
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")
    print(f"{c.BOLD}{c.WHITE}  THE AUTONOMATON{c.RESET}")
    print(f"{c.DIM}  Profile: {c.CYAN}{profile}{c.RESET}")
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")
    print(f"  {c.DIM}{dock_info}{c.RESET}")
    print(f"  {c.DIM}Cortex: {cortex_pending} pending Kaizen item(s){c.RESET}")
    if glass_enabled:
        print(f"  {c.MAGENTA}Glass Pipeline: ACTIVE{c.RESET}")
    print(f"  {c.DIM}Compute: {c.CYAN}{compute_mode}{c.RESET}")
    if tier_info:
        print(f"  {c.DIM}Tiers: {tier_info}{c.RESET}")
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")

    # Reference profile intro block
    if profile == "reference":
        print()
        print(f"  {c.DIM}This is the naked engine. No domain. No context. No skills.{c.RESET}")
        print(f"  {c.DIM}Every pipeline stage will announce itself as it runs.{c.RESET}")
        print(f"  {c.DIM}Type anything to see the architecture in motion.{c.RESET}")

    print()


def display_result(context, verbose: bool) -> None:
    """
    Display pipeline result based on dispatch data type.

    Handles type-specific formatting for different handler outputs.
    """
    c = Colors
    event_id = context.telemetry_event.get('id', 'unknown')[:8]
    zone = context.zone or "green"
    data = context.result.get("data", {})
    data_type = data.get("type") if isinstance(data, dict) else None

    # Verbose dock context
    if verbose and context.dock_context:
        print(f"\n  {c.CYAN}[DOCK CONTEXT]{c.RESET}")
        dock_text = context.dock_context[0] if context.dock_context else ""
        lines = dock_text.split('\n')
        for line in lines[:5]:
            if line.strip():
                print(f"  {c.DIM}{line.strip()}{c.RESET}")
        print()

    # Type-specific display
    if data_type == "dock_status":
        print(f"\n  {c.GREEN}[DOCK STATUS]{c.RESET}")
        print(f"  {c.DIM}Chunks:{c.RESET} {data.get('chunks', 0)}")
        print(f"  {c.DIM}Sources:{c.RESET} {', '.join(data.get('sources', []))}\n")

    elif data_type == "queue_status":
        print(f"\n  {c.MAGENTA}[KAIZEN QUEUE]{c.RESET}")
        items = data.get("items", [])
        if items:
            for item in items:
                print(f"  {c.DIM}-{c.RESET} [{c.CYAN}{item.get('trigger', '?')}{c.RESET}] {item.get('proposal', '?')}...")
        else:
            print(f"  {c.DIM}No pending items.{c.RESET}")
        print()

    elif data_type == "skills_list":
        print(f"\n  {c.BLUE}[DEPLOYED SKILLS]{c.RESET}")
        skills = data.get("skills", [])
        if skills:
            for skill in skills:
                status = "configured" if skill.get("has_config") else "incomplete"
                status_color = c.GREEN if skill.get("has_config") else c.YELLOW
                print(f"    {c.DIM}-{c.RESET} {c.WHITE}{skill['name']}{c.RESET} ({status_color}{status}{c.RESET})")
        else:
            print(f"    {c.DIM}No skills deployed yet.{c.RESET}")
        print()

    elif data_type == "content_compilation":
        draft_count = data.get("draft_count", 0)
        if draft_count > 0:
            print(f"\n  {c.YELLOW}[CONTENT ENGINE]{c.RESET} {draft_count} draft(s) compiled")
            print(f"  {c.DIM}Approval was handled during pipeline execution.{c.RESET}\n")
        else:
            print(f"\n  {c.YELLOW}[CONTENT ENGINE]{c.RESET} {c.DIM}No content seeds found{c.RESET}\n")

    elif data_type == "pit_crew_build":
        # Skill build result (description provided inline per V6 compliance)
        result = data.get("result", {})
        if result.get("status") == "deployed":
            print(f"\n  {c.GREEN}[PIT CREW]{c.RESET} Skill deployed successfully!")
            print(f"  {c.DIM}Skill:{c.RESET} {data.get('skill_name')}")
            print(f"  {c.DIM}Description:{c.RESET} {data.get('description')}")
            if result.get("files"):
                print(f"  {c.DIM}Files created:{c.RESET}")
                for f in result["files"]:
                    print(f"    {c.DIM}-{c.RESET} {Path(f).name}")
            print()
        elif result.get("status") == "rejected":
            print(f"\n  {c.YELLOW}[PIT CREW]{c.RESET} {result.get('message')}\n")
        else:
            print(f"\n  {c.RED}[PIT CREW]{c.RESET} {context.result.get('message')}\n")

    elif data_type == "pit_crew_usage":
        # Usage instructions (missing name or description)
        print(f"\n  {c.RED}[PIT CREW]{c.RESET} {context.result.get('message')}\n")

    elif data_type == "skill_execution":
        # Skill execution results - show the actual LLM output
        response = data.get("response", "")
        if response:
            print(f"  {c.WHITE}{response}{c.RESET}")
        else:
            skill_name = data.get("skill_name", "unknown")
            print(f"  {c.YELLOW}Skill '{skill_name}' produced no output.{c.RESET}")

    else:
        # Generic display with zone coloring
        zc = zone_color(zone)
        if context.executed:
            print(f"  {c.DIM}[LOGGED]{c.RESET} Event ID: {c.DIM}{event_id}...{c.RESET}")
            print(f"  {zc}[{zone.upper()}]{c.RESET} {context.result.get('message', 'Complete')}\n")
        else:
            print(f"  {c.DIM}[LOGGED]{c.RESET} Event ID: {c.DIM}{event_id}...{c.RESET}")
            print(f"  {c.YELLOW}[CANCELLED]{c.RESET} {context.result.get('message', 'Cancelled')}\n")


def main():
    """
    Main REPL loop.

    CRITICAL: Every user input goes through run_pipeline().
    No direct function calls for commands.
    """
    args = parse_args()

    # Handle --list-profiles
    if args.list_profiles:
        profiles = list_available_profiles()
        print("\nAvailable profiles:")
        for p in profiles:
            marker = " (default)" if p == "reference" else ""
            print(f"  - {p}{marker}")
        print()
        return

    # Set the active profile BEFORE importing engine modules
    set_profile(args.profile)

    # Load profile-specific handlers (V-012: Domain handlers in profiles/)
    _load_profile_handlers()

    # Now import engine modules (they will use the active profile)
    from engine.pipeline import run_pipeline
    from engine.dock import get_dock

    # Load profile config (presentation layer flags)
    from engine.config_loader import load_profile_config
    profile_config = load_profile_config()

    # Glass pipeline: enabled by profile.yaml OR --glass CLI flag
    glass_enabled = profile_config["display"]["glass_pipeline"] or args.glass
    glass_level = profile_config["display"]["glass_level"]

    # Tips engine: enabled by profile.yaml
    tips_enabled = profile_config["display"]["tips"]
    tip_engine = None
    if tips_enabled:
        from engine.glass import TipEngine
        tip_engine = TipEngine()

    # Startup gating: profile.yaml flags OR CLI flags (either can suppress)
    startup_config = profile_config["startup"]
    skip_welcome = startup_config["skip_welcome"] or args.skip_welcome
    skip_plan = startup_config["skip_plan_generation"]
    skip_brief = startup_config["skip_startup_brief"]

    verbose = args.verbose
    profile = get_profile()

    # V-016: Prompt label from profile config (Config Over Code)
    prompt_label = profile_config["display"].get("prompt_label", "operator")

    # Initialize the Dock (Layer 1)
    dock = get_dock()
    dock_info = f"Dock: {dock.get_chunk_count()} chunks from {len(dock.list_sources())} sources"

    # V-016: Watchman status report — tiers, cortex, compute posture
    cortex_pending = _get_cortex_pending()
    tier_info = _build_tier_display()
    compute_mode = "Free Mode (LLM on-demand with consent)"  # Default for reference profile

    print_banner(
        profile=profile,
        dock_info=dock_info,
        glass_enabled=glass_enabled,
        cortex_pending=cortex_pending,
        compute_mode=compute_mode,
        tier_info=tier_info
    )

    # V-015: Startup mode selection (before any pipeline traversals)
    # This sets session-scoped enrichment mode, not persisted to disk.
    from engine.profile import set_session_enrichment
    enrichment_enabled = _run_startup_mode_selection()
    set_session_enrichment(enrichment_enabled)

    # Check for structured plan — generate on first boot (Sprint 5)
    # Now routed through the pipeline (purity-audit-v1)
    from engine.profile import get_dock_dir

    c = Colors
    plan_path = get_dock_dir() / "system" / "structured-plan.md"
    if not skip_plan and not plan_path.exists():
        print(f"  {c.CYAN}[FIRST BOOT]{c.RESET} No structured plan found.")
        print(f"  {c.DIM}Generating initial plan from dock context...{c.RESET}")
        print()

        # Route through pipeline - Stage 4 handles Yellow zone approval,
        # Stage 5 dispatcher handler does LLM call and file write
        plan_context = run_pipeline(
            raw_input="generate plan",
            source="startup_ceremony",
        )
        if plan_context.executed:
            result = plan_context.result or {}
            if result.get("data", {}).get("plan_written"):
                print(f"  {c.GREEN}[PLAN CREATED]{c.RESET} Structured plan written to dock.")
                print(f"  {c.DIM}The Chief of Staff now has trajectory awareness.{c.RESET}")
            elif not plan_context.approved:
                print(f"  {c.YELLOW}[DEFERRED]{c.RESET} Plan generation skipped.")
            else:
                print(f"  {c.YELLOW}[JIDOKA]{c.RESET} Plan generation failed — check telemetry.")
        else:
            print(f"  {c.YELLOW}[DEFERRED]{c.RESET} Plan generation skipped.")
        print()

    # Welcome Briefing (replaces cold command list)
    # Now routed through the pipeline (purity-audit-v1)
    if not skip_welcome:
        # Route welcome_card through pipeline
        welcome_context = run_pipeline(
            raw_input="welcome_card",
            source="startup_ceremony",
        )
        if welcome_context.executed:
            result = welcome_context.result or {}
            briefing = result.get("message", "")
            if briefing:
                print(f"  {c.WHITE}{briefing}{c.RESET}")
                print()
            else:
                # Briefing failed — Jidoka: surface the failure, don't hide it
                print(f"  {c.YELLOW}[JIDOKA]{c.RESET} Welcome briefing unavailable — check telemetry for details.")
                print(f"  {c.DIM}Type {c.CYAN}help{c.RESET} for the operator guide, or start with what's on your mind.{c.RESET}")
                print()
        else:
            print(f"  {c.YELLOW}[JIDOKA]{c.RESET} Welcome briefing unavailable — check telemetry for details.")
            print(f"  {c.DIM}Type {c.CYAN}help{c.RESET} for the operator guide, or start with what's on your mind.{c.RESET}")
            print()

        # Chief of Staff Strategic Brief - route through pipeline
        if not skip_brief:
            brief_context = run_pipeline(
                raw_input="startup_brief",
                source="startup_ceremony",
            )
            if brief_context.executed:
                result = brief_context.result or {}
                brief = result.get("message", "")
                if brief:
                    print(f"  {c.CYAN}{'─' * 56}{c.RESET}")
                    print(f"  {c.WHITE}{brief}{c.RESET}")
                    print()
    else:
        print(f"  {c.DIM}Ready.{c.RESET}")
        print()

    while True:
        try:
            # Read user input with colored prompt (V-016: configurable label)
            user_input = input(f"{c.CYAN}{prompt_label}>{c.RESET} ").strip()

            # Handle exit commands (only exception - not routed through pipeline)
            if user_input.lower() in ("exit", "quit"):
                print(f"\n{c.DIM}Session complete. Engine standing by.{c.RESET}\n")
                break

            # Handle empty input
            if not user_input:
                continue

            # Handle verbose toggle (system command, no telemetry needed)
            if user_input.lower() == "verbose":
                verbose = not verbose
                status = f"{c.GREEN}ON{c.RESET}" if verbose else f"{c.YELLOW}OFF{c.RESET}"
                print(f"\n  {c.DIM}[VERBOSE MODE]{c.RESET} {status}\n")
                continue

            # ================================================================
            # EVERY other input goes through the Invariant Pipeline
            # The Cognitive Router determines intent, domain, and zone
            # The Dispatcher routes to the appropriate handler in Stage 5
            # ================================================================
            context = run_pipeline(
                raw_input=user_input,
                source="operator_session"
            )

            # Glass pipeline display (if enabled)
            # Epic E: Read from telemetry stream, not PipelineContext
            if glass_enabled:
                from engine.glass import display_glass_from_telemetry, display_ratchet_announcement
                pipeline_id = context.telemetry_event.get("id", "")
                ratchet_msg = display_glass_from_telemetry(pipeline_id, glass_level)
                if ratchet_msg:
                    display_ratchet_announcement(ratchet_msg)

            # Display results based on dispatch data type
            display_result(context, verbose)

            # Contextual tips (if enabled)
            if tip_engine:
                # Pass dict to TipEngine (event-based)
                tip_data = {
                    "intent": context.intent,
                    "zone": context.zone,
                    "entities": context.entities,
                    "events": context.events,
                }
                tip_text = tip_engine.evaluate(tip_data)
                if tip_text:
                    from engine.glass import display_tip
                    display_tip(tip_text)

        except KeyboardInterrupt:
            print(f"\n\n{c.YELLOW}Session interrupted.{c.RESET} Exiting...\n")
            break
        except EOFError:
            print(f"\n\n{c.DIM}End of input.{c.RESET} Exiting...\n")
            break
        except Exception as e:
            # Digital Jidoka: Surface errors, don't swallow them
            print(f"\n  {c.RED}[ERROR]{c.RESET} Pipeline failure: {e}")
            print(f"  {c.DIM}The line has stopped. Please review and retry.{c.RESET}\n")


if __name__ == "__main__":
    main()
