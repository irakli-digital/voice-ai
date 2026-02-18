#!/bin/bash
set -e

# Write Google credentials from env var to file
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  echo "$GOOGLE_CREDENTIALS_JSON" > /app/agent/google-credentials.json
  export GOOGLE_APPLICATION_CREDENTIALS=/app/agent/google-credentials.json
fi

# Next.js web server (background) — uses $PORT from Railway
node /app/web/server.js &

# Python voice agent (foreground) — override PORT to avoid conflict
cd /app/agent
export PORT=8081
exec uv run agent.py start
