"""
ux.py - Andon Gate & Jidoka UX

Implements "stop the line" user interaction patterns (Andon)
in service of the Digital Jidoka quality discipline.
When ambiguity or approval is required, the system halts
and surfaces a numbered, single-keystroke prompt.

No silent failures. No graceful degradation.
"""

import sys
import os


# =========================================================================
# Terminal Colors
# =========================================================================

class _Colors:
    """ANSI color codes for terminal output."""
    ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"

    RESET = "\033[0m" if ENABLED else ""
    BOLD = "\033[1m" if ENABLED else ""
    DIM = "\033[2m" if ENABLED else ""
    YELLOW = "\033[93m" if ENABLED else ""
    RED = "\033[91m" if ENABLED else ""
    GREEN = "\033[92m" if ENABLED else ""
    CYAN = "\033[96m" if ENABLED else ""
    WHITE = "\033[97m" if ENABLED else ""
    MAGENTA = "\033[95m" if ENABLED else ""


_c = _Colors


def ask_jidoka(context_message: str, options: dict) -> str:
    """
    Present a Jidoka prompt requiring single-keystroke numeric response.

    Args:
        context_message: Explanation of why the system stopped
        options: Dict mapping option numbers (as strings) to descriptions
                 e.g., {"1": "Approve and continue", "2": "Cancel operation"}

    Returns:
        The key of the selected option (e.g., "1" or "2")

    Behavior:
        - Prints context message
        - Lists numbered options
        - Blocks until valid single-digit response
        - Rejects any non-matching input and re-prompts
    """
    print()
    print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
    print(f"{_c.BOLD}{_c.YELLOW}ANDON GATE: Stopping the line for human input{_c.RESET}")
    print(f"{_c.YELLOW}{'=' * 60}{_c.RESET}")
    print(f"\n{context_message}\n")

    # Display options
    valid_keys = set(options.keys())
    for key in sorted(options.keys(), key=int):
        print(f"  {_c.CYAN}[{key}]{_c.RESET} {options[key]}")

    print()

    while True:
        try:
            response = _get_single_keystroke(valid_keys)
            if response in valid_keys:
                print(f"\n{_c.GREEN}>>{_c.RESET} Selected: {_c.WHITE}{options[response]}{_c.RESET}\n")
                return response
        except KeyboardInterrupt:
            print(f"\n\n{_c.YELLOW}Operation cancelled by user.{_c.RESET}")
            sys.exit(0)


def _get_single_keystroke(valid_keys: set) -> str:
    """
    Get a single keystroke from the user.

    Strictly enforces single-character numeric input.
    Falls back to line-based input if terminal doesn't support raw mode.
    """
    prompt = f"Enter choice [{'/'.join(sorted(valid_keys))}]: "

    # Try platform-specific single-key input
    if sys.platform == "win32":
        return _get_keystroke_windows(prompt, valid_keys)
    else:
        return _get_keystroke_unix(prompt, valid_keys)


def _get_keystroke_windows(prompt: str, valid_keys: set) -> str:
    """Windows-specific keystroke capture."""
    try:
        import msvcrt
        print(prompt, end="", flush=True)
        while True:
            if msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in valid_keys:
                    print(char)  # Echo the character
                    return char
                else:
                    print(f"\n  Invalid input '{char}'. Please enter a valid option.")
                    print(prompt, end="", flush=True)
    except ImportError:
        return _get_keystroke_fallback(prompt, valid_keys)


def _get_keystroke_unix(prompt: str, valid_keys: set) -> str:
    """Unix-specific keystroke capture using termios."""
    try:
        import tty
        import termios

        print(prompt, end="", flush=True)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                char = sys.stdin.read(1)
                if char in valid_keys:
                    print(char)  # Echo the character
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    return char
                elif char == "\x03":  # Ctrl+C
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    raise KeyboardInterrupt
                else:
                    # Restore terminal, print error, set raw again
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    print(f"\n  Invalid input. Please enter a valid option.")
                    print(prompt, end="", flush=True)
                    tty.setraw(fd)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except (ImportError, termios.error):
        return _get_keystroke_fallback(prompt, valid_keys)


def _get_keystroke_fallback(prompt: str, valid_keys: set) -> str:
    """Fallback for environments without raw terminal support."""
    while True:
        response = input(prompt).strip()
        if len(response) == 1 and response in valid_keys:
            return response
        print(f"  Invalid input. Please enter exactly one of: {', '.join(sorted(valid_keys))}")


def confirm_yellow_zone(action_description: str) -> bool:
    """
    Convenience wrapper for Yellow Zone approval.

    Returns True if user approves, False if cancelled.
    """
    result = ask_jidoka(
        context_message=f"{_c.YELLOW}YELLOW ZONE ACTION REQUIRES APPROVAL:{_c.RESET}\n{action_description}",
        options={
            "1": "Approve and execute",
            "2": "Cancel operation"
        }
    )
    return result == "1"


