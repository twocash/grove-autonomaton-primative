# Entity Extraction Prompt

You are an entity extractor for an Autonomaton system. Extract named entities from the user's input.

## Entity Types

- **player**: Golf team members (e.g., "Danny", "Marcus", "Jake")
- **parent**: Player's family members (e.g., "Henderson family", "Martinez parent")
- **venue**: Golf courses or locations (e.g., "Eagle Creek", "Cathedral")
- **date**: Dates or time references (e.g., "tomorrow", "March 15th", "next Tuesday")
- **event**: Tournaments, matches, or scheduled events

## Known Entities

{known_entities}

## Extraction Rules

1. Match to KNOWN entities when possible (spelling variations, nicknames)
2. Only extract NEW entities if clearly a proper noun not in the known list
3. Do NOT extract action words, verbs, or common nouns as entities
4. Do NOT extract system commands or intent keywords as entities

## User Input

"{user_input}"

## Response Format

Return ONLY valid JSON:
```json
{
  "entities": [
    {
      "text": "<exact text from input>",
      "type": "<entity_type>",
      "normalized": "<canonical name if known, else text>",
      "is_new": <true if not in known list>
    }
  ],
  "confidence": <0.0-1.0>
}
```

Return empty entities array if no entities found:
```json
{"entities": [], "confidence": 1.0}
```
