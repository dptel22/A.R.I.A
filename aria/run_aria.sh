#!/bin/bash
# run_aria.sh — A.R.I.A. System Launcher
# Initialises DB, downloads model, then starts the API and dashboard.
# Run from inside the aria/ directory.

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         🛣️  A.R.I.A. — Road Infrastructure Auditor       ║"
echo "║         Autonomous Road Infrastructure Auditor  v1.0     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Schema & Seed ──────────────────────────────────────
echo "📦 Step 1/3 — Initialising database …"
python db/schema.py
python db/seed.py
echo ""

# ── Step 2: Download Model ─────────────────────────────────────
echo "🤖 Step 2/3 — Setting up model weights …"
python pipeline/setup_model.py
echo ""

# ── Step 3: Launch Services ────────────────────────────────────
echo "🚀 Step 3/3 — Starting services …"
echo ""

# Start FastAPI in background
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
UVICORN_PID=$!
echo "   ✅ FastAPI started  — http://localhost:8000  (PID: $UVICORN_PID)"
echo "   📖 API docs         — http://localhost:8000/docs"
sleep 2

# Start Streamlit in foreground (blocks — press Ctrl+C to stop both)
echo "   ✅ Streamlit starting — http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop all A.R.I.A. services."
echo ""

trap "echo ''; echo 'Stopping A.R.I.A. services …'; kill $UVICORN_PID 2>/dev/null; exit 0" INT TERM

streamlit run dashboard/app.py --server.port 8501
