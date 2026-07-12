# Hook Plan

| Event | Matcher | Handler | Purpose | Blocking? |
|---|---|---|---|---|
| SessionStart | * | hooks/scripts/bootstrap.sh | Prepare extension workspace | No |
| PreToolUse | Bash | hooks/scripts/guard-bash.sh | Block dangerous commands | Yes |
| PostToolUse | Write | hooks/scripts/validate-output.py | Validate generated artefacts | No |
| Stop | * | hooks/scripts/final-check.py | Warn on missing validation | No |
