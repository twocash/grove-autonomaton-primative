# HANDOFF PROMPT: Autonomaton UX Sprint — Onboarding & Classification Fix

## Who You Are Working With
Jim Calhoun, founder of The Grove Foundation. He built the Autonomaton — a domain-agnostic, declarative agentic system with a five-stage invariant pipeline (Telemetry → Recognition → Compilation → Approval → Execution). The `coach_demo` profile is a working reference implementation for a Catholic high school golf coach running a content ministry (@ChristInTheFairway).

## The Repo
`C:\GitHub\grove-autonomaton-primative` — Python, main branch, no worktrees active.

**Do NOT modify files until you have audited the repo and discussed the plan with Jim.**

## What Has Been Done (3 sprints completed this session)

### Sprint 1: "Opening Day" (commit cb8faa9)
Warmed the coach_demo profile with real content. All config/content, zero code changes:
- 3 new dock files: `seasonal-context.md`, `content-strategy.md`, `revenue-tithing.md`
- 6 player entities with coaching depth (Jake captain/senior, Tommy talented junior, Chris joyful junior, Danny anxious sophomore, Marcus promising freshman, Will raw freshman)
- 2 parent families, 1 venue (Eagle Creek GC with key holes and content spots)
- Rewrote `weekly-report` skill from stub to structured practice plan generator
- New `tournament-prep` skill (lineup, scouting cards, pregame word, logistics)
- 4 new content seeds across different pillars
- Enriched persona.yaml with player/calendar/content awareness
- Cleanup: deleted ~200 tmpclaude files, duplicate entities, reset exhaust/vision boards

### Sprint 2: "Onboarding" (commit 7e76456)
- Fixed JSON extraction bug in `cognitive_router.py` — old code used `startswith("```")` which failed if LLM returned any preamble before JSON. Fixed with `find('{')`/`rfind('}')`.
- Created `welcome-card` startup skill with prompt template
- Replaced cold command-list banner with LLM-generated welcome briefing in `autonomaton.py`
- Added `--skip-welcome` CLI flag

### Sprint 3: "UX Flow" (commit d0b6ce9, current HEAD)
- Bumped classification from Tier 1 (Haiku) to Tier 2 (Sonnet)
- Simplified classification prompt (5 fields instead of 8, compound input rules)
- Bumped welcome card generation to Tier 2 (Sonnet)
- Stripped hardcoded examples from welcome-card prompt (was causing parroting)

## What Is Still Broken

### Problem 1: Classification still fails on natural language
"What's on tap for today?" → Jidoka clarification menu. Even with Sonnet. The `strategy_session` intent exists with keywords like "what should I do", "what's next", "priorities" — but informal phrasing doesn't match keywords AND the LLM isn't mapping it to `strategy_session` either.

**Jim's iron law:** The LLM is the brain. Keywords are the bootstrap cache. The keyword list grows THROUGH the pipeline (the Ratchet spots stable patterns and proposes Tier 0 rules). Never manually expand keyword lists. Fix the classifier, not the word list.

### Problem 2: Jidoka message is generic, not diagnostic
When classification fails, the user sees a generic 4-option menu ("Draft content / Schedule / Check status / Just chatting"). This violates the spirit of Jidoka. Real Jidoka should be SPECIFIC — it should tell the user (and by extension the Pit Crew) WHERE the failure was: "I couldn't match your input to a known intent. Closest match was strategy_session (40% confidence). Did you mean...?" That's diagnostic. The current version is a customer service phone tree.

### Problem 3: Welcome card returned "Ready." instead of briefing
In Jim's test, `generate_welcome_briefing()` returned empty string and fell to the fallback. Need to diagnose: LLM call failure? Skill prompt path not found? Dock not loaded? The function silently catches all exceptions and returns "" — need better error surfacing.

### Problem 4: No onboarding flow — THE BIG ONE
Jim's words: "gaping wide mouth and no brains." User dumps a plan, loads dock content, and then... nothing guides them. No skill says:
- "You have 7 content seeds ready to compile. Want to start there?"
- "Your first match is in 11 days — want me to generate a tournament prep package?"
- "I notice you don't have parent email addresses loaded yet. That's needed before we can send the tournament schedule."

This is the gap between a terminal and a product. The system knows everything (dock, entities, skills, calendar) but doesn't SYNTHESIZE it into "here's what matters right now."

## Architecture You Must Understand

