#!/bin/bash
set -e

# Write Google credentials from env var to file
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  echo "$GOOGLE_CREDENTIALS_JSON" > /app/agent/google-credentials.json
  export GOOGLE_APPLICATION_CREDENTIALS=/app/agent/google-credentials.json
fi

# Next.js web server (background)
node /app/web/server.js &

# Python voice agent (foreground — container lives/dies with this)
cd /app/agent
exec uv run agent.py start
