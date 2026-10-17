#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -x "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" ]; then
  exec "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" server.py
fi
exec python3 server.py