def confirm_red_zone(action_description: str) -> bool:
    """
    Convenience wrapper for Red Zone approval.

    Returns True if user approves, False if cancelled.
    """
    result = ask_jidoka(
        context_message=f"{_c.RED}{_c.BOLD}RED ZONE ACTION REQUIRES EXPLICIT APPROVAL:{_c.RESET}\n{action_description}",
        options={
            "1": "Approve and execute",
            "2": "Cancel operation"
        }
    )
    return result == "1"


def resolve_entity_ambiguity(entity_type: str, candidates: list[str]) -> str:
    """
    Convenience wrapper for entity resolution.

    Returns the selected entity string.
    """
    options = {str(i + 1): candidate for i, candidate in enumerate(candidates)}
    options[str(len(candidates) + 1)] = "None of these / Cancel"

    result = ask_jidoka(
        context_message=f"{_c.CYAN}AMBIGUOUS {entity_type.upper()} REFERENCE:{_c.RESET}\nMultiple matches found. Please select:",
        options=options
    )

    idx = int(result) - 1
    if idx < len(candidates):
        return candidates[idx]
    return ""


# =========================================================================
# Conversational Jidoka (Sprint 7.5)
# =========================================================================

def translate_action_for_approval(payload: dict) -> str:
    """
    Translate a raw action payload into conversational language.

    Uses Tier 1 (Haiku) LLM for low latency.
    Persona from config/persona.yaml explains what the system wants to do.

    Implements Invariant #2: Config Over Code - persona loaded from YAML.

    Args:
        payload: Raw action payload with intent, handler, handler_args, etc.

    Returns:
        Conversational explanation string
    """
    import json
    from engine.llm_client import call_llm
    from engine.config_loader import get_persona

    persona = get_persona()
    payload_str = json.dumps(payload, indent=2, default=str)

    # Build system prompt from persona config with Jidoka-specific context
    task_context = """The system has halted to ask the boss for approval.
Read this technical payload and explain to the boss in 1-2 conversational sentences
what the system wants to do and why it needs permission.
Be clear, concise, and avoid technical jargon."""

    system_prompt = persona.build_system_prompt(task_context)

    prompt = f"""Technical payload requiring approval:

{payload_str}

Explain this action in conversational language:"""

    try:
        translation = call_llm(prompt=prompt, system=system_prompt, tier=1)
        return translation.strip()
    except Exception:
        # Graceful fallback: return a basic description
        intent = payload.get("intent", "unknown action")
        handler = payload.get("handler", "")
        return f"The system wants to perform: {intent}" + (f" (via {handler})" if handler else "")


def format_jidoka_display(conversational: str, raw_payload: dict) -> str:
    """
    Format the Jidoka display with conversational summary at top,
    raw payload underneath for transparency.

    Args:
        conversational: The conversational explanation from translate_action_for_approval
        raw_payload: The raw technical payload dict

    Returns:
        Formatted string for display
    """
    import json
    from engine.config_loader import get_persona

    persona = get_persona()
    payload_str = json.dumps(raw_payload, indent=2, default=str)

    output_lines = [
        "",
        f"{_c.BOLD}{persona.name}:{_c.RESET}",
        f"  {conversational}",
        "",
        f"{_c.DIM}─── RAW SYSTEM PAYLOAD ───{_c.RESET}",
        f"{_c.DIM}{payload_str}{_c.RESET}",
        f"{_c.DIM}──────────────────────────{_c.RESET}",
        ""
    ]

    return "\n".join(output_lines)


def confirm_yellow_zone_with_context(action_description: str, payload: dict) -> bool:
    """
    Yellow Zone approval with conversational translation.

    Translates the payload to conversational language before showing
    the approval prompt. Shows both conversational summary and raw payload.

    Args:
        action_description: Brief description of the action
        payload: Raw action payload for translation

    Returns:
        True if user approves, False if cancelled
    """
    # Get conversational translation
    conversational = translate_action_for_approval(payload)

    # Format the display
    display = format_jidoka_display(conversational, payload)

    # Show with Jidoka prompt
    result = ask_jidoka(
        context_message=f"{_c.YELLOW}YELLOW ZONE ACTION REQUIRES APPROVAL:{_c.RESET}\n{display}",
        options={
            "1": "Approve and execute",
            "2": "Cancel operation"
        }
    )
    return result == "1"


def confirm_red_zone_with_context(action_description: str, payload: dict) -> bool:
    """
    Red Zone approval with conversational translation.

    Translates the payload to conversational language before showing
    the approval prompt. Shows both conversational summary and raw payload.

    Args:
        action_description: Brief description of the action
        payload: Raw action payload for translation

    Returns:
        True if user approves, False if cancelled
    """
    # Get conversational translation
    conversational = translate_action_for_approval(payload)

    # Format the display
    display = format_jidoka_display(conversational, payload)

    # Show with Jidoka prompt
    result = ask_jidoka(
        context_message=f"{_c.RED}{_c.BOLD}RED ZONE ACTION REQUIRES EXPLICIT APPROVAL:{_c.RESET}\n{display}",
        options={
            "1": "Approve and execute",
            "2": "Cancel operation"
        }
    )
    return result == "1"
