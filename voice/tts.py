"""
voice/tts.py  —  Raunit's file
================================
Text-to-Speech using Groq Orpheus v1 English.

Why Groq Orpheus over ElevenLabs/Polly:
  ✅ Same GROQ_API_KEY — no extra account needed
  ✅ Completely free (100 requests/day free tier)
  ✅ Sub-200ms time-to-first-byte
  ✅ Human-level voice quality (trained on 100k+ hours)
  ✅ Supports vocal directions: [cheerful], [whisper], [laugh]
  ✅ 6 professionally trained English voices to choose from

Available voices (English):
  autumn  → warm female (recommended for receptionist)
  diana   → professional female
  hannah  → friendly female
  austin  → calm male
  daniel  → professional male
  troy    → energetic male

Vocal direction tags you can use in text:
  [cheerful]  → upbeat, positive tone
  [whisper]   → soft, quiet tone
  [laugh]     → adds a light laugh
  [sigh]      → adds a sigh sound
  [sad]       → empathetic, softer tone

Free tier limits:
  100 requests/day — enough for ~50-100 booking calls/day

Audio output format: WAV (48kHz — Groq Orpheus fixed sample rate)

Test:
  cd voice
  python tts.py
"""

import os
import time
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

# ── Model + voice configuration ───────────────────────────────────────────
TTS_MODEL = "canopylabs/orpheus-v1-english"   # only English model for now
TTS_VOICE = os.getenv("GROQ_TTS_VOICE", "autumn")  # change voice in .env if needed

# ── Audio output directory ────────────────────────────────────────────────
AUDIO_DIR = Path("static/audio")


def _get_groq_client():
    """Returns Groq client."""
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


# ── Prepare text for Orpheus ──────────────────────────────────────────────
def _prepare_text(text: str) -> str:
    """
    Cleans and prepares text for Orpheus TTS.

    - Removes internal flags (##END_CALL##, ##ESCALATE##)
    - Strips markdown formatting (* _ #)
    - Optionally adds vocal direction based on content

    Orpheus handles punctuation naturally — periods create pauses,
    question marks raise pitch. No special handling needed.
    """
    # Remove internal system flags
    text = text.replace("##END_CALL##", "").replace("##ESCALATE##", "")

    # Remove markdown formatting (shouldn't be in voice responses but just in case)
    text = text.replace("**", "").replace("*", "").replace("_", "").replace("#", "")

    # Clean up extra whitespace
    text = " ".join(text.split())

    return text.strip()


# ── MAIN FUNCTION: Convert text to audio URL ─────────────────────────────
async def text_to_speech_url(
    text:  str,
    voice: str = TTS_VOICE,
) -> str | None:
    """
    Converts text to speech using Groq Orpheus and returns a public URL.
    Twilio plays this URL to the caller.

    Args:
        text:  The AI's reply text to speak
        voice: Voice name (autumn/diana/hannah/austin/daniel/troy)

    Returns:
        Public URL string to the WAV audio file, or None if failed

    Usage in twilio_handler.py:
        audio_url = await text_to_speech_url(ai_reply)
        if audio_url:
            response.play(audio_url)
        else:
            response.say(ai_reply, voice="Polly.Aditi")  # fallback
    """
    if not GROQ_API_KEY:
        logger.warning("[TTS] GROQ_API_KEY not set — cannot generate audio")
        return None

    if not text or not text.strip():
        logger.warning("[TTS] Empty text provided")
        return None

    # Clean the text
    clean_text = _prepare_text(text)

    if not clean_text:
        return None

    # Truncate if too long (Orpheus works best under 500 chars per request)
    if len(clean_text) > 500:
        clean_text = clean_text[:497] + "..."
        logger.warning("[TTS] Text truncated to 500 chars")

    try:
        client = _get_groq_client()

        # Ensure audio directory exists
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        # Unique filename per request
        filename   = f"aria_{int(time.time() * 1000)}.wav"
        audio_path = AUDIO_DIR / filename

        logger.info(f"[TTS] Generating: '{clean_text[:60]}...' voice={voice}")

        # Run sync Groq call in thread pool
        loop = asyncio.get_event_loop()

        def _generate():
            return client.audio.speech.create(
                model           = TTS_MODEL,
                voice           = voice,
                input           = clean_text,
                response_format = "wav",   # WAV format, 48kHz fixed
            )

        response = await loop.run_in_executor(None, _generate)

        # Save audio file
        audio_path.write_bytes(response.content)

        logger.info(f"[TTS] ✅ Audio saved: {audio_path} ({len(response.content)} bytes)")

        # Return public URL for Twilio to play
        audio_url = f"{PUBLIC_BASE_URL}/static/audio/{filename}"
        return audio_url

    except Exception as e:
        err = str(e)
        logger.error(f"[TTS] Error: {err}")

        # Specific error hints
        if "rate_limit" in err.lower() or "429" in err:
            logger.warning("[TTS] Rate limit hit (100/day) — Twilio Polly fallback will be used")
        elif "model_terms" in err.lower() or "terms" in err.lower():
            logger.warning("[TTS] Accept model terms at console.groq.com → Playground → Orpheus")

        return None


