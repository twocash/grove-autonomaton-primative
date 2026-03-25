"""
theme.py - Unified Visual Language Constants

Single source of truth for colors, spacing, and typography.
All terminal output modules import from here.

V-024: Extracted from ux.py, glass.py, and autonomaton.py.

ARCHITECTURAL GROUNDING:
  White Paper Part III §1 (Config Over Code): "Can a non-technical
  domain expert alter the system's behavior by editing a config file?"
  Color IS governance in this system — the zone model says so.

  White Paper Part III §2 (Zone Model): Colors map to governance signals.
    Green = "Autonomous Routine" → flow, not success
    Yellow = "Supervised Proposals" → paused, yielding
    Red = "Human-Only Zones" → requires intervention

COLOR SEMANTICS:
  TPS names (from V-023 Andon UX):
    JIDOKA  — quality alert detected (red)
    ANDON   — line paused, yielding (amber)
    KAIZEN  — calm improvement proposal (white)
    GREEN   — flow / confirmation

  Generic names (backward compatibility):
    RED, YELLOW, WHITE, GREEN, CYAN, MAGENTA
"""

import sys
import os


class Colors:
    """
    Unified color constants for all terminal output.

    Provides both TPS semantic names (JIDOKA, ANDON, KAIZEN) and
    generic color names (RED, YELLOW, WHITE) as aliases to the
    same underlying ANSI codes.
    """
    # Terminal capability detection
    ENABLED = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"

    # Text formatting
    RESET = "\033[0m" if ENABLED else ""
    BOLD = "\033[1m" if ENABLED else ""
    DIM = "\033[2m" if ENABLED else ""

    # ─────────────────────────────────────────────────────────
    # TPS Semantic Colors (White Paper Part III §2)
    # ─────────────────────────────────────────────────────────
    # Each maps to an architectural concept, not a decoration.

    JIDOKA = "\033[91m" if ENABLED else ""   # Quality alert detected
    ANDON = "\033[93m" if ENABLED else ""    # Line paused, yielding
    KAIZEN = "\033[97m" if ENABLED else ""   # Calm proposal
    GREEN = "\033[92m" if ENABLED else ""    # Flow / confirmation

    # ─────────────────────────────────────────────────────────
    # Generic Color Aliases (backward compatibility)
    # ─────────────────────────────────────────────────────────
    # Same ANSI codes, different names for different contexts.

    RED = "\033[91m" if ENABLED else ""      # = JIDOKA
    YELLOW = "\033[93m" if ENABLED else ""   # = ANDON
    WHITE = "\033[97m" if ENABLED else ""    # = KAIZEN
    CYAN = "\033[96m" if ENABLED else ""     # Informational accent
    MAGENTA = "\033[95m" if ENABLED else ""  # Special markers
    BLUE = "\033[94m" if ENABLED else ""     # Skills/status markers


# Module-level alias for compact usage: `from engine.theme import c`
c = Colors


# ─────────────────────────────────────────────────────────────
# Layout Constants
# ─────────────────────────────────────────────────────────────
# Future: these could be loaded from theme.yaml in the profile.
# For now, hardcoded constants are the structural win.

GLASS_WIDTH = 58          # Character width of Glass Pipeline display
DIVIDER_CHAR = "─"        # Thin horizontal line (U+2500)
INDENT = "  "             # Standard indentation (2 spaces)
