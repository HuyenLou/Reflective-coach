#!/bin/bash
# Integration test script for the coaching API
# Tests a complete feedback avoidance coaching session
#
# Usage:
#   ./scripts/run_case_feedback.sh
#   BASE_URL=http://localhost:8000 ./scripts/run_case_feedback.sh

set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}

echo "Testing API at: $BASE_URL"

# Step 1: Create session
echo ""
echo "============================================================"
echo "Step 1: Creating session..."
echo "============================================================"

create_resp=$(curl -s -X POST "$BASE_URL/sessions" \
  -H "Content-Type: application/json" \
  -d '{"topic":"I avoid feedback because it makes me feel exposed","max_turns":12}')

echo "Create response: $create_resp"

if [ -z "$create_resp" ]; then
  echo "ERROR: Empty response from server. Is the API running at $BASE_URL?"
  exit 1
fi

# Parse session_id using Python (more reliable than jq on Windows)
session_id=$(echo "$create_resp" | python -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))")

if [ -z "$session_id" ]; then
  echo "ERROR: Failed to parse session_id. Response was:"
  echo "$create_resp"
  exit 1
fi

echo "Session ID: $session_id"

# Step 2: Send messages
echo ""
echo "============================================================"
echo "Step 2: Sending messages..."
echo "============================================================"

declare -a messages=(
  "In my last 1:1, my manager asked how I want feedback and I said it's fine, but I actually didn't want any."
  "I worry feedback means I'm failing or not good enough."
  "If they point out weaknesses, I feel embarrassed and start doubting myself."
  "Last time I got a critical comment, I kept replaying it for days."
  "So I try to avoid the conversation to protect my confidence."
  "But I also feel stuck because I'm not improving."
  "If I keep avoiding this, I'll probably plateau and get passed over."
  "I want to handle feedback without spiraling."
  "I will ask my manager for one specific piece of feedback in next week's 1:1."
  "Tonight I'll write down the exact question I'll ask and how I'll respond if it's uncomfortable."
)

i=1
for msg in "${messages[@]}"; do
  echo ""
  echo "--- Turn $i ---"
  echo "User: ${msg:0:60}..."

  # Build JSON payload using Python (handles escaping properly)
  payload=$(echo "$msg" | python -c "import json,sys; print(json.dumps({'content': sys.stdin.read().strip()}))")

  resp=$(curl -s -X POST "$BASE_URL/sessions/$session_id/messages" \
    -H "Content-Type: application/json" \
    -d "$payload")

  # Extract phase and truncated content
  phase=$(echo "$resp" | python -c "import json,sys; print(json.load(sys.stdin).get('phase',''))" 2>/dev/null || echo "unknown")
  content=$(echo "$resp" | python -c "import json,sys; c=json.load(sys.stdin).get('content',''); print(c[:100]+'...' if len(c)>100 else c)" 2>/dev/null || echo "$resp")

  echo "Phase: $phase"
  echo "Coach: $content"

  i=$((i+1))
  sleep 0.5
done

# Step 3: End session
echo ""
echo "============================================================"
echo "Step 3: Ending session..."
echo "============================================================"

end_resp=$(curl -s -X POST "$BASE_URL/sessions/$session_id/end")
echo "Session ended"

# Extract reflection info if available
outcome=$(echo "$end_resp" | python -c "import json,sys; r=json.load(sys.stdin).get('reflection',{}); print(r.get('outcome_classification',''))" 2>/dev/null || echo "")
commitment=$(echo "$end_resp" | python -c "import json,sys; r=json.load(sys.stdin).get('reflection',{}); print(r.get('commitment',''))" 2>/dev/null || echo "")

if [ -n "$outcome" ]; then
  echo "Outcome: $outcome"
  echo "Commitment: $commitment"
fi

# Step 4: Get final session state
echo ""
echo "============================================================"
echo "Step 4: Final session state..."
echo "============================================================"

curl -s "$BASE_URL/sessions/$session_id" | python -m json.tool

# Optional: Check database if sqlite3 is available
if command -v sqlite3 >/dev/null 2>&1 && [ -f "coaching.db" ]; then
  echo ""
  echo "============================================================"
  echo "Database check..."
  echo "============================================================"
  sqlite3 coaching.db "SELECT id, topic, current_phase, turn_count, status FROM sessions WHERE id = '$session_id';"
  sqlite3 coaching.db "SELECT role, phase, turn_number, substr(content,1,80) FROM messages WHERE session_id = '$session_id' ORDER BY turn_number, created_at;"
  sqlite3 coaching.db "SELECT outcome, substr(observations,1,120), commitment, substr(insights,1,120) FROM reflections WHERE session_id = '$session_id';"
fi

echo ""
echo "============================================================"
echo "TEST COMPLETED SUCCESSFULLY"
echo "============================================================"
