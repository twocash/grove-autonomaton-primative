# Weekly Practice Plan Skill

## Overview
Generates structured weekly practice plans that integrate skill development with character formation. Reads the current roster, seasonal context, and upcoming match schedule to produce actionable practice sessions for Monday/Wednesday/Friday.

## Usage
```
autonomaton> practice plan
autonomaton> weekly session
autonomaton> weekly practice
autonomaton> what should we work on
```

## What It Does
1. Reads seasonal context from the Dock (current week, upcoming matches, weather)
2. Pulls player profiles from entities (strengths, development areas, coaching notes)
3. Generates three structured practice sessions (MWF, 3:30-5:30 PM)
4. Each session includes: warm-up, technical station, on-course work, short game, and a character lesson
5. Pairs players strategically based on coaching notes
6. Notes content opportunities that arise naturally from practice activities

## Zone
Green — read-only analysis and generation. No external actions.

## Output
Structured weekly practice plan saved to `output/reports/`. Can be printed or shared with assistant coaches.

## Telemetry Value
Every practice plan generates data about drill selection, player pairings, and content seed generation — feeding the Ratchet's understanding of coaching patterns and enabling the Cortex to propose optimizations over time.
