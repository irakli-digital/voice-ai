#!/bin/bash
set -e

trap 'kill $(jobs -p) 2>/dev/null' EXIT

# Web server (background)
(cd web && npm run dev) &

# Agent (foreground)
cd agent && uv run agent.py dev
