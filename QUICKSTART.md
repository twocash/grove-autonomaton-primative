# Quickstart: Build Your Own Autonomaton

This guide walks you through creating a new Autonomaton profile for your domain.

---

## Prerequisites

- Python 3.11+
- An Anthropic API key (set as `ANTHROPIC_API_KEY` environment variable)

```bash
pip install anthropic pyyaml
```

---

## Step 1: Create Your Profile

Duplicate the `blank_template` profile with your domain name:

```bash
cp -r profiles/blank_template profiles/my_domain
```

Your profile directory structure:
```
profiles/my_domain/
├── config/
│   ├── routing.config    # Intent-to-handler mapping
│   ├── zones.schema      # Zone governance rules
│   ├── mcp.config        # External service config
│   ├── voice.yaml        # Brand voice
│   └── pillars.yaml      # Content themes
├── dock/                  # Strategic context (RAG)
├── entities/              # Extracted entities
├── skills/                # Generated skills
├── telemetry/             # Audit trail
├── queue/                 # Kaizen proposals
└── output/                # Generated content
```

---

## Step 2: Define Your Strategic Context

Populate your `dock/` directory with strategic documents:

**dock/goals.md** - Your primary objectives:
```markdown
# Goals

## Primary Objectives
1. [Your first goal]
2. [Your second goal]

## Success Metrics
- [How you measure progress]
```

**dock/business-plan.md** - Your operational context:
```markdown
# Business Plan

## Mission
[Your mission statement]

## Key Activities
- [What your Autonomaton does]

## Target Audience
- [Who you serve]
```

---

## Step 3: Configure Your Intents

Edit `config/routing.config` to define your domain intents:

```yaml
routes:
  # Example: Generate a report
  generate_report:
    tier: 1
    zone: green
    domain: reports
    description: "Generate a weekly report"
    keywords:
      - "weekly report"
      - "generate report"
    handler: "skill_executor"
    handler_args:
      skill_name: "weekly-report"

  # Example: Send notification (Yellow Zone)
  send_notification:
    tier: 2
    zone: yellow
    domain: communications
    description: "Send notification to stakeholders"
    keywords:
      - "notify"
      - "send notification"
    handler: "mcp_notification"
    handler_args:
      server: "email_service"
      capability: "send_email"
```

---

## Step 4: Configure Your Zones

Edit `config/zones.schema` to define domain governance:

```yaml
zones:
  green:
    approval: none
    description: "Safe autonomous operations"
  yellow:
    approval: one_thumb
    description: "Requires confirmation"
  red:
    approval: explicit_with_context
    description: "High-stakes, full review"

domains:
  reports:
    description: "Report generation"
    default_zone: green

  communications:
    description: "External communications"
    default_zone: yellow
```

---

## Step 5: Run Session Zero (Optional)

Bootstrap your entities with the guided intake:

```bash
python autonomaton.py --profile my_domain
```

Then in the REPL:
```
autonomaton> session zero
```

This Socratic interview extracts:
- Key entities (people, places, concepts)
- Business context
- Operational patterns

---

## Step 6: Start Using Your Autonomaton

Launch your Autonomaton:

```bash
python autonomaton.py --profile my_domain
```

### Basic Commands

| Command | Description |
|---------|-------------|
| `dock` | Show loaded strategic context |
| `queue` | Show pending Kaizen proposals |
| `skills` | List deployed skills |
| `build skill [name]` | Generate a new skill (Red Zone) |
| `exit` | End session |

---

## Step 7: Build Custom Skills

As you use your Autonomaton, the Cortex analyzes patterns and proposes new skills.

To manually build a skill:
```
autonomaton> build skill weekly-summary
```

The Pit Crew will:
1. Prompt for a description
2. Generate the skill using LLM
3. Validate against the Architectural Judge
4. Deploy to `skills/weekly-summary/`

---

## Zone Governance in Action

### Green Zone (Automatic)
```
autonomaton> generate report
[EXECUTED] Report generated successfully
```

### Yellow Zone (Requires Approval)
```
autonomaton> send notification

==================================================
JIDOKA: Stopping the line for human input
==================================================

YELLOW ZONE ACTION REQUIRES APPROVAL:
[ACTION] Send notification to stakeholders

  [1] Approve and execute
  [2] Cancel operation

Enter choice [1/2]: 1

[EXECUTED] Notification sent
```

### Red Zone (Explicit Review)
```
autonomaton> build skill payment-processor

==================================================
RED ZONE: System Modification Requires Approval
==================================================

This action will modify system capabilities.
Skill: payment-processor

Review and confirm? [yes/no]: yes
[EXECUTED] Skill deployed
```

---

## Telemetry & Analytics

All interactions are logged to `telemetry/telemetry.jsonl`:

```json
{
  "id": "abc123...",
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "operator_session",
  "raw_transcript": "generate report",
  "zone_context": "green",
  "inferred": {"intent": "generate_report", "confidence": 0.95}
}
```

Run Cortex analysis manually:
```
autonomaton> cortex analyze
autonomaton> cortex ratchet
autonomaton> cortex evolve
```

---

## Directory Reference

| Directory | Purpose |
|-----------|---------|
| `config/` | Declarative configuration |
| `dock/` | Strategic documents (RAG) |
| `entities/` | Extracted entities (players, projects) |
| `skills/` | Pit Crew generated skills |
| `telemetry/` | JSONL audit trail |
| `queue/` | Pending Kaizen proposals |
| `output/` | Generated content |

---

## Next Steps

1. **Add MCP integrations** - Configure external services in `mcp.config`
2. **Define content pillars** - Set up themes in `pillars.yaml`
3. **Create skills** - Build automation for repeated tasks
4. **Monitor telemetry** - Use Cortex lenses to optimize

---

## Troubleshooting

### "No profile set" error
Ensure you specify a profile:
```bash
python autonomaton.py --profile my_domain
```

### "Unknown handler" error
Your `routing.config` references a handler that doesn't exist. Use one of:
- `status_display`
- `content_engine`
- `pit_crew`
- `session_zero_handler`
- `skill_executor`
- `cortex_batch`

### Yellow Zone keeps prompting
This is by design. Yellow Zone actions require human approval. To make an intent autonomous, change its `zone: yellow` to `zone: green` in `routing.config`.

---

*Your sovereign Autonomaton awaits. Build wisely.*
