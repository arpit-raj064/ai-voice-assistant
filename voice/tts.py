"""
voice/tts.py  —  Raunit's file (migrated to Groq)
--------------------------------------
Text-to-Speech module using Groq Orpheus TTS.

Available English voices on Groq Orpheus:
  - autumn (female)
  - diana (female)
  - hannah (female)
  - austin (male)
  - daniel (male)
  - troy (male)

Important notes:
  - Groq Orpheus supports max 200 characters per request.
  - To support longer responses, we split text into sentence-based chunks,
    request audio for each chunk, and concatenate the WAV files.
  - No external binary dependencies (ffmpeg/pydub) are required for WAV concatenation.
"""

import os
import re
import wave
import time
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TTS_MODEL = os.getenv("GROQ_TTS_MODEL", "canopylabs/orpheus-v1-english")
DEFAULT_VOICE = os.getenv("GROQ_TTS_VOICE", "troy")

# Map old ElevenLabs voice names/IDs to Groq Orpheus voices to avoid breaking twilio_handler
VOICE_IDS = {
    "rachel":  "diana",
    "adam":    "troy",
    "antoni":  "daniel",
    "default": "troy",
}

VOICES = ["autumn", "diana", "hannah", "austin", "daniel", "troy"]


def _get_groq_client():
    """Returns Groq client. Imported here to avoid circular imports."""
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


def get_twilio_voice_options() -> dict:
    """Returns available Twilio TTS voice options for fallback reference."""
    return {
        "indian_english_female": "Polly.Aditi",
        "indian_english_female2": "Polly.Raveena",
        "generic_english":       "alice",
        "language_code":         "en-IN",
        "usage": "gather.say('Your text here', voice='Polly.Aditi', language='en-IN')",
    }


def split_text_into_chunks(text: str, max_chars: int = 180) -> list[str]:
    """
    Splits text into chunks of <= max_chars size along sentence boundaries.
    If a sentence is too long, splits it along word boundaries.
    """
    if not text:
        return []
    
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_chunk = []
    current_len = 0
    
    for sentence in sentences:
        if len(sentence) > max_chars:
            # Output current chunk first if any
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0
            
            # Split the long sentence by spaces
            words = sentence.split(" ")
            sub_chunk = []
            sub_len = 0
            for word in words:
                if sub_len + len(word) + 1 > max_chars:
                    if sub_chunk:
                        chunks.append(" ".join(sub_chunk))
                    sub_chunk = [word]
                    sub_len = len(word)
                else:
                    sub_chunk.append(word)
                    sub_len += len(word) + 1
            if sub_chunk:
                current_chunk = sub_chunk
                current_len = sub_len
        else:
            if current_len + len(sentence) + (1 if current_chunk else 0) > max_chars:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_len = len(sentence)
            else:
                current_chunk.append(sentence)
                current_len += len(sentence) + (1 if current_chunk else 0)
                
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks


def concatenate_wav_files(input_files: list[Path], output_file: Path):
    """
    Concatenates a list of WAV files into a single WAV output file.
    Expects all input WAV files to have identical audio parameters.
    """
    if not input_files:
        return

    with wave.open(str(input_files[0]), 'rb') as first_file:
        params = first_file.getparams()
        
    with wave.open(str(output_file), 'wb') as output_file_obj:
        output_file_obj.setparams(params)
        for path in input_files:
            with wave.open(str(path), 'rb') as wav_file:
                output_file_obj.writeframes(wav_file.readframes(wav_file.getnframes()))


async def text_to_speech_url(
    text:     str,
    voice_id: str = VOICE_IDS["default"],
) -> str | None:
    """
    Converts text to speech using Groq Orpheus and returns a public URL.

    Args:
        text:     The text to speak
        voice_id: Groq voice name (e.g. troy, diana) or ElevenLabs compatible name

    Returns:
        Public URL string to the audio file, or None if failed
    """
    if not GROQ_API_KEY:
        logger.warning("[TTS] GROQ_API_KEY not set — falling back to Twilio TTS")
        return None

    if not text or not text.strip():
        logger.warning("[TTS] Empty text provided")
        return None

    # Resolve voice mapping if legacy ElevenLabs voice ID is passed
    voice = voice_id.lower()
    if voice in VOICE_IDS:
        voice = VOICE_IDS[voice]
    elif voice not in VOICES:
        # Check if the voice string itself maps directly
        found_mapped = False
        for k, v in VOICE_IDS.items():
            if k in voice or v in voice:
                voice = v
                found_mapped = True
                break
        if not found_mapped:
            voice = DEFAULT_VOICE

    # Project Root Setup
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    audio_dir = PROJECT_ROOT / "static" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    chunks = split_text_into_chunks(text)
    if not chunks:
        return None

    logger.info(f"[TTS] Generating speech using Groq Orpheus ({voice}) in {len(chunks)} chunks...")

    try:
        client = _get_groq_client()
        temp_files = []
        timestamp = int(time.time() * 1000)
        loop = asyncio.get_event_loop()

        for idx, chunk in enumerate(chunks):
            temp_path = audio_dir / f"temp_{timestamp}_{idx}.wav"
            
            # Execute the synchronous Groq API call in a thread pool (asyncio-friendly)
            response = await loop.run_in_executor(
                None,
                lambda: client.audio.speech.create(
                    model=TTS_MODEL,
                    voice=voice,
                    input=chunk
                )
            )
            
            # Write WAV content to temp file
            response.stream_to_file(temp_path)
            temp_files.append(temp_path)

        final_filename = f"reply_{timestamp}.wav"
        final_path = audio_dir / final_filename

        if len(temp_files) == 1:
            temp_files[0].rename(final_path)
        else:
            # Concatenate WAV files
            concatenate_wav_files(temp_files, final_path)
            # Cleanup temp files
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()

        logger.info(f"[TTS] Audio saved: {final_path} (from {len(chunks)} chunks)")

        base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
        audio_url = f"{base_url}/static/audio/{final_filename}"
        logger.info(f"[TTS] Public URL: {audio_url}")
        return audio_url

    except Exception as e:
        logger.error(f"[TTS] Groq Orpheus synthesis failed: {e}")
        # Cleanup any remaining temp files
        if 'temp_files' in locals():
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()
        return None


def cleanup_old_audio(max_age_seconds: int = 3600):
    """Deletes audio files older than max_age_seconds (default: 1 hour)."""
    import time
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    audio_dir = PROJECT_ROOT / "static" / "audio"
    if not audio_dir.exists():
        return
 
    now     = time.time()
    deleted = 0
    for f in audio_dir.glob("*.wav"):
        if now - f.stat().st_mtime > max_age_seconds:
            f.unlink()
            deleted += 1
 
    if deleted:
        logger.info(f"[TTS cleanup] Deleted {deleted} old audio files")


# ── Quick test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Groq Orpheus TTS Test ===")
    print(f"API Key set: {'YES' if GROQ_API_KEY else 'NO — add GROQ_API_KEY to .env!'}")
    print(f"Model:       {TTS_MODEL}")
    print(f"Voice:       {DEFAULT_VOICE}")
 
    if not GROQ_API_KEY:
        print("\nERROR: Set GROQ_API_KEY in .env first.")
    else:
        # Use a long text to test chunking + concatenation
        test_text = (
            "Hello! I am your AI receptionist assistant, powered by Groq Orpheus TTS. "
            "Your appointment for Tuesday at three PM has been successfully confirmed. "
            "We look forward to welcoming you to our clinic. Please let us know if you need to reschedule."
        )
        print(f"\nGenerating audio for: '{test_text}'")
        url = asyncio.run(text_to_speech_url(test_text))
        if url:
            print(f"\nSUCCESS! Audio saved. URL: {url}")
        else:
            print("\nFAILED — check API key and internet connection.")