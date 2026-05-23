"""
backend/routes/webhook.py  —  Raunit's file
=============================================
This file connects Twilio to your full voice pipeline.

It imports all routes directly from voice/twilio_handler.py
and registers them under the /voice/ prefix.

When Twilio calls:
  POST /voice/incoming-call  → handled by twilio_handler.incoming_call()
  POST /voice/process-speech → handled by twilio_handler.process_speech()
  POST /voice/call-status    → handled by twilio_handler.call_status()
  GET  /voice/status         → handled by twilio_handler.voice_status()

No logic lives here — this file is purely a router bridge.
All actual call handling logic is in voice/twilio_handler.py
"""

import sys
import os
from pathlib import Path

# ── Make sure voice/ and ai/ folders are importable from backend/ ─────────
# This is needed because uvicorn runs from the backend/ folder
# but twilio_handler.py imports from voice/ and ai/

ROOT_DIR   = Path(__file__).resolve().parents[2]   # ai-voice-assistant/
VOICE_DIR  = ROOT_DIR / "voice"
AI_DIR     = ROOT_DIR / "ai"

for path in [str(ROOT_DIR), str(VOICE_DIR), str(AI_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ── Import the full router from twilio_handler ────────────────────────────
try:
    from voice.twilio_handler import router

except ImportError as e:
    # Fallback — if twilio_handler can't be imported yet
    # (e.g. twilio package not installed) keep placeholder routes
    import logging
    logging.getLogger(__name__).warning(
        f"[WEBHOOK] Could not import twilio_handler: {e}\n"
        f"Run: pip install twilio\n"
        f"Using placeholder routes until then."
    )

    from fastapi import APIRouter, Request
    router = APIRouter()

    @router.post("/incoming-call")
    async def incoming_call(request: Request):
        return {"status": "twilio_handler not loaded", "error": str(e)}

    @router.post("/process-speech")
    async def process_speech(request: Request):
        return {"status": "twilio_handler not loaded"}

    @router.post("/call-status")
    async def call_status(request: Request):
        return {"received": True}

    @router.get("/status")
    def voice_status():
        return {
            "status": "placeholder — twilio not installed",
            "fix":    "pip install twilio"
        }