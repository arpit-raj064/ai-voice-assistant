"""
voice/stt.py  —  Raunit's file
================================
Speech-to-Text using Groq Whisper Large v3 Turbo.

Why Groq Whisper over Deepgram/OpenAI:
  ✅ Same GROQ_API_KEY — no extra account needed
  ✅ Completely free (28,800 audio seconds/day free)
  ✅ ~150ms latency — among the fastest available
  ✅ Excellent Indian English accent support
  ✅ 100+ language support via whisper-large-v3
  ✅ OpenAI Whisper-compatible API format

Models available on Groq:
  whisper-large-v3-turbo  → faster, slightly less accurate (recommended)
  whisper-large-v3        → more accurate, slightly slower

Free tier limits (per day):
  whisper-large-v3-turbo: 28,800 audio seconds = 480 minutes/day
  whisper-large-v3:       28,800 audio seconds = 480 minutes/day
  That's 480 minutes of calls per day — more than enough.

Supported audio formats:
  flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm

Test:
  cd voice
  python stt.py
"""

import os
import io
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Model selection ───────────────────────────────────────────────────────
# Use turbo for voice calls (faster), large-v3 for more accuracy
STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")


def _get_groq_client():
    """Returns Groq client. Imported here to avoid circular imports."""
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


# ── MODE 1: Transcribe from audio file bytes ──────────────────────────────
# This is what Raunit uses — Twilio sends audio, we transcribe it
async def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename:    str = "audio.wav",
    language:    str = "en",
) -> str:
    """
    Transcribes raw audio bytes using Groq Whisper.

    Args:
        audio_bytes: Raw audio data (from Twilio recording)
        filename:    Filename hint for format detection (e.g. "audio.wav")
        language:    Language code — "en" for English, "hi" for Hindi

    Returns:
        Transcribed text string, or empty string if failed

    Usage in twilio_handler.py:
        audio_data = await download_twilio_recording(RecordingUrl)
        text = await transcribe_audio_bytes(audio_data)
    """
    if not GROQ_API_KEY:
        logger.error("[STT] GROQ_API_KEY not set in .env")
        return ""

    if not audio_bytes:
        logger.warning("[STT] No audio bytes provided")
        return ""

    try:
        client = _get_groq_client()

        # Groq expects a file-like object with a name attribute
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename   # tells Groq the format

        logger.info(f"[STT] Sending {len(audio_bytes)} bytes to Groq Whisper...")

        # Run sync Groq call in thread pool (asyncio-friendly)
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model           = STT_MODEL,
                file            = audio_file,
                language        = language,
                response_format = "text",      # returns plain string, not JSON
                prompt          = (            # helps with Indian names + medical terms
                    "This is a phone call with an AI receptionist. "
                    "The caller may mention appointment dates, times, "
                    "names, and phone numbers."
                ),
            )
        )

        transcript = str(result).strip() if result else ""

        if transcript:
            logger.info(f"[STT] ✅ Transcript: '{transcript}'")
        else:
            logger.warning("[STT] Empty transcript returned")

        return transcript

    except Exception as e:
        logger.error(f"[STT] Error: {e}")
        return ""


# ── MODE 2: Transcribe from a public URL ─────────────────────────────────
# Use this when Twilio gives you a RecordingUrl directly
async def transcribe_audio_url(
    audio_url: str,
    language:  str = "en",
) -> str:
    """
    Downloads audio from a URL and transcribes it using Groq Whisper.

    Args:
        audio_url: Public URL to audio file (e.g. Twilio RecordingUrl)
        language:  Language code

    Returns:
        Transcribed text string

    Usage in twilio_handler.py:
        text = await transcribe_audio_url(RecordingUrl)
    """
    if not audio_url:
        return ""

    try:
        import httpx

        logger.info(f"[STT] Downloading audio from URL...")

        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(audio_url)

        if response.status_code != 200:
            logger.error(f"[STT] Failed to download audio: {response.status_code}")
            return ""

        audio_bytes = response.content

        # Detect format from URL
        filename = "audio.wav"
        if ".mp3" in audio_url:
            filename = "audio.mp3"
        elif ".ogg" in audio_url:
            filename = "audio.ogg"
        elif ".webm" in audio_url:
            filename = "audio.webm"

        return await transcribe_audio_bytes(audio_bytes, filename, language)

    except Exception as e:
        logger.error(f"[STT URL] Error: {e}")
        return ""


# ── MODE 3: Transcribe from a local file (for testing) ───────────────────
async def transcribe_file(
    file_path: str,
    language:  str = "en",
) -> str:
    """
    Transcribes a local audio file. Useful for testing stt.py directly.

    Args:
        file_path: Path to audio file on disk
        language:  Language code

    Returns:
        Transcribed text string
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"[STT] File not found: {file_path}")
        return ""

    audio_bytes = path.read_bytes()
    return await transcribe_audio_bytes(audio_bytes, path.name, language)


# ── Quick test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Groq Whisper STT Test ===")
    print(f"API Key set: {'YES ✅' if GROQ_API_KEY else 'NO ❌ — add GROQ_API_KEY to .env'}")
    print(f"Model:       {STT_MODEL}")
    print(f"Free limit:  28,800 seconds/day (~480 minutes)")

    if not GROQ_API_KEY:
        print("\nGet a free key at: console.groq.com → API Keys")
        print("Then add to .env: GROQ_API_KEY=gsk_your-key")
    else:
        # Test with a sample audio URL
        print("\nTesting with sample audio file...")
        TEST_URL = "https://www2.cs.uic.edu/~i101/SoundFiles/BabyElephantWalk60.wav"

        result = asyncio.run(transcribe_audio_url(TEST_URL))

        if result:
            print(f"\n✅ SUCCESS! Transcript: '{result}'")
        else:
            print("\n❌ FAILED — check API key and try again")
            print("Note: The test audio is music so transcript may be empty — that's ok")
            print("The API connection itself is what matters")

    print("\nTo test with a real voice recording:")
    print("  1. Record yourself saying 'I want to book an appointment for Tuesday'")
    print("  2. Save as test.wav in the voice/ folder")
    print("  3. Run: python -c \"import asyncio; from stt import transcribe_file; print(asyncio.run(transcribe_file('test.wav')))\"")