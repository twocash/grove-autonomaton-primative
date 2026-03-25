"""
ux.py - Stage 4 Andon Display

Three-beat TPS display grounded in the published specification.
Every design decision cites the White Paper or TCP/IP Paper.

ARCHITECTURAL GROUNDING:
  White Paper Part II: "Jidoka — automation with a human touch.
    When a machine detects a quality problem, it stops the production
    line automatically and signals for human intervention."
  White Paper Part II: "Kaizen — continuous improvement... propose a
    specific improvement, implement the change, measure the result."
  TCP/IP Paper §III: "the five-stage pipeline is the thin waist of
    the cognitive hourglass." ONE rendering path. No legacy fallback.

THREE BEATS — each a distinct TPS moment:
  Beat 1: JIDOKA  — The discipline DETECTS (quality awareness)
  Beat 2: ANDON   — The mechanism STOPS (the cord pulls)
  Beat 3: KAIZEN  — The response PROPOSES (improvement options)
           Only present when proposing improvement, never for
           zone consent. (White Paper Part III §2: Red zone —
           "The system doesn't propose here.")

V-023: Eliminated legacy fallback path. ONE function, no branches
for display style. Frame is pipeline infrastructure, not config.
"""

import sys
import os
import json

# Windows UTF-8 support for Unicode box-drawing characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


# =========================================================================
# Semantic Color Palette
# =========================================================================
# Each color maps to a TPS concept, not a decoration.
#
# White Paper Part III §2 (Sovereignty Guardrails):
#   Green = "Autonomous Routine" → flow, not success
#   Yellow = "Supervised Proposals" → paused, yielding
#   Red = "Human-Only Zones" → requires intervention
#
# The color IS the governance signal.

class _Colors:
    """TPS semantic colors — each maps to an architectural concept."""
    ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"

    RESET   = "\033[0m" if ENABLED else ""
    BOLD    = "\033[1m" if ENABLED else ""
    DIM     = "\033[2m" if ENABLED else ""

    # TPS state colors
    JIDOKA  = "\033[91m" if ENABLED else ""   # Soft red — quality alert detected
    ANDON   = "\033[93m" if ENABLED else ""   # Warm amber — line paused, yielding
    KAIZEN  = "\033[97m" if ENABLED else ""   # Clean white — calm proposal
    GREEN   = "\033[92m" if ENABLED else ""   # Sage — flow / confirmation echo


_c = _Colors


# =========================================================================
# V-015/V-018: Template Resolution for Tiered Options
# =========================================================================

def _resolve_option_template(label: str, tier: int = None,
                              classification_tier: int = None,
                              response_tier: int = None) -> str:
    """
    Resolve template variables in option labels.

    V-015: Options in kaizen.yaml can include {tier_label} and {tier_cost}
    placeholders. This function resolves them from models.yaml at display time.

    V-018: Added {total_cost} for unified options that include both
    classification AND response tiers. Config Over Code — reads from llm_client.
    """
    from engine.llm_client import estimate_turn_cost, get_model_label

    has_templates = any(t in label for t in ['{tier_label}', '{tier_cost}', '{total_cost}'])
    if not has_templates:
        return label

    resolved = label

    # V-018: Handle {total_cost} for unified classification+response options
    if '{total_cost}' in resolved:
        c_tier = classification_tier if classification_tier is not None else tier
        r_tier = response_tier if response_tier is not None else tier

        if c_tier is not None and r_tier is not None:
            class_cost = estimate_turn_cost(c_tier)
            resp_cost = estimate_turn_cost(r_tier)
            total_cost = class_cost + resp_cost
            resolved = resolved.replace('{total_cost}', f"{total_cost:.4f}")
        elif tier is not None:
            total_cost = estimate_turn_cost(tier)
            resolved = resolved.replace('{total_cost}', f"{total_cost:.4f}")

    # Legacy single-tier placeholders
    if tier is not None:
        if '{tier_label}' in resolved:
            tier_label = get_model_label(tier)
            resolved = resolved.replace('{tier_label}', tier_label)

        if '{tier_cost}' in resolved:
            tier_cost = estimate_turn_cost(tier)
            resolved = resolved.replace('{tier_cost}', f"{tier_cost:.4f}")

    return resolved


# =========================================================================
# Stage 4 Andon Display — THREE BEATS, ONE PATH
# =========================================================================

