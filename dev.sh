#!/bin/bash
set -e

# Load all env vars from root .env.local
set -a
source .env.local
set +a

trap 'kill $(jobs -p) 2>/dev/null' EXIT

# Web server (background)
(cd web && npm run dev) &

# Agent (foreground)
cd agent && uv run agent.py dev