### The Invariant Pipeline
Every input traverses 5 stages: Telemetry → Recognition → Compilation → Approval → Execution. No bypass paths. Code: `engine/pipeline.py`.

### Recognition (Stage 2): Two-Tier Classification
- **Tier 0:** Keyword match from `routing.config` (fast, free, deterministic)
- **Tier 2:** LLM classification via Sonnet when keyword confidence < 0.7
- LLM returns structured JSON: intent, intent_type, confidence, action_required, reasoning
- If LLM returns unknown with confidence < 0.5 → clarification Jidoka fires
- Code: `engine/cognitive_router.py`

### The Ratchet Thesis
Every LLM classification logs to telemetry. Over time, the Cortex (Lens 4) spots stable patterns and proposes Tier 0 keyword rules. The keyword list WRITES ITSELF. Manual expansion is forbidden.

### Key Config Files (all in `profiles/coach_demo/config/`)
- `routing.config` — intent routing table (keywords, zones, handlers, intent_types)
- `persona.yaml` — Chief of Staff voice and constraints
- `voice.yaml` — brand voice for content generation
- `pillars.yaml` — 8 content pillars with platform-specific formatting
- `zones.schema` — domain governance (green/yellow/red)
- `mcp.config` — external service definitions (calendar, gmail — stubbed)

### Key Engine Files
- `autonomaton.py` — REPL entry point, welcome briefing, main loop
- `engine/cognitive_router.py` — Tier 0/Tier 2 classification, clarification Jidoka
- `engine/pipeline.py` — 5-stage invariant pipeline
- `engine/dispatcher.py` — handler routing (general_chat, strategy_session, content_engine, etc.)
- `engine/dock.py` — local RAG with keyword matching
- `engine/llm_client.py` — Anthropic SDK wrapper (Tier 1=Haiku, Tier 2=Sonnet, Tier 3=Opus)
- `engine/ux.py` — Jidoka prompts, zone approval UX
- `engine/config_loader.py` — persona.yaml loader

## What Jim Wants Next

### 1. An Onboarding Skill (Strategic Advisor)
Not a welcome card (that's just a greeting). An ACTIVE skill that:
- Reads the dock and understands what context is loaded
- Reads routing.config and knows what the system CAN do
- Reads entities and knows what data exists (and what's MISSING)
- Produces "here's what we can do right now" recommendations
- Identifies gaps ("no parent emails loaded — need those for the email handler")
- Prioritizes by urgency ("match in 11 days → tournament prep first")
- Helps the user "eat the elephant one bite at a time"

This should feel like a strategic advisor who looked at all your files while you were away and has a prioritized action list ready when you sit down.

### 2. Diagnostic Jidoka
When classification fails, the system should tell the user:
- What intent it ALMOST matched (closest candidate + confidence score)
- What the user could say differently
- Or suggest creating a new intent if nothing is close
- Feed this diagnostic data to the Pit Crew so it knows where routing gaps are

### 3. Classification That Works
"What's on tap for today?" should route to `strategy_session`. Diagnose why it doesn't — is it the prompt? The intent descriptions? The tier? Test before changing.

## Jim's Design Philosophy
- "Design is philosophy expressed through constraint" — the lodestar
- The LLM is the brain, keywords are the reflex. Reflexes develop FROM experience.
- Jidoka = stop the line on ambiguity, surface the decision with SPECIFIC context. NOT a generic menu.
- Config over code — domain logic in YAML, engine is dumb pipes
- The system should feel like a colleague who already knows the situation

## Sprint Discipline
- Always create a git worktree before modifying files
- `git worktree add -b sprint/[name] C:\GitHub\grove-autonomaton-primative-[name] main`
- Write `.bat` files for git commits (inline messages with spaces fail on Windows CMD)
- Merge to main with fast-forward, then remove worktree and branch
- Audit repo FIRST, discuss plan with Jim SECOND, build THIRD

## How to Start This Session
1. Read `engine/cognitive_router.py` (classification logic + Jidoka)
2. Read `profiles/coach_demo/config/routing.config` (intent vocabulary)
3. Read `autonomaton.py` (welcome briefing + main loop)
4. Read `engine/dispatcher.py` (how strategy_session handler works)
5. Test mentally: given the routing.config intent descriptions, would Sonnet classify "What's on tap for today?" → strategy_session? If not, why not?
6. Propose the onboarding skill architecture to Jim BEFORE writing code
7. Discuss Jidoka improvements BEFORE implementing

**DO NOT** expand keyword lists. **DO NOT** make changes without discussing with Jim first.