# ── Synchronous wrapper (for non-async contexts) ──────────────────────────
def text_to_speech_url_sync(text: str, voice: str = TTS_VOICE) -> str | None:
    """
    Synchronous version of text_to_speech_url.
    Use this if you're not in an async context.
    """
    return asyncio.run(text_to_speech_url(text, voice))


# ── Get available voices ──────────────────────────────────────────────────
def get_available_voices() -> dict:
    """Returns all available Orpheus English voices with descriptions."""
    return {
        "autumn": "Warm female — best for receptionist (recommended)",
        "diana":  "Professional female — formal tone",
        "hannah": "Friendly female — casual, approachable",
        "austin": "Calm male — neutral, clear",
        "daniel": "Professional male — formal tone",
        "troy":   "Energetic male — upbeat",
    }


# ── Cleanup old audio files ───────────────────────────────────────────────
def cleanup_old_audio(max_age_seconds: int = 3600):
    """Deletes WAV files older than max_age_seconds (default 1 hour)."""
    if not AUDIO_DIR.exists():
        return
    now     = time.time()
    deleted = 0
    for f in AUDIO_DIR.glob("aria_*.wav"):
        if now - f.stat().st_mtime > max_age_seconds:
            f.unlink()
            deleted += 1
    if deleted:
        logger.info(f"[TTS] Cleaned up {deleted} old audio files")


# ── Quick test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Groq Orpheus TTS Test ===")
    print(f"API Key set: {'YES ✅' if GROQ_API_KEY else 'NO ❌ — add GROQ_API_KEY to .env'}")
    print(f"Model:       {TTS_MODEL}")
    print(f"Voice:       {TTS_VOICE}")
    print(f"Free limit:  100 requests/day")

    print("\nAvailable voices:")
    for voice, desc in get_available_voices().items():
        marker = " ← currently selected" if voice == TTS_VOICE else ""
        print(f"  {voice:8} — {desc}{marker}")

    if not GROQ_API_KEY:
        print("\nGet a free key at: console.groq.com → API Keys")
        print("Then add to .env: GROQ_API_KEY=gsk_your-key")
        print("\nAlso add (optional): GROQ_TTS_VOICE=autumn")
    else:
        # ── IMPORTANT: Accept model terms first ──────────────────────────
        print("\n⚠️  BEFORE RUNNING: Make sure you accepted Orpheus model terms!")
        print("   Go to: console.groq.com → Playground → select 'Orpheus English'")
        print("   Click 'Accept Terms' if prompted. Only needed once.\n")

        test_text = (
            "Hello! Thank you for calling. This is Aria, your virtual receptionist. "
            "Your appointment has been confirmed for Tuesday at 3 PM. "
            "Your booking ID is A-P-T dash 2-8-4-7. "
            "I've also sent you a WhatsApp confirmation. "
            "Is there anything else I can help you with today?"
        )

        print(f"Generating speech for: '{test_text[:60]}...'")
        print("Please wait...")

        # Create audio dir for test
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        url = asyncio.run(text_to_speech_url(test_text))

        if url:
            print(f"\n✅ SUCCESS!")
            print(f"Audio URL: {url}")
            filename = url.split("/")[-1]
            local_path = AUDIO_DIR / filename
            print(f"Local file: {local_path}")
            print(f"\nTo play it (Windows):")
            print(f"  start {local_path}")
            print(f"\nTo play it (Mac/Linux):")
            print(f"  afplay {local_path}  OR  aplay {local_path}")
        else:
            print("\n❌ FAILED")
            print("Common fixes:")
            print("  1. Accept Orpheus model terms at console.groq.com")
            print("  2. Check GROQ_API_KEY in .env")
            print("  3. Check internet connection")
            print("  4. Free tier limit: 100 requests/day — may be exhausted")