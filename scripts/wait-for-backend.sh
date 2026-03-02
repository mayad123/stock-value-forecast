#!/usr/bin/env sh
# Poll http://localhost:8000/health until 200 or timeout. On timeout: print error, optionally kill backend PID, exit 1.
# Usage: wait-for-backend.sh [timeout_seconds] [backend_pid]
#   timeout_seconds  default 60
#   backend_pid      optional; if set and we timeout, kill this process before exiting

set -e

TIMEOUT="${1:-60}"
BACKEND_PID="${2:-}"
URL="${WAIT_FOR_BACKEND_URL:-http://localhost:8000/health}"

i=0
while [ "$i" -lt "$TIMEOUT" ]; do
	code=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null) || true
	if [ "$code" = "200" ]; then
		echo "Backend ready at $URL"
		exit 0
	fi
	i=$((i + 1))
	[ "$i" -eq "$TIMEOUT" ] && break
	sleep 1
done

echo "Error: Backend did not respond with HTTP 200 at $URL within ${TIMEOUT}s." >&2
echo "  Check that the backend starts correctly (e.g. run 'python run.py serve' in another terminal)." >&2
echo "  If the backend failed to start, fix the error above and run 'make dev' again." >&2
if [ -n "$BACKEND_PID" ]; then
	kill "$BACKEND_PID" 2>/dev/null || true
	echo "  Stopped the backend process (PID $BACKEND_PID)." >&2
fi
exit 1
