# Calendar Event Extraction

Extract scheduling parameters from the user's request.

## User Input
"{user_input}"

## Instructions
Return ONLY valid JSON with these fields:
- event_type: Type of event (lesson, practice, tournament, meeting)
- participant: Name of person/group involved
- date: Date in ISO format (YYYY-MM-DD)
- time: Time in 24-hour format (HH:MM)
- duration_minutes: Duration in minutes (default 60)
- location: Location if mentioned (optional)

JSON:
