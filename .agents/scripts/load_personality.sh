#!/bin/bash
# PreInvocation hook to load the personality file automatically

# Read input from stdin to extract the workspace path
INPUT=$(cat)

# The hook is executed from the .agents folder. We want the root folder of the workspace.
# We can extract it from the input JSON 'workspacePaths' array.
WORKSPACE_PATH=$(echo "$INPUT" | jq -r '.workspacePaths[0]')

if [ -z "$WORKSPACE_PATH" ] || [ "$WORKSPACE_PATH" = "null" ]; then
    # Fallback if jq fails or workspacePaths is missing: assume we are in .agents and go up
    cd ..
    WORKSPACE_PATH="$PWD"
else
    cd "$WORKSPACE_PATH"
fi

CLONE_NAME=$(basename "$WORKSPACE_PATH")

if [ "$CLONE_NAME" = "DeniDin" ]; then
    CLONE_NAME="root"
fi

PERSONALITY_FILE=".claude/personalities/${CLONE_NAME}.md"

if [ ! -f "$PERSONALITY_FILE" ]; then
    PERSONALITY_FILE=".claude/personalities/default.md"
fi

if [ -f "$PERSONALITY_FILE" ]; then
    CONTENT=$(cat "$PERSONALITY_FILE")
    jq -n --arg content "Please act as the personality described below for the duration of this chat:\n\n$CONTENT" \
    '{
      "injectSteps": [
        {
          "ephemeralMessage": $content
        }
      ]
    }'
else
    echo "{}"
fi
