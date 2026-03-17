FROM python:3.11-slim

# Install system dependencies and Node (needed for Claude Code Pit Crew & MCPs)
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean

# Install Claude Code globally for the Pit Crew
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# We do not copy the code here. We will mount it at runtime
# so the coach's local files (telemetry, dock, entities) persist.
