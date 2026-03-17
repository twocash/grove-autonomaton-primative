#!/usr/bin/env python3
"""
autonomaton.py - The Invariant Engine Entry Point

The Autonomaton REPL - a domain-agnostic agentic system.
All user input passes through the Invariant Pipeline.
The Cortex runs tail-pass analysis after each interaction.

Usage:
    python autonomaton.py                          # Uses default profile (coach_demo)
    python autonomaton.py --profile coach_demo     # Explicit profile selection
    python autonomaton.py --zone yellow            # Force yellow zone for testing
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
        "--zone",
        choices=["green", "yellow", "red"],
        default="green",
        help="Default zone for all commands (default: green)"
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


def handle_build_skill(user_input: str) -> None:
    """
    Handle the 'build skill [name]' command with Red Zone governance.

    This is a Tier 3 / Red Zone operation that:
    1. Generates boilerplate skill files in memory
    2. Requires explicit Red Zone approval via Jidoka
    3. Only writes to skills/ directory if approved
    """
    from engine.pit_crew import build_skill
    from engine.telemetry import log_event

    # Parse skill name from input
    parts = user_input.split(maxsplit=2)

    if len(parts) < 3:
        print("\n  [PIT CREW] Usage: build skill <name>")
        print("  Example: build skill weekly-report")
        print("  Example: build skill tournament-prep\n")
        return

    skill_name = parts[2]

    # Log the build request through the pipeline
    log_event(
        source="operator_session",
        raw_transcript=user_input,
        zone_context="red",
        inferred={"intent": "pit_crew_build", "skill_name": skill_name}
    )

    print(f"\n  [PIT CREW] Initiating skill build: {skill_name}")
    print("  This is a RED ZONE operation that modifies system capabilities.\n")

    # Prompt for description
    try:
        description = input("  Enter skill description: ").strip()
        if not description:
            description = f"Auto-generated skill: {skill_name}"
    except (KeyboardInterrupt, EOFError):
        print("\n  [PIT CREW] Build cancelled.\n")
        return

    # Build the skill (includes Red Zone approval)
    result = build_skill(skill_name, description)

    # Report outcome
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


def handle_content_compilation() -> None:
    """
    Handle the 'compile content' command with Yellow Zone approval.

    This is a Tier 2 / Yellow Zone operation that:
    1. Reads content seeds from entities/content-seeds/
    2. Compiles them into platform-ready drafts
    3. Requires user approval before saving to output/content/
    """
    from engine.content_engine import compile_content, save_content_drafts, format_for_approval
    from engine.ux import ask_jidoka
    from engine.telemetry import log_event

    print("\n  [CONTENT ENGINE] Compiling content seeds...")

    # Log the compilation request
    log_event(
        source="content_compilation",
        raw_transcript="compile content",
        zone_context="yellow",
        inferred={"intent": "content_compilation"}
    )

    # Compile content seeds
    drafts = compile_content()

    if not drafts:
        print("  [CONTENT ENGINE] No content seeds found in entities/content-seeds/")
        print("  Create markdown files with pillar/theme metadata to get started.\n")
        return

    # Format drafts for approval display
    approval_text = format_for_approval(drafts)

    # Yellow Zone: Require explicit approval before writing files
    result = ask_jidoka(
        context_message=f"YELLOW ZONE - Content Compilation Complete:\n\n{approval_text}",
        options={
            "1": "Approve and save to output/content/",
            "2": "Discard drafts"
        }
    )

    if result == "1":
        # Save the approved drafts
        saved_files = save_content_drafts(drafts)
        print(f"\n  [CONTENT ENGINE] Saved {len(saved_files)} draft(s) to output/content/:")
        for filepath in saved_files:
            print(f"    - {filepath.name}")
        print()

        # Log the successful save
        log_event(
            source="content_compilation",
            raw_transcript=f"Saved {len(saved_files)} content drafts",
            zone_context="yellow",
            inferred={"action": "approved", "files_saved": len(saved_files)}
        )
    else:
        print("\n  [CONTENT ENGINE] Drafts discarded. No files written.\n")

        # Log the rejection
        log_event(
            source="content_compilation",
            raw_transcript="Content drafts discarded by user",
            zone_context="yellow",
            inferred={"action": "rejected"}
        )


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
            # Future: Add to a task list or calendar
            remove_from_queue(item_id)
            processed += 1
        elif result == "2":
            print(f"  Dismissed: {item_id}")
            remove_from_queue(item_id)
            processed += 1
        else:
            print(f"  Deferred: {item_id}")
            # Leave in queue for next startup
            processed += 1

    print()
    return processed


def main():
    """Main REPL loop."""
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
    from engine.pit_crew import list_deployed_skills

    default_zone = args.zone
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
            # Read
            user_input = input("autonomaton> ").strip()

            # Handle exit commands
            if user_input.lower() in ("exit", "quit"):
                print("\nSession complete. Engine standing by.\n")
                break

            # Handle empty input
            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() == "dock":
                print(f"\n  [DOCK STATUS]")
                print(f"  Chunks: {dock.get_chunk_count()}")
                print(f"  Sources: {', '.join(Path(s).name for s in dock.list_sources())}\n")
                continue

            if user_input.lower() == "queue":
                pending = load_pending_queue()
                print(f"\n  [KAIZEN QUEUE]")
                if pending:
                    for item in pending:
                        print(f"  - [{item.get('trigger', '?')}] {item.get('proposal', '?')[:50]}...")
                else:
                    print("  No pending items.")
                print()
                continue

            if user_input.lower() == "verbose":
                verbose = not verbose
                print(f"\n  [VERBOSE MODE] {'ON' if verbose else 'OFF'}\n")
                continue

            # Handle content compilation command (Yellow Zone)
            if user_input.lower() == "compile content":
                handle_content_compilation()
                continue

            # Handle build skill command (RED ZONE)
            if user_input.lower().startswith("build skill"):
                handle_build_skill(user_input)
                continue

            # Handle skills list command
            if user_input.lower() == "skills":
                skills = list_deployed_skills()
                print(f"\n  [DEPLOYED SKILLS]")
                if skills:
                    for skill in skills:
                        status = "configured" if skill.get("has_config") else "incomplete"
                        print(f"    - {skill['name']} ({status})")
                else:
                    print("    No skills deployed yet.")
                print()
                continue

            # Handle zone testing command
            zone = default_zone
            if user_input.lower() == "yellow":
                zone = "yellow"
                user_input = "Test yellow zone approval flow"

            # Eval: Pass through the Invariant Pipeline
            context = run_pipeline(
                raw_input=user_input,
                source="operator_session",
                zone=zone
            )

            # Print: Acknowledge the result
            event_id = context.telemetry_event.get('id', 'unknown')[:8]

            if verbose and context.dock_context:
                print(f"\n  [DOCK CONTEXT]")
                # Show a condensed version of the dock context
                dock_text = context.dock_context[0] if context.dock_context else ""
                # Extract just the source info
                lines = dock_text.split('\n')
                for line in lines[:5]:  # First 5 lines
                    if line.strip():
                        print(f"  {line.strip()}")
                print()

            if context.executed:
                print(f"  [LOGGED] Event ID: {event_id}...")
                print(f"  [STATUS] {context.result.get('message', 'Complete')}\n")
            else:
                print(f"  [LOGGED] Event ID: {event_id}...")
                print(f"  [STATUS] {context.result.get('message', 'Cancelled')}\n")

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