def ask_jidoka(
    context_message: str,
    options: dict,
    diagnostic: dict = None,
    kaizen_prompt: str = None,
    payload: dict = None,
    options_config: dict = None,
) -> str:
    """
    Stage 4 prompt — Three-beat TPS display.

    ONE function. No legacy fallback. No second code path.
    (TCP/IP Paper §III: "the five-stage pipeline is the thin
    waist of the cognitive hourglass.")

    Beat 1: JIDOKA  — detects (White Paper Part II)
    Beat 2: ANDON   — stops   (White Paper Part II)
    Beat 3: KAIZEN  — proposes (White Paper Part VI)
             Only when proposing improvement. Never for
             zone consent. (Part III §2: Red = "surfaces
             information and waits")

    Args:
        context_message: Explanation of why the system stopped
        options: Dict mapping option numbers (as strings) to descriptions
        diagnostic: Optional dict with {summary, confidence, cost} for Jidoka beat
        kaizen_prompt: Optional string — triggers Kaizen beat (only for improvement)
        payload: Optional dict — triggers payload display (Red zone transparency)
        options_config: Optional dict with tier info for template resolution

    Returns:
        The key of the selected option (e.g., "1" or "2")
    """
    print()

    # ── Beat 1: JIDOKA ──
    # White Paper Part II: "Jidoka transforms a machine from a blind,
    # repetitive engine into an active partner in quality control —
    # one that has the authority to stop the world the moment it
    # needs human intuition."
    #
    # The watchman reports WHAT it found. Diagnostic context.
    print(f"  {_c.JIDOKA}◇ JIDOKA{_c.RESET}")
    if diagnostic:
        summary = diagnostic.get("summary", "")
        conf = diagnostic.get("confidence", 0)
        cost = diagnostic.get("cost", 0)
        print(f"  {_c.DIM}└─{_c.RESET} {summary}")
        print(f"  {_c.DIM}   Confidence: {conf:.0%}  ·  Cost: ${cost:.2f}{_c.RESET}")
    else:
        # Zone approval — Jidoka detected a governance boundary
        # White Paper Part III §2: every action has an explicit risk classification
        for i, line in enumerate(context_message.strip().split("\n")):
            prefix = "└─" if i == 0 else "  "
            print(f"  {_c.DIM}{prefix}{_c.RESET} {line}")

    # ── Beat 2: ANDON ──
    # White Paper Part II: "signals for human intervention with
    # the 'andon cord.' The system doesn't hide defects. It
    # doesn't route around them with fallback paths. It stops,
    # surfaces the problem with diagnostic context, and waits
    # for a human decision."
    #
    # White Paper Part III §5: "This is Toyoda's 'andon cord', digitized."
    print(f"  {_c.ANDON}◇ ANDON{_c.RESET}")
    if diagnostic:
        print(f"  {_c.DIM}└─ Line stopped. Routing decision required.{_c.RESET}")
    else:
        print(f"  {_c.DIM}└─ Line stopped. Approval required.{_c.RESET}")

    # Payload transparency (Red zone)
    # White Paper Part III §2: Red zone "surfaces information
    # and waits." The payload IS the surfaced information.
    if payload:
        payload_str = json.dumps(payload, indent=2, default=str)
        print(f"  {_c.DIM}   ┌─ payload ─┐{_c.RESET}")
        for pl in payload_str.split("\n"):
            print(f"  {_c.DIM}   │ {pl}{_c.RESET}")
        print(f"  {_c.DIM}   └───────────┘{_c.RESET}")

    # ── Beat 3: KAIZEN (conditional) ──
    # White Paper Part II: "Kaizen — continuous improvement.
    # Not a one-time fix but a systematic discipline: observe
    # the process, identify waste or failure, propose a specific
    # improvement."
    #
    # CRITICAL: Kaizen ONLY appears when the system is PROPOSING
    # IMPROVEMENT — not when requesting zone consent.
    #   Part III §2, Red: "The system doesn't propose here."
    #   Part III §2, Yellow: Governance consent, not Kaizen.
    if kaizen_prompt:
        print(f"  {_c.KAIZEN}◇ KAIZEN{_c.RESET}")
        print(f"  {_c.DIM}└─{_c.RESET} {kaizen_prompt}")

    # ── Options ──
    print()
    valid_keys = set(options.keys())
    for key in sorted(options.keys(), key=int):
        label = options[key]
        # Resolve template variables if options_config provided
        if options_config and key in options_config:
            opt = options_config[key]
            label = _resolve_option_template(
                label,
                tier=opt.get("tier"),
                classification_tier=opt.get("classification_tier"),
                response_tier=opt.get("response_tier")
            )
        print(f"     {_c.BOLD}[{key}]{_c.RESET} {label}")
    print()

    # ── Input ──
    while True:
        try:
            response = _get_single_keystroke(valid_keys)
            if response in valid_keys:
                # Resolve selection label for echo
                selected_label = options[response]
                if options_config and response in options_config:
                    opt = options_config[response]
                    selected_label = _resolve_option_template(
                        selected_label,
                        tier=opt.get("tier"),
                        classification_tier=opt.get("classification_tier"),
                        response_tier=opt.get("response_tier")
                    )
                print(f"\n  {_c.GREEN}▸{_c.RESET} {_c.BOLD}{selected_label}{_c.RESET}\n")
                return response
        except KeyboardInterrupt:
            print(f"\n\n{_c.ANDON}Operation cancelled by user.{_c.RESET}")
            sys.exit(0)


# =========================================================================
# Single-Keystroke Input
# =========================================================================

def _get_single_keystroke(valid_keys: set) -> str:
    """Get a single keystroke from the user."""
    prompt = f"     Choice [{'/'.join(sorted(valid_keys))}]: "

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
                    print(char)
                    return char
                else:
                    print(f"\n     Invalid. Enter {'/'.join(sorted(valid_keys))}.")
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
                    print(char)
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    return char
                elif char == "\x03":  # Ctrl+C
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    raise KeyboardInterrupt
                else:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    print(f"\n     Invalid. Enter {'/'.join(sorted(valid_keys))}.")
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
        print(f"     Invalid. Enter {'/'.join(sorted(valid_keys))}.")


# =========================================================================
# Convenience Wrappers — Zone Approval (Two-Beat, No Kaizen)
# =========================================================================

def confirm_yellow_zone(action_description: str) -> bool:
    """
    Yellow Zone approval — two-beat display.
    Jidoka detects zone boundary. Andon stops. Operator consents.
    No Kaizen — this is governance consent, not improvement.
    """
    result = ask_jidoka(
        context_message=f"Yellow zone action detected.\n{action_description}",
        options={
            "1": "Approve and execute",
            "2": "Cancel"
        }
    )
    return result == "1"


def confirm_red_zone(action_description: str) -> bool:
    """
    Red Zone approval — two-beat display.
    Jidoka detects zone boundary. Andon stops. Operator consents.
    No Kaizen — White Paper Part III §2: "The system doesn't propose here."
    """
    result = ask_jidoka(
        context_message=f"Red zone action detected.\n{action_description}",
        options={
            "1": "Approve and execute",
            "2": "Cancel"
        }
    )
    return result == "1"


def confirm_yellow_zone_with_context(action_description: str, payload: dict) -> bool:
    """
    Yellow Zone approval with payload transparency.
    """
    result = ask_jidoka(
        context_message=f"Yellow zone action detected.\n{action_description}",
        options={
            "1": "Approve and execute",
            "2": "Cancel"
        },
        payload=payload
    )
    return result == "1"


def confirm_red_zone_with_context(action_description: str, payload: dict) -> bool:
    """
    Red Zone approval with payload transparency.
    White Paper Part III §2: "surfaces information and waits."
    """
    result = ask_jidoka(
        context_message=f"Red zone action detected.\n{action_description}",
        options={
            "1": "Approve and execute",
            "2": "Cancel"
        },
        payload=payload
    )
    return result == "1"


def resolve_entity_ambiguity(entity_type: str, candidates: list[str]) -> str:
    """
    Entity resolution — two-beat display.
    Jidoka detected multiple matches. Andon stops. Operator selects.
    """
    options = {str(i + 1): candidate for i, candidate in enumerate(candidates)}
    options[str(len(candidates) + 1)] = "None of these / Cancel"

    result = ask_jidoka(
        context_message=f"Multiple matches found for {entity_type.upper()}.",
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
    """
    from engine.llm_client import call_llm
    from engine.config_loader import get_persona

    persona = get_persona()
    payload_str = json.dumps(payload, indent=2, default=str)

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
        intent = payload.get("intent", "unknown action")
        handler = payload.get("handler", "")
        return f"The system wants to perform: {intent}" + (f" (via {handler})" if handler else "")
