#!/bin/bash

# Test script for changelog generation logic

echo "=== Testing Changelog Generation ==="
echo

# Get the previous tag using the new logic
PREVIOUS_TAG=$(git tag --sort=-version:refname | head -2 | tail -1 2>/dev/null || echo "")
echo "Previous tag found: '$PREVIOUS_TAG'"

# Get current tag (simulate getting the latest tag)
CURRENT_TAG=$(git tag --sort=-version:refname | head -1 2>/dev/null || echo "")
echo "Current tag: '$CURRENT_TAG'"

echo
echo "=== Changelog Generation ==="

CHANGELOG_CONTENT=""
GIT_LOG_COMMAND=""

if [ -z "$PREVIOUS_TAG" ]; then
  echo "No previous tag found, generating changelog from all commits:"
  GIT_LOG_COMMAND='git log --pretty=format:"* %s (%h)"'
  CHANGELOG_CONTENT=$(git log --pretty=format:"* %s (%h)")
else
  echo "Generating changelog from $PREVIOUS_TAG to $CURRENT_TAG:"
  GIT_LOG_COMMAND="git log --pretty=format:\"* %s (%h)\" $PREVIOUS_TAG..HEAD"
  CHANGELOG_CONTENT=$(git log --pretty=format:"* %s (%h)" $PREVIOUS_TAG..HEAD)
fi

echo "Executing command: $GIT_LOG_COMMAND"
echo
echo "=== Generated Changelog ==="
echo "$CHANGELOG_CONTENT"
echo
echo "=== End of Changelog ==="