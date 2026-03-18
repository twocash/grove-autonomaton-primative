# The Autonomaton: Quickstart Guide

Welcome to your sovereign cognitive engine. This is not a chatbot; it is an operating system where logic lives in configuration, and the system executes via an immutable pipeline.

## Step 1: Claim Your Sovereignty (Create a Profile)
The system ships with a `coach_demo` profile, but you should build your own.
1. Copy the `profiles/blank_template/` directory and rename it to your project (e.g., `profiles/my_engine/`).
2. Open `profiles/my_engine/config/zones.schema` and define your governance boundaries (what is safe to do automatically, what requires your approval).

## Step 2: Fill the Dock
The Dock is your strategic lens. The engine reads this before making any decisions.
1. Open `profiles/my_engine/dock/` and add your `business-plan.md`, `goals.md`, or any core operating principles.
2. The system uses RAG to pull from these files during the Compilation stage.

## Step 3: Run Session Zero
Start the engine and run the guided intake.
```bash
python autonomaton.py --profile my_engine
autonomaton> session zero
```
The system will interview you to establish your entities, voice, and workflows.

## Step 4: The Vision Board & Ambient Evolution
You do not need to code to build new features.

Tell the engine what you want: `autonomaton> I wish I had a way to track my weekly expenses.`

The system writes this to your Vision Board (`dock/system/vision-board.md`).

As you use the system, the Cortex (Layer 3) watches your telemetry. When your actual behavior matches your Vision Board aspirations, the Personal Product Manager will spec a new skill and propose it to you.

If you approve, the Pit Crew will write the code, the Architectural Judge will verify its compliance, and it will self-register into your routing table.

Welcome to the TCP/IP of the cognitive layer.
