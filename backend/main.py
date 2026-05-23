"""
backend/main.py  —  Sameer's file (updated for Groq integration)
============================================================
Main entry point for the FastAPI backend server.
Mounts routes for appointment CRUD and Twilio webhook voice integration.
Also mounts static files to serve dynamically generated TTS wav files.
"""

import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Resolve paths to allow importing from both backend and root level directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "backend"))

# Import active routers
from backend.routes import appointments
from voice.twilio_handler import router as twilio_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Voice Assistant API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static files directory exists
static_dir = PROJECT_ROOT / "static"
static_dir.mkdir(exist_ok=True)
audio_dir = static_dir / "audio"
audio_dir.mkdir(parents=True, exist_ok=True)

# Mount Static Files to serve generated TTS files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(appointments.router, prefix="/appointments")
app.include_router(twilio_router, prefix="/voice")


@app.get("/")
def health_check():
    return {
        "status": "running", 
        "message": "AI Voice Assistant backend is live and integrated with Groq APIs"
    }