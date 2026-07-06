#!/bin/bash
#
# Worker launcher - creates, triggers, monitors, and deletes a dynamic worker
# Usage: worker_launcher.sh "user query"
#

set -e

# ---------- Configuration ----------
MAX_WORKERS=19
REPO="${REPO:-${{ github.repository }}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- Input ----------
QUERY="$1"
if [ -z "$QUERY" ]; then
    echo "❌ Error: query is required"
    exit 1
fi

echo "🧠 Creating worker for query: $QUERY"

# ---------- Check concurrency limit ----------
RUNNING=$(python3 "$SCRIPT_DIR/github_ops.py" --count-running "Temporary Worker" 2>/dev/null || echo 0)
if [ "$RUNNING" -ge "$MAX_WORKERS" ]; then
    echo "❌ All $MAX_WORKERS workers are busy. Please wait."
    exit 1
fi

echo "✅ Currently $RUNNING workers running. Spawning new one."

# ---------- Generate unique filename ----------
TIMESTAMP=$(date +%s)
FILENAME="worker_${TIMESTAMP}.yaml"

# ---------- Build worker YAML ----------
cat > /tmp/worker.yaml << 'WORKER_EOF'
name: Temporary Worker

on:
  workflow_dispatch:

jobs:
  worker:
    runs-on: ubuntu-latest
    timeout-minutes: 360
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          curl -fsSL https://ollama.com/install.sh | sh
          ollama serve &
          sleep 5
          ollama pull granite4:tiny-h
          npm install -g openclaw
          echo "$(npm root -g)/bin" >> $GITHUB_PATH
          mkdir -p ~/.openclaw
          echo '{
            "models": {
              "providers": {
                "ollama": {
                  "baseUrl": "http://localhost:11434",
                  "models": [{"id": "granite4:tiny-h", "api": "ollama"}]
                }
              }
            },
            "agents": {
              "defaults": {
                "model": { "primary": "ollama/granite4:tiny-h" }
              }
            }
          }' > ~/.openclaw/openclaw.json

      - name: Execute query
        run: |
          openclaw agent run --task "$QUERY" --output result.json
          mkdir -p upload
          cp result.json upload/
        env:
          QUERY: ${{ github.event.inputs.query }}

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: result
          path: upload/
WORKER_EOF

# Replace placeholder with actual query
ESCAPED_QUERY=$(echo "$QUERY" | sed 's/"/\\"/g')
sed -i "s/\$QUERY/$ESCAPED_QUERY/g" /tmp/worker.yaml

# ---------- Create the workflow file ----------
echo "📝 Creating workflow $FILENAME..."
SHA=$(python3 "$SCRIPT_DIR/github_ops.py" --create "$FILENAME" "$(cat /tmp/worker.yaml)")
echo "✅ Created workflow (sha=$SHA)"

# ---------- Wait for registration ----------
sleep 5

# ---------- Trigger the workflow ----------
echo "🚀 Triggering workflow..."
python3 "$SCRIPT_DIR/github_ops.py" --trigger "$FILENAME"

# ---------- Poll for completion ----------
echo "⏳ Waiting for worker to finish..."
RUN_ID=$(python3 "$SCRIPT_DIR/github_ops.py" --wait "$FILENAME" 600)
echo "✅ Worker completed (run_id=$RUN_ID)"

# ---------- Download result ----------
echo "📥 Downloading result..."
RESULT=$(python3 "$SCRIPT_DIR/github_ops.py" --download "$RUN_ID")

if [ -n "$RESULT" ]; then
    echo "✅ Result:"
    echo "$RESULT" | jq .
else
    echo "⚠️ No result found"
fi

# ---------- Clean up ----------
echo "🗑️ Deleting temporary workflow..."
python3 "$SCRIPT_DIR/github_ops.py" --delete "$FILENAME" "$SHA"
echo "✅ Cleanup complete"

# ---------- Output result ----------
echo "$RESULT"
