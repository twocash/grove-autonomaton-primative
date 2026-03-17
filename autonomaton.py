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
import argparse
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Profile must be set BEFORE importing engine modules
from engine.profile import set_profile, list_available_profiles, get_profile


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
    print()
    print("=" * 55)
    print("  THE AUTONOMATON")
    print(f"  Profile: {profile}")
    print("=" * 55)
    print(f"  {dock_info}")
    print(f"  {cortex_info}")
    print("=" * 55)
    print("  Commands:")
    print("    exit/quit         - End session")
    print("    compile content   - Compile content seeds (Yellow Zone)")
    print("    build skill [name]- Build new skill (RED ZONE)")
    print("    skills            - List deployed skills")
    print("    dock              - Show dock status")
    print("    queue             - Show pending Kaizen items")
    print("    verbose           - Toggle verbose mode")
    print("=" * 55)
    print()


def process_pending_queue() -> int:
    """
    Process pending Kaizen items at startup using Jidoka UX.

    Returns the number of items processed.
    """
    from engine.cortex import load_pending_queue, remove_from_queue
    from engine.ux import ask_jidoka

    pending = load_pending_queue()

    if not pending:
        return 0

    print()
    print("=" * 55)
    print("  PENDING KAIZEN ITEMS")
    print("  The Cortex has identified improvement opportunities.")
    print("=" * 55)
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
            print(f"  Accepted: {proposal[:50]}...")
            remove_from_queue(item_id)
            processed += 1
        elif result == "2":
            print(f"  Dismissed: {item_id}")
            remove_from_queue(item_id)
            processed += 1
        else:
            print(f"  Deferred: {item_id}")
            processed += 1

    print()
    return processed


def display_result(context, verbose: bool) -> None:
    """
    Display pipeline result based on dispatch data type.

    Handles type-specific formatting for different handler outputs.
    """
    event_id = context.telemetry_event.get('id', 'unknown')[:8]
    data = context.result.get("data", {})
    data_type = data.get("type") if isinstance(data, dict) else None

    # Verbose dock context
    if verbose and context.dock_context:
        print(f"\n  [DOCK CONTEXT]")
        dock_text = context.dock_context[0] if context.dock_context else ""
        lines = dock_text.split('\n')
        for line in lines[:5]:
            if line.strip():
                print(f"  {line.strip()}")
        print()

    # Type-specific display
    if data_type == "dock_status":
        print(f"\n  [DOCK STATUS]")
        print(f"  Chunks: {data.get('chunks', 0)}")
        print(f"  Sources: {', '.join(data.get('sources', []))}\n")

    elif data_type == "queue_status":
        print(f"\n  [KAIZEN QUEUE]")
        items = data.get("items", [])
        if items:
            for item in items:
                print(f"  - [{item.get('trigger', '?')}] {item.get('proposal', '?')}...")
        else:
            print("  No pending items.")
        print()

    elif data_type == "skills_list":
        print(f"\n  [DEPLOYED SKILLS]")
        skills = data.get("skills", [])
        if skills:
            for skill in skills:
                status = "configured" if skill.get("has_config") else "incomplete"
                print(f"    - {skill['name']} ({status})")
        else:
            print("    No skills deployed yet.")
        print()

    elif data_type == "content_compilation":
        draft_count = data.get("draft_count", 0)
        if draft_count > 0:
            print(f"\n  [CONTENT ENGINE] {draft_count} draft(s) compiled")
            print("  Approval was handled during pipeline execution.\n")
        else:
            print("\n  [CONTENT ENGINE] No content seeds found\n")

    elif data_type == "pit_crew_build":
        if data.get("requires_description"):
            # Need to collect description interactively
            handle_skill_build_interactive(data.get("skill_name"))
        elif data.get("error"):
            print(f"\n  [PIT CREW] {context.result.get('message')}\n")
        else:
            print(f"\n  [PIT CREW] {context.result.get('message')}\n")

    else:
        # Generic display
        if context.executed:
            print(f"  [LOGGED] Event ID: {event_id}...")
            print(f"  [STATUS] {context.result.get('message', 'Complete')}\n")
        else:
            print(f"  [LOGGED] Event ID: {event_id}...")
            print(f"  [STATUS] {context.result.get('message', 'Cancelled')}\n")


def handle_skill_build_interactive(skill_name: str) -> None:
    """
    Handle interactive skill building (description prompt).

    This is called AFTER the pipeline has classified and approved
    the pit_crew_build intent. The actual build operation goes
    through the pit_crew module which has its own Red Zone approval.
    """
    from engine.pit_crew import build_skill

    print(f"\n  [PIT CREW] Initiating skill build: {skill_name}")
    print("  This is a RED ZONE operation that modifies system capabilities.\n")

    try:
        description = input("  Enter skill description: ").strip()
        if not description:
            description = f"Auto-generated skill: {skill_name}"
    except (KeyboardInterrupt, EOFError):
        print("\n  [PIT CREW] Build cancelled.\n")
        return

    # Build the skill (includes its own Red Zone approval)
    result = build_skill(skill_name, description)

    if result.get("status") == "deployed":
        print(f"\n  [PIT CREW] Skill deployed successfully!")
        print(f"  Location: skills/{skill_name}/")
        if result.get("files"):
            print("  Files created:")
            for f in result["files"]:
                print(f"    - {Path(f).name}")
        print()
    elif result.get("status") == "rejected":
        print(f"\n  [PIT CREW] {result.get('message')}\n")
    else:
        print(f"\n  [PIT CREW] Error: {result.get('message')}\n")


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

    while True:
        try:
            # Read user input
            user_input = input("autonomaton> ").strip()

            # Handle exit commands (only exception - not routed through pipeline)
            if user_input.lower() in ("exit", "quit"):
                print("\nSession complete. Engine standing by.\n")
                break

            # Handle empty input
            if not user_input:
                continue

            # Handle verbose toggle (system command, no telemetry needed)
            if user_input.lower() == "verbose":
                verbose = not verbose
                print(f"\n  [VERBOSE MODE] {'ON' if verbose else 'OFF'}\n")
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
                print(f"  [CORTEX] Extracted {cortex_result.get('entities', 0)} entities, "
                      f"{cortex_result.get('kaizen', 0)} Kaizen proposals\n")

        except KeyboardInterrupt:
            print("\n\nSession interrupted. Exiting...\n")
            break
        except EOFError:
            print("\n\nEnd of input. Exiting...\n")
            break
        except Exception as e:
            # Digital Jidoka: Surface errors, don't swallow them
            print(f"\n  [ERROR] Pipeline failure: {e}")
            print("  The line has stopped. Please review and retry.\n")


if __name__ == "__main__":
    main()
