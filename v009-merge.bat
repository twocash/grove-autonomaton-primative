@echo off
cd /d C:\GitHub\grove-autonomaton-primative

echo === Adding all changes ===
git add -A

echo === Committing (if any unstaged changes) ===
git commit -m "V-009-phase2-deprecate-coach-tests" --allow-empty

echo === Checking out main ===
git checkout main

echo === Merging v009-telemetry-tests with --no-ff ===
git merge v009-telemetry-tests --no-ff -m "Merge v009-telemetry-tests: pipeline invariant verified"

echo === Creating tag v0.1.0-pattern-proven ===
git tag -a v0.1.0-pattern-proven -m "Pipeline invariant verified. V-009 architecture tests enforce five-stage pipeline, Digital Jidoka, Ratchet cache, and clean startup. Full pytest green."

echo === Pushing to origin main with tags ===
git push origin main --tags

echo === Done ===
