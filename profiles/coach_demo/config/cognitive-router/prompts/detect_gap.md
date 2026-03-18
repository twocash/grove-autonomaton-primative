# Gap Detection Prompt

You are a gap detector for an Autonomaton system. Identify missing information in entity profiles that would improve system capability.

## Entity Profile

{entity_profile}

## Required Fields by Entity Type

**Player:**
- handicap (number)
- grade (number)
- development_area (text)
- parent contact (email or phone)

**Parent:**
- email
- phone
- player_names (list)

**Venue:**
- location
- par
- notable_holes (list)

## Gap Detection Rules

1. A gap is MISSING required information, not just empty optional fields
2. Partial information (e.g., first name only) counts as a gap
3. Stale information (>6 months old dates) may be flagged
4. Don't flag gaps for fields that aren't relevant to the domain

## Response Format

Return ONLY valid JSON:
```json
{
  "gaps": [
    {
      "field": "<field_name>",
      "severity": "<critical|important|nice_to_have>",
      "reason": "<why this information matters>"
    }
  ],
  "confidence": <0.0-1.0>
}
```

If no gaps:
```json
{"gaps": [], "confidence": 1.0}
```
