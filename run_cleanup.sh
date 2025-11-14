#!/bin/bash
# Script to run expired subscriptions cleanup
# This can be called by cron or scheduled tasks

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the cleanup script
python3 remove_expired.py

# Exit with the same code as the Python script
exit $?

