# Autonomaton Developer Guide

## The TCP/IP of Cognition
Protocol over Implementation. Skills are nodes in a composable pipeline.

## Composition Primitives
- Chain: Output of Node A becomes input telemetry for Node B
- Supervisor/Worker: Parent node dispatches to children

## Output Contract
All skills MUST return structured JSON with:
- status: success/failure
- data: payload for downstream nodes
- chain_context: metadata for composition
