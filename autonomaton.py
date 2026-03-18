#!/usr/bin/env python3
"""
autonomaton.py - The Invariant Engine Entry Point

The Autonomaton REPL - a domain-agnostic agentic system.
ALL user input passes through the Invariant Pipeline.
No direct function calls - everything is routed through the 5-stage pipeline.

Sprint 1: Strict Pipeline Enforcement
- Cognitive Router classifies intents from routing.config
- Dispatcher routes to handlers in Stage 5
- Every command generates telemetry with all 5 stages

Usage:
    python autonomaton.py                          # Uses default profile (coach_demo)
    python autonomaton.py --profile coach_demo     # Explicit profile selection
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
        default="coach_demo",
        help="Profile to load (default: coach_demo)"
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
        "--skip-queue",
        action="store_true",
        help="Skip processing pending Kaizen queue at startup"
    )
    return parser.parse_args()


def print_banner(profile: str, dock_info: str, cortex_info: str):
    """Display startup banner with profile, dock, and cortex status."""
    c = Colors
    print()
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")
    print(f"{c.BOLD}{c.WHITE}  THE AUTONOMATON{c.RESET}")
    print(f"{c.DIM}  Profile: {c.CYAN}{profile}{c.RESET}")
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")
    print(f"  {c.DIM}{dock_info}{c.RESET}")
    print(f"  {c.DIM}{cortex_info}{c.RESET}")
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")
    print(f"  {c.BOLD}Commands:{c.RESET}")
    print(f"    {c.WHITE}exit/quit{c.RESET}          - End session")
    print(f"    {c.YELLOW}compile content{c.RESET}    - Compile content seeds")
    print(f"    {c.RED}build skill [name]{c.RESET} - Build new skill")
    print(f"    {c.GREEN}skills{c.RESET}             - List deployed skills")
    print(f"    {c.GREEN}dock{c.RESET}               - Show dock status")
    print(f"    {c.GREEN}queue{c.RESET}              - Show pending Kaizen items")
    print(f"    {c.DIM}verbose{c.RESET}            - Toggle verbose mode")
    print(f"{c.CYAN}{'=' * 60}{c.RESET}")
    print()


def process_pending_queue() -> int:
    """
    Process pending Kaizen items at startup using Jidoka UX.

    Returns the number of items processed.
    """
    from engine.cortex import load_pending_queue, remove_from_queue
    from engine.ux import ask_jidoka

    c = Colors
    pending = load_pending_queue()

    if not pending:
        return 0

    print()
    print(f"{c.MAGENTA}{'=' * 60}{c.RESET}")
    print(f"  {c.BOLD}{c.MAGENTA}PENDING KAIZEN ITEMS{c.RESET}")
    print(f"  {c.DIM}The Cortex has identified improvement opportunities.{c.RESET}")
    print(f"{c.MAGENTA}{'=' * 60}{c.RESET}")
    print()

    processed = 0

    for item in pending[:]:  # Copy list since we modify during iteration
        proposal = item.get("proposal", "Unknown proposal")
        trigger = item.get("trigger", "unknown")
        item_id = item.get("id", "unknown")

        result = ask_jidoka(
            context_message=f"KAIZEN PROPOSAL (trigger: {trigger}):\n\n{proposal}",
            options={
                "1": "Accept - Add to my task list",
                "2": "Dismiss - Not relevant now",
                "3": "Defer - Ask me later"
            }
        )

        if result == "1":
            print(f"  {c.GREEN}Accepted:{c.RESET} {proposal[:50]}...")
            remove_from_queue(item_id)
            processed += 1
        elif result == "2":
            print(f"  {c.YELLOW}Dismissed:{c.RESET} {item_id}")
            remove_from_queue(item_id)
            processed += 1
        else:
            print(f"  {c.DIM}Deferred:{c.RESET} {item_id}")
            processed += 1

    print()
    return processed


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
        if data.get("requires_description"):
            # Need to collect description interactively
            handle_skill_build_interactive(data.get("skill_name"))
        elif data.get("error"):
            print(f"\n  {c.RED}[PIT CREW]{c.RESET} {context.result.get('message')}\n")
        else:
            print(f"\n  {c.RED}[PIT CREW]{c.RESET} {context.result.get('message')}\n")

    elif data_type == "session_zero":
        # Session Zero intake - display the Socratic prompt
        print(f"\n  {c.CYAN}[SESSION ZERO]{c.RESET} Cortex Intake Interview")
        print(f"{c.CYAN}{'=' * 60}{c.RESET}")
        prompt_content = data.get("prompt_content", "")
        if prompt_content:
            # Display the prompt (Sprint 2: send to LLM instead)
            print(prompt_content)
        else:
            print(f"  {c.RED}Error:{c.RESET} No prompt content available")
        print(f"{c.CYAN}{'=' * 60}{c.RESET}")
        if data.get("note"):
            print(f"\n  {c.DIM}Note: {data.get('note')}{c.RESET}\n")

    elif data_type and data_type.startswith("cortex_"):
        # Cortex batch analysis results
        zc = zone_color(zone)
        print(f"\n  {c.MAGENTA}[CORTEX]{c.RESET} {context.result.get('message', 'Analysis complete')}")
        if data.get("patterns_detected"):
            print(f"  {c.DIM}Patterns:{c.RESET}")
            for pattern in data["patterns_detected"][:3]:
                print(f"    {c.DIM}-{c.RESET} {pattern}")
        if data.get("kaizen_proposals"):
            print(f"  {c.DIM}Kaizen Proposals:{c.RESET}")
            for proposal in data["kaizen_proposals"][:3]:
                priority = proposal.get("priority", "medium")
                pc = c.RED if priority == "high" else (c.YELLOW if priority == "medium" else c.GREEN)
                print(f"    {pc}[{priority.upper()}]{c.RESET} {proposal.get('proposal', '?')}")
        if data.get("ratchet_proposals"):
            print(f"  {c.DIM}Ratchet Proposals:{c.RESET}")
            for proposal in data["ratchet_proposals"][:3]:
                print(f"    {c.CYAN}[{proposal.get('intent', '?')}]{c.RESET} {proposal.get('proposed_action', '?')}")
        if data.get("evolution_proposals"):
            print(f"  {c.DIM}Evolution Proposals:{c.RESET}")
            for proposal in data["evolution_proposals"][:3]:
                print(f"    {c.BLUE}[{proposal.get('skill_name', '?')}]{c.RESET} {proposal.get('description', '?')}")
        print()

    else:
        # Generic display with zone coloring
        zc = zone_color(zone)
        if context.executed:
            print(f"  {c.DIM}[LOGGED]{c.RESET} Event ID: {c.DIM}{event_id}...{c.RESET}")
            print(f"  {zc}[{zone.upper()}]{c.RESET} {context.result.get('message', 'Complete')}\n")
        else:
            print(f"  {c.DIM}[LOGGED]{c.RESET} Event ID: {c.DIM}{event_id}...{c.RESET}")
            print(f"  {c.YELLOW}[CANCELLED]{c.RESET} {context.result.get('message', 'Cancelled')}\n")


def handle_skill_build_interactive(skill_name: str) -> None:
    """
    Handle interactive skill building (description prompt).

    This is called AFTER the pipeline has classified and approved
    the pit_crew_build intent. The actual build operation goes
    through the pit_crew module which has its own Red Zone approval.
    """
    from engine.pit_crew import build_skill

    c = Colors

    print(f"\n  {c.RED}[PIT CREW]{c.RESET} Initiating skill build: {c.WHITE}{skill_name}{c.RESET}")
    print(f"  {c.DIM}This is a RED ZONE operation that modifies system capabilities.{c.RESET}\n")

    try:
        description = input(f"  {c.BOLD}Enter skill description:{c.RESET} ").strip()
        if not description:
            description = f"Auto-generated skill: {skill_name}"
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {c.YELLOW}[PIT CREW]{c.RESET} Build cancelled.\n")
        return

    # Build the skill (includes its own Red Zone approval)
    result = build_skill(skill_name, description)

    if result.get("status") == "deployed":
        print(f"\n  {c.GREEN}[PIT CREW]{c.RESET} Skill deployed successfully!")
        print(f"  {c.DIM}Location:{c.RESET} skills/{skill_name}/")
        if result.get("files"):
            print(f"  {c.DIM}Files created:{c.RESET}")
            for f in result["files"]:
                print(f"    {c.DIM}-{c.RESET} {Path(f).name}")
        print()
    elif result.get("status") == "rejected":
        print(f"\n  {c.YELLOW}[PIT CREW]{c.RESET} {result.get('message')}\n")
    else:
        print(f"\n  {c.RED}[PIT CREW]{c.RESET} Error: {result.get('message')}\n")


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
            marker = " (default)" if p == "coach_demo" else ""
            print(f"  - {p}{marker}")
        print()
        return

    # Set the active profile BEFORE importing engine modules
    set_profile(args.profile)

    # Now import engine modules (they will use the active profile)
    from engine.pipeline import run_pipeline
    from engine.dock import get_dock
    from engine.cortex import run_tail_pass, load_pending_queue

    verbose = args.verbose
    profile = get_profile()

    # Initialize the Dock (Layer 1)
    dock = get_dock()
    dock_info = f"Dock: {dock.get_chunk_count()} chunks from {len(dock.list_sources())} sources"

    # Check pending queue count
    pending = load_pending_queue()
    cortex_info = f"Cortex: {len(pending)} pending Kaizen item(s)"

    print_banner(profile, dock_info, cortex_info)

    # Process pending Kaizen items at startup (unless skipped)
    if not args.skip_queue and pending:
        process_pending_queue()

    c = Colors

    while True:
        try:
            # Read user input with colored prompt
            user_input = input(f"{c.CYAN}autonomaton>{c.RESET} ").strip()

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

            # Display results based on dispatch data type
            display_result(context, verbose)

            # Run Cortex tail-pass analysis (Layer 3)
            cortex_result = run_tail_pass()
            if cortex_result.get("entities", 0) > 0 or cortex_result.get("kaizen", 0) > 0:
                print(f"  {c.MAGENTA}[CORTEX]{c.RESET} Extracted {cortex_result.get('entities', 0)} entities, "
                      f"{cortex_result.get('kaizen', 0)} Kaizen proposals\n")

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
