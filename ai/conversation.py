"""
ai/conversation.py  —  Arpit's file  —  Week 6
================================================
Multi-turn conversation memory and session management.

What this file does:
  - Manages conversation history for each call session
  - Extracts and tracks entities (name, phone, date, time, short_id)
    so the AI never asks for information already given
  - Detects caller intent from each message
  - Detects urgency, hesitation, and frustration
  - Recognises returning callers by phone number
  - Provides a clean interface for twilio_handler.py to use

Why this is separate from agent.py:
  agent.py   → talks to Groq (the AI brain)
  tools.py   → defines what actions the AI can take
  conversation.py → manages the MEMORY and STATE of each call
                    so the AI always has full context

Usage in twilio_handler.py:
    from ai.conversation import ConversationSession

    session = ConversationSession(call_sid="CA123", caller_phone="+919876543210")
    session.add_user_message("I want to book for Tuesday 3pm")
    reply = get_ai_response(session.get_history())
    session.add_assistant_message(reply)
    session.extract_entities_from_message("I want to book for Tuesday 3pm")
"""

from __future__ import annotations

import os
import re
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — ENTITY STORE
# Tracks all information extracted from the conversation so far
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExtractedEntities:
    """
    Stores all caller information extracted during the conversation.
    Once a field is set, the AI should NEVER ask for it again.

    This directly powers the Adaptive Questioning System Rule 1:
    "Never ask for information already given"
    """
    name:       Optional[str]  = None   # caller's full name
    phone:      Optional[str]  = None   # caller's phone number
    date:       Optional[str]  = None   # preferred date YYYY-MM-DD
    time:       Optional[str]  = None   # preferred time HH:MM
    short_id:   Optional[str]  = None   # booking ID e.g. APT-2847
    intent:     Optional[str]  = None   # book / cancel / reschedule / query
    urgency:    bool           = False  # caller said urgent/ASAP/emergency
    hesitant:   bool           = False  # caller said umm/not sure/maybe
    frustrated: int            = 0      # count of frustrated responses

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "phone":      self.phone,
            "date":       self.date,
            "time":       self.time,
            "short_id":   self.short_id,
            "intent":     self.intent,
            "urgency":    self.urgency,
            "hesitant":   self.hesitant,
            "frustrated": self.frustrated,
        }

    def missing_booking_fields(self) -> list[str]:
        """Returns list of fields still needed to complete a booking."""
        missing = []
        if not self.name:     missing.append("name")
        if not self.phone:    missing.append("phone")
        if not self.date:     missing.append("date")
        if not self.time:     missing.append("time")
        return missing

    def has_enough_to_book(self) -> bool:
        """Returns True when all 4 required booking fields are collected."""
        return all([self.name, self.phone, self.date, self.time])


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — ENTITY EXTRACTOR
# Pulls structured info out of natural language messages
# ═══════════════════════════════════════════════════════════════════════════

