"""
voice/twilio_handler.py  —  Raunit's file (migrated to Groq)
===========================================================
Webhooks for Twilio to handle incoming calls and process speech.

Exposes the following endpoints for Twilio:
  1. POST /incoming-call  —  Greet caller, start speech gather
  2. POST /process-speech —  Send transcript to LLM, play Groq TTS response
  3. POST /call-status    —  Handle cleanup when call ends
  4. GET  /status         —  Health check / debugging route
"""

import os
import sys
import json
import logging
from fastapi import APIRouter, Request, Form, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv

# Ensure voice/, root/, and ai/ are in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai")))

# Load environmental variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Import AI brain & voice pipelines ────────────────────────────────────
from voice.stt import transcribe_audio_url
from voice.tts import text_to_speech_url
from ai.agent import get_ai_response

# Active call sessions: CallSid -> list of message dicts (memory)
call_sessions = {}

# Default Twilio Polly voice parameters (used as fallback if Groq TTS fails/fails key check)
FALLBACK_VOICE = "Polly.Aditi"
FALLBACK_LANG = "en-IN"


# ── ROUTE 1 — /voice/incoming-call ───────────────────────────────────────
@router.post("/incoming-call")
async def incoming_call(request: Request):
    """Twilio hits this first when someone dials our number."""
    form     = await request.form()
    call_sid = form.get("CallSid", "")
    logger.info(f"[CALL RECEIVED] CallSid={call_sid} — initializing Aria...")

    # Start new session with empty memory
    call_sessions[call_sid] = []

    response = VoiceResponse()

    gather = Gather(
        input         = "speech",
        action        = "/voice/process-speech",
        method        = "POST",
        speech_timeout= "auto",
        speech_model  = "phone_call",
        language      = FALLBACK_LANG,
        timeout       = 5,
    )

    greeting_text = (
        "Hello! Thank you for calling. "
        "This is Aria, your virtual receptionist. "
        "How may I assist you today?"
    )

    # Synthesize greeting via Groq Orpheus
    audio_url = await text_to_speech_url(greeting_text)
    if audio_url:
        gather.play(audio_url)
    else:
        # Fallback to standard Twilio Polly
        gather.say(greeting_text, voice=FALLBACK_VOICE, language=FALLBACK_LANG)

    response.append(gather)

    # Fallback if caller says nothing at greeting
    no_input_text = "I'm sorry, I didn't catch that. Please call us back anytime. Goodbye!"
    fallback_audio = await text_to_speech_url(no_input_text)
    if fallback_audio:
        response.play(fallback_audio)
    else:
        response.say(no_input_text, voice=FALLBACK_VOICE)

    response.hangup()
    return Response(content=str(response), media_type="application/xml")


# ── ROUTE 2 — /voice/process-speech ──────────────────────────────────────
@router.post("/process-speech")
async def process_speech(
    request      : Request,
    SpeechResult : str = Form(default=""),
    CallSid      : str = Form(default=""),
    RecordingUrl : str = Form(default=""),
    Confidence   : str = Form(default="0"),
):
    """Twilio hits this after the caller finishes speaking."""
    logger.info(f"[SPEECH] CallSid={CallSid}  transcript='{SpeechResult}'  recording='{RecordingUrl}'")

    response  = VoiceResponse()

    # Step 1: Resolve the transcript using Groq Whisper STT (Option B) if audio URL is available
    if RecordingUrl:
        user_text = await transcribe_audio_url(RecordingUrl)
    else:
        # Fall back to Twilio's built-in transcription
        user_text = SpeechResult.strip()

    # Handle empty input
    if not user_text:
        gather = Gather(
            input         = "speech",
            action        = "/voice/process-speech",
            method        = "POST",
            speech_timeout= "auto",
            language      = FALLBACK_LANG,
            timeout       = 5,
        )
        silence_text = "I'm sorry, I didn't quite catch that. Could you please repeat what you said?"
        audio_url = await text_to_speech_url(silence_text)
        if audio_url:
            gather.play(audio_url)
        else:
            gather.say(silence_text, voice=FALLBACK_VOICE)
            
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    # Build conversation memory
    if CallSid not in call_sessions:
        call_sessions[CallSid] = []

    call_sessions[CallSid].append({"role": "user", "content": user_text})

    # Get response from Groq LLM (Llama 4 Scout)
    try:
        ai_reply = get_ai_response(call_sessions[CallSid])
    except Exception as e:
        logger.error(f"[AI ERROR] {e}")
        ai_reply = (
            "I'm experiencing a small technical issue right now. "
            "Please hold on or call us back in a moment."
        )

    logger.info(f"[AI REPLY] '{ai_reply}'")
    call_sessions[CallSid].append({"role": "assistant", "content": ai_reply})

    # Check for special routing flags
    end_call  = "##END_CALL##"  in ai_reply
    escalate  = "##ESCALATE##" in ai_reply
    ai_reply  = ai_reply.replace("##END_CALL##", "").replace("##ESCALATE##", "").strip()

    # Synthesize the response via Groq Orpheus
    reply_audio_url = await text_to_speech_url(ai_reply)

    # Build TwiML response
    if escalate:
        escalate_text = ai_reply + " Please hold while I connect you to our team."
        escalate_audio = await text_to_speech_url(escalate_text)
        if escalate_audio:
            response.play(escalate_audio)
        else:
            response.say(escalate_text, voice=FALLBACK_VOICE)
        
        # TODO: response.dial(os.getenv("HUMAN_AGENT_NUMBER"))
        response.hangup()

    elif end_call:
        if reply_audio_url:
            response.play(reply_audio_url)
        else:
            response.say(ai_reply, voice=FALLBACK_VOICE)
        response.hangup()
        call_sessions.pop(CallSid, None)

    else:
        gather = Gather(
            input         = "speech",
            action        = "/voice/process-speech",
            method        = "POST",
            speech_timeout= "auto",
            speech_model  = "phone_call",
            language      = FALLBACK_LANG,
            timeout       = 8,
        )
        if reply_audio_url:
            gather.play(reply_audio_url)
        else:
            gather.say(ai_reply, voice=FALLBACK_VOICE, language=FALLBACK_LANG)
        response.append(gather)

        # Handle silence after playing the reply
        silence_warning = "I apologise — I'm having a little trouble hearing you. Are you still there?"
        warning_audio = await text_to_speech_url(silence_warning)
        if warning_audio:
            response.play(warning_audio)
        else:
            response.say(silence_warning, voice=FALLBACK_VOICE)
            
        gather2 = Gather(
            input         = "speech",
            action        = "/voice/process-speech",
            method        = "POST",
            speech_timeout= "auto",
            language      = FALLBACK_LANG,
            timeout       = 5,
        )
        response.append(gather2)
        
        goodbye_text = "It seems like we may have lost the connection. Please feel free to call us back anytime. Have a wonderful day — goodbye!"
        goodbye_audio = await text_to_speech_url(goodbye_text)
        if goodbye_audio:
            response.play(goodbye_audio)
        else:
            response.say(goodbye_text, voice=FALLBACK_VOICE)
            
        response.hangup()

    return Response(content=str(response), media_type="application/xml")


# ── ROUTE 3 — /voice/call-status ─────────────────────────────────────────
@router.post("/call-status")
async def call_status(request: Request):
    """Twilio calls this when a call ends — used for logging."""
    form          = await request.form()
    call_sid      = form.get("CallSid",      "")
    status        = form.get("CallStatus",   "")
    duration      = form.get("CallDuration", "0")

    logger.info(f"[CALL ENDED] CallSid={call_sid}  Status={status}  Duration={duration}s")
    call_sessions.pop(call_sid, [])
    return {"received": True}


# ── ROUTE 4 — /voice/status (health check) ───────────────────────────────
@router.get("/status")
def voice_status():
    return {
        "status":       "voice pipeline ready",
        "active_calls": len(call_sessions),
        "voice": "autumn (Groq Orpheus)",
        "stt":          "Groq Whisper Large v3 Turbo",
        "tts":          "Groq Orpheus TTS",
    }