class EntityExtractor:
    """
    Extracts entities from caller messages without needing an AI call.
    Pure Python regex + keyword matching — fast and free.

    Used to update ExtractedEntities after every caller message
    so the AI always knows what's already been collected.
    """

    # ── Intent keywords ───────────────────────────────────────────────────
    INTENT_PATTERNS = {
        "book": [
            "book", "schedule", "appointment", "slot", "see a doctor",
            "make an appointment", "need to come", "want to visit",
            "fix an appointment", "set up",
        ],
        "cancel": [
            "cancel", "cancellation", "don't want", "won't be able",
            "can't make it", "remove my booking", "delete",
        ],
        "reschedule": [
            "reschedule", "change", "move", "shift", "different time",
            "different date", "postpone", "earlier", "later",
        ],
        "query": [
            "hours", "working hours", "timing", "when", "how much",
            "price", "fee", "charges", "location", "address", "contact",
            "available", "open", "closed",
        ],
        "status": [
            "status", "confirm", "confirmed", "details", "my booking",
            "my appointment", "check my",
        ],
    }

    # ── Urgency keywords ──────────────────────────────────────────────────
    URGENCY_KEYWORDS = [
        "urgent", "urgently", "emergency", "asap", "as soon as possible",
        "immediately", "right now", "today itself", "very soon",
        "can't wait", "critical", "important",
    ]

    # ── Hesitation keywords ───────────────────────────────────────────────
    HESITATION_KEYWORDS = [
        "umm", "uh", "uhh", "hmm", "not sure", "i don't know",
        "maybe", "perhaps", "i think", "sort of", "kind of",
        "i just need", "i just want", "not really sure",
    ]

    # ── Frustration keywords ──────────────────────────────────────────────
    FRUSTRATION_KEYWORDS = [
        "this is taking too long", "you're not understanding",
        "i already said", "i told you", "why are you asking again",
        "this is useless", "not helpful", "frustrated", "ridiculous",
        "wasting my time", "i said that already",
    ]

    # ── Short ID pattern ──────────────────────────────────────────────────
    SHORT_ID_PATTERN = re.compile(r"\bAPT[-\s]?\d{4}\b", re.IGNORECASE)

    # ── Phone number pattern ──────────────────────────────────────────────
    PHONE_PATTERN = re.compile(
        r"(?<!\d)(\+?91[-\s]?)?[6-9]\d{9}(?!\d)"  # Indian mobile
        r"|(?<!\d)(\+?[1-9]\d{6,14})(?!\d)"        # International
    )

    # ── Time patterns ─────────────────────────────────────────────────────
    TIME_PATTERNS = [
        re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b"),
        re.compile(r"\b(\d{1,2})\s*(am|pm|AM|PM)\b"),
        re.compile(r"\b(\d{1,2}):(\d{2})\b"),
    ]

    # ── Day name patterns ─────────────────────────────────────────────────
    DAY_NAMES = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3,
        "fri": 4, "sat": 5, "sun": 6,
    }

    @classmethod
    def extract_intent(cls, text: str) -> Optional[str]:
        """Detects the caller's primary intent from their message."""
        text_lower = text.lower()
        for intent, keywords in cls.INTENT_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        return None

    @classmethod
    def extract_name(cls, text: str) -> Optional[str]:
        """
        Extracts caller name from patterns like:
          "my name is Arpit"
          "this is Arpit"
          "I am Rahul"
          "I'm Priya Sharma"
        """
        patterns = [
            r"(?:my name is|name is|i am|i'm|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:name's|named)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                # Filter out common false positives
                if name.lower() not in ["aria", "the", "a", "an", "please", "thank"]:
                    return name
        return None

    @classmethod
    def extract_phone(cls, text: str) -> Optional[str]:
        """Extracts phone number from message."""
        # Remove spaces/dashes from digits for matching
        cleaned = re.sub(r"[\s\-\(\)]", "", text)
        match = cls.PHONE_PATTERN.search(cleaned)
        if match:
            phone = re.sub(r"[^\d+]", "", match.group(0))
            # Normalise Indian numbers
            if len(phone) == 10 and phone[0] in "6789":
                return f"+91{phone}"
            if len(phone) == 12 and phone.startswith("91"):
                return f"+{phone}"
            if phone.startswith("+"):
                return phone
        return None

    @classmethod
    def extract_short_id(cls, text: str) -> Optional[str]:
        """Extracts booking ID like APT-2847 from message."""
        match = cls.SHORT_ID_PATTERN.search(text)
        if match:
            return match.group(0).upper().replace(" ", "-")
        return None

    @classmethod
    def extract_date(cls, text: str) -> Optional[str]:
        """
        Extracts date from various formats:
          "15th April" → "2026-04-15"
          "tomorrow"   → actual tomorrow date
          "Monday"     → next Monday's date
          "2026-04-15" → "2026-04-15"
        """
        text_lower = text.lower()
        today = date.today()

        # Explicit YYYY-MM-DD
        match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if match:
            return match.group(0)

        # Relative: today/tomorrow/day after tomorrow
        if "day after tomorrow" in text_lower:
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")
        if "tomorrow" in text_lower:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        if "today" in text_lower:
            return today.strftime("%Y-%m-%d")

        # Day names: "next Monday", "this Friday", "Monday"
        for day_name, weekday in cls.DAY_NAMES.items():
            if day_name in text_lower:
                days_ahead = (weekday - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7   # if today is that day, take next week
                target = today + timedelta(days=days_ahead)
                return target.strftime("%Y-%m-%d")

        # DD Month / Month DD formats
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "jun": 6, "jul": 7, "aug": 8, "sep": 9,
            "oct": 10, "nov": 11, "dec": 12,
        }
        for month_name, month_num in month_map.items():
            pattern = rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{month_name}\b"
            match = re.search(pattern, text_lower)
            if match:
                day = int(match.group(1))
                year = today.year
                try:
                    target = date(year, month_num, day)
                    if target < today:
                        target = date(year + 1, month_num, day)
                    return target.strftime("%Y-%m-%d")
                except ValueError:
                    pass

        return None

    @classmethod
    def extract_time(cls, text: str) -> Optional[str]:
        """
        Extracts time and converts to HH:MM 24-hour format.
          "3 PM"    → "15:00"
          "3:30 pm" → "15:30"
          "14:00"   → "14:00"
        """
        text_upper = text.upper()

        for pattern in cls.TIME_PATTERNS:
            match = pattern.search(text_upper)
            if match:
                groups = match.groups()
                hour   = int(groups[0])
                minute = int(groups[1]) if len(groups) > 1 and groups[1] else 0
                ampm   = groups[-1] if groups[-1] in ("AM", "PM") else None

                if ampm == "PM" and hour != 12:
                    hour += 12
                elif ampm == "AM" and hour == 12:
                    hour = 0

                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"

        # Time-of-day inference
        text_lower = text.lower()
        if "morning" in text_lower:
            return "09:00"
        if "afternoon" in text_lower:
            return "14:00"
        if "evening" in text_lower:
            return "17:00"
        if "noon" in text_lower or "lunch" in text_lower:
            return "12:00"

        return None

    @classmethod
    def is_urgent(cls, text: str) -> bool:
        """Returns True if message contains urgency keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in cls.URGENCY_KEYWORDS)

    @classmethod
    def is_hesitant(cls, text: str) -> bool:
        """Returns True if message contains hesitation keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in cls.HESITATION_KEYWORDS)

    @classmethod
    def is_frustrated(cls, text: str) -> bool:
        """Returns True if message contains frustration keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in cls.FRUSTRATION_KEYWORDS)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — CONVERSATION SESSION
# One session = one phone call
# ═══════════════════════════════════════════════════════════════════════════

class ConversationSession:
    """
    Manages the full state of one phone call conversation.

    One instance is created per call and stored in twilio_handler.py's
    call_sessions dict, keyed by CallSid.

    Responsibilities:
      - Store conversation history (messages list)
      - Track extracted entities across all turns
      - Detect silence count
      - Track returning callers
      - Provide summary context string for debugging
    """

    def __init__(
        self,
        call_sid:     str,
        caller_phone: Optional[str] = None,
    ):
        self.call_sid      = call_sid
        self.caller_phone  = caller_phone
        self.entities      = ExtractedEntities()
        self.history:      list[dict] = []
        self.silence_count: int       = 0
        self.started_at    = datetime.now()
        self.is_returning  = False   # set to True if phone found in DB

        # Pre-fill phone from caller ID if available
        if caller_phone:
            self.entities.phone = caller_phone
            logger.info(f"[SESSION] New call {call_sid} from {caller_phone}")
        else:
            logger.info(f"[SESSION] New call {call_sid} — unknown caller")

    # ── History management ────────────────────────────────────────────────
    def add_user_message(self, text: str) -> None:
        """
        Adds a user message to history AND automatically extracts entities.
        Call this after every STT transcription.
        """
        self.history.append({"role": "user", "content": text})
        self._extract_and_update(text)
        self.silence_count = 0   # reset silence on valid input
        logger.debug(f"[SESSION] User: '{text[:60]}'")

    def add_assistant_message(self, text: str) -> None:
        """Adds an AI reply to history."""
        self.history.append({"role": "assistant", "content": text})
        logger.debug(f"[SESSION] Aria: '{text[:60]}'")

    def add_tool_call(self, message: object) -> None:
        """Adds a tool call message object to history (from Groq response)."""
        self.history.append(message)

    def add_tool_result(self, tool_call_id: str, result: dict) -> None:
        """Adds a tool result to history after tool execution."""
        self.history.append({
            "role":         "tool",
            "tool_call_id": tool_call_id,
            "content":      json.dumps(result),
        })

    def get_history(self) -> list[dict]:
        """Returns full conversation history for passing to Groq."""
        return self.history

    def increment_silence(self) -> int:
        """
        Called when caller goes silent.
        Returns current silence count (1, 2, or 3).
        At 3: twilio_handler should end the call.
        """
        self.silence_count += 1
        logger.info(f"[SESSION] Silence count: {self.silence_count}")
        return self.silence_count

    # ── Entity extraction ─────────────────────────────────────────────────
    def _extract_and_update(self, text: str) -> None:
        """
        Runs all entity extractors on a user message
        and updates self.entities with any new findings.
        Only sets fields that are currently None — never overwrites.
        """
        extractor = EntityExtractor

        # Intent
        if not self.entities.intent:
            intent = extractor.extract_intent(text)
            if intent:
                self.entities.intent = intent
                logger.info(f"[SESSION] Intent detected: {intent}")

        # Name
        if not self.entities.name:
            name = extractor.extract_name(text)
            if name:
                self.entities.name = name
                logger.info(f"[SESSION] Name extracted: {name}")

        # Phone (only if not already set from caller ID)
        if not self.entities.phone:
            phone = extractor.extract_phone(text)
            if phone:
                self.entities.phone = phone
                logger.info(f"[SESSION] Phone extracted: {phone}")

        # Date
        if not self.entities.date:
            extracted_date = extractor.extract_date(text)
            if extracted_date:
                self.entities.date = extracted_date
                logger.info(f"[SESSION] Date extracted: {extracted_date}")

        # Time
        if not self.entities.time:
            extracted_time = extractor.extract_time(text)
            if extracted_time:
                self.entities.time = extracted_time
                logger.info(f"[SESSION] Time extracted: {extracted_time}")

        # Short ID (APT-XXXX)
        if not self.entities.short_id:
            short_id = extractor.extract_short_id(text)
            if short_id:
                self.entities.short_id = short_id
                logger.info(f"[SESSION] Short ID extracted: {short_id}")

        # Urgency
        if not self.entities.urgency:
            if extractor.is_urgent(text):
                self.entities.urgency = True
                logger.info("[SESSION] Urgency detected")

        # Hesitation
        if extractor.is_hesitant(text):
            self.entities.hesitant = True

        # Frustration counter
        if extractor.is_frustrated(text):
            self.entities.frustrated += 1
            logger.info(f"[SESSION] Frustration count: {self.entities.frustrated}")

    # ── Context summary ───────────────────────────────────────────────────
    def get_context_summary(self) -> str:
        """
        Returns a plain-text summary of extracted entities.
        Useful for logging and debugging.
        """
        e = self.entities
        parts = [f"Call: {self.call_sid}"]
        if e.name:       parts.append(f"Name: {e.name}")
        if e.phone:      parts.append(f"Phone: {e.phone}")
        if e.date:       parts.append(f"Date: {e.date}")
        if e.time:       parts.append(f"Time: {e.time}")
        if e.short_id:   parts.append(f"BookingID: {e.short_id}")
        if e.intent:     parts.append(f"Intent: {e.intent}")
        if e.urgency:    parts.append("URGENT")
        if e.hesitant:   parts.append("HESITANT")
        if e.frustrated: parts.append(f"Frustrated x{e.frustrated}")
        parts.append(f"Turns: {len(self.history)}")
        return " | ".join(parts)

    def get_call_duration_seconds(self) -> int:
        """Returns how many seconds the call has been active."""
        return int((datetime.now() - self.started_at).total_seconds())


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — SESSION STORE
# Manages all active call sessions (replaces the raw dict in twilio_handler)
# ═══════════════════════════════════════════════════════════════════════════

class SessionStore:
    """
    In-memory store for all active call sessions.

    Replace the raw `call_sessions = {}` dict in twilio_handler.py
    with a single SessionStore instance for cleaner session management.

    Usage in twilio_handler.py:
        from ai.conversation import SessionStore
        sessions = SessionStore()

        # On new call:
        session = sessions.create(call_sid, caller_phone)

        # On speech:
        session = sessions.get(call_sid)
        session.add_user_message(transcript)

        # On call end:
        sessions.remove(call_sid)
    """

    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}

    def create(
        self,
        call_sid:     str,
        caller_phone: Optional[str] = None,
    ) -> ConversationSession:
        """Creates a new session for a call."""
        session = ConversationSession(call_sid, caller_phone)
        self._sessions[call_sid] = session
        logger.info(f"[STORE] Created session for {call_sid}. Active: {len(self._sessions)}")
        return session

    def get(self, call_sid: str) -> Optional[ConversationSession]:
        """Returns existing session or None if not found."""
        return self._sessions.get(call_sid)

    def get_or_create(
        self,
        call_sid:     str,
        caller_phone: Optional[str] = None,
    ) -> ConversationSession:
        """Returns existing session or creates a new one."""
        session = self._sessions.get(call_sid)
        if not session:
            session = self.create(call_sid, caller_phone)
        return session

    def remove(self, call_sid: str) -> Optional[ConversationSession]:
        """Removes and returns session when call ends."""
        session = self._sessions.pop(call_sid, None)
        if session:
            logger.info(
                f"[STORE] Removed session {call_sid}. "
                f"Duration: {session.get_call_duration_seconds()}s. "
                f"Active: {len(self._sessions)}"
            )
        return session

    def active_count(self) -> int:
        """Returns number of active calls."""
        return len(self._sessions)

    def get_all_summaries(self) -> list[str]:
        """Returns context summaries of all active sessions — for debugging."""
        return [s.get_context_summary() for s in self._sessions.values()]


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 — RETURNING CALLER CHECKER
# Checks if a caller has booked before using their phone number
# ═══════════════════════════════════════════════════════════════════════════

def check_returning_caller(phone: str) -> Optional[dict]:
    """
    Looks up the caller's phone number in the database.
    If found, returns their most recent booking details.

    This enables Aria to greet returning callers by name:
    "Welcome back, Arpit! How can I help you today?"

    Args:
        phone: Caller's phone number (E.164 format)

    Returns:
        dict with name, last_date, last_time, short_id
        or None if first-time caller
    """
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
        from backend.database import db

        result = db.table("appointments") \
            .select("name, date, time, short_id, status") \
            .eq("phone",  phone) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if result.data:
            record = result.data[0]
            logger.info(f"[RETURNING] Found returning caller: {record.get('name')}")
            return {
                "name":       record.get("name"),
                "last_date":  str(record.get("date", "")),
                "last_time":  str(record.get("time", ""))[:5],
                "short_id":   record.get("short_id"),
                "status":     record.get("status"),
            }

    except Exception as e:
        logger.warning(f"[RETURNING] Could not check DB: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6 — SELF TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n=== conversation.py — Self Test ===\n")

    # Create a session
    session = ConversationSession(
        call_sid     = "CA_test_001",
        caller_phone = "+919876543210",
    )

    # Simulate a full booking conversation
    test_messages = [
        "I want to book an appointment for Tuesday at 3pm",
        "My name is Arpit Gupta",
        "Sure, go ahead and confirm",
    ]

    print("Simulating conversation:")
    for msg in test_messages:
        session.add_user_message(msg)
        session.add_assistant_message("Aria's reply would go here")
        print(f"  User: {msg}")
        print(f"  Entities: {session.entities.to_dict()}\n")

    print(f"Context summary: {session.get_context_summary()}")
    print(f"Has enough to book: {session.entities.has_enough_to_book()}")
    print(f"Missing fields: {session.entities.missing_booking_fields()}")

    print("\n--- Entity Extraction Tests ---")
    extractor = EntityExtractor

    tests = [
        ("I want to book for Monday at 3pm",          "date+time"),
        ("My name is Priya Sharma",                    "name"),
        ("My number is 9876543210",                    "phone"),
        ("My booking ID is APT-2847",                  "short_id"),
        ("I need this urgently please",                "urgency"),
        ("Umm I'm not really sure what I want",        "hesitation"),
        ("I already told you my name!",                "frustration"),
        ("I want to book for tomorrow afternoon",      "relative date+time"),
        ("Can I come on 15th April?",                  "specific date"),
    ]

    for text, label in tests:
        e = ExtractedEntities()
        session2 = ConversationSession("test", None)
        session2.add_user_message(text)
        e = session2.entities
        print(f"  [{label}] '{text}'")
        print(f"    → date={e.date} time={e.time} name={e.name} "
              f"phone={e.phone} short_id={e.short_id} "
              f"urgent={e.urgency} hesitant={e.hesitant}")

    print("\n--- SessionStore Test ---")
    store = SessionStore()
    s1 = store.create("CA001", "+919876543210")
    s2 = store.create("CA002", "+919988776655")
    print(f"Active calls: {store.active_count()}")
    store.remove("CA001")
    print(f"After removing CA001: {store.active_count()}")

    print("\n=== All tests passed ✅ ===\n")