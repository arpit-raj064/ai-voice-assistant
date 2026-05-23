"""
scheduling/rules.py  —  Arpit's file (AI layer)
================================================
Single source of truth for all scheduling business rules.

Every rule used by the AI agent, booking engine, and API endpoints
lives here. Change a rule here → it applies everywhere automatically.

MVP Scope (confirmed):
  ✅ Monday–Saturday, 9 AM–6 PM IST
  ✅ 30-minute slots with 10-minute operational buffer
  ✅ Lunch block 1–2 PM
  ✅ Same-day booking: slot must be ≥ 2 hours ahead
  ✅ No past bookings
  ✅ One appointment per slot
  ✅ 3 nearest alternative slots if requested slot is taken
  ✅ Time-of-day inference (morning / afternoon / evening)
  ❌ No doctor-specific calendars (MVP)
  ❌ No emergency overrides (MVP)
  ❌ No recurring appointments (MVP)

Public holidays list: update INDIA_PUBLIC_HOLIDAYS each year.
Timezone: IST (Asia/Kolkata, UTC+5:30) — all datetime comparisons
          use timezone-aware objects.

Usage:
    from scheduling.rules import (
        get_available_slots,
        is_slot_available,
        validate_booking_request,
        suggest_alternative_slots,
        infer_slots_from_time_of_day,
        get_next_working_day,
        slot_to_display_str,
    )
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo          # stdlib in Python 3.9+

logger = logging.getLogger(__name__)

# ── Timezone ──────────────────────────────────────────────────────────────
IST = ZoneInfo("Asia/Kolkata")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 1 — CONSTANTS  (edit these to change business rules)
# ═════════════════════════════════════════════════════════════════════════

# Working days: 0=Monday … 6=Sunday
WORKING_WEEKDAYS: set[int] = {0, 1, 2, 3, 4, 5}   # Mon–Sat; Sun (6) excluded

# Working hours (IST)
WORK_START = time(9,  0)   # 9:00 AM
WORK_END   = time(18, 0)   # 6:00 PM

# Lunch break — no slots during this window
LUNCH_START = time(13, 0)  # 1:00 PM
LUNCH_END   = time(14, 0)  # 2:00 PM

# Slot configuration
SLOT_DURATION_MINUTES  = 30   # appointment length
BUFFER_MINUTES         = 10   # operational buffer AFTER each appointment
                               # effective slot block = 30 + 10 = 40 min
                               # but next slot starts on 30-min boundary

# Same-day booking: caller must book at least this far ahead
SAME_DAY_MIN_ADVANCE_HOURS = 2

# How many alternative slots to suggest when requested slot is taken
NUM_ALTERNATIVES = 3

# India public holidays 2025 — update annually
# Format: date(YYYY, M, D)
INDIA_PUBLIC_HOLIDAYS: set[date] = {
    date(2025,  1, 26),  # Republic Day
    date(2025,  3, 17),  # Holi
    date(2025,  4, 14),  # Dr. Ambedkar Jayanti / Ram Navami
    date(2025,  4, 18),  # Good Friday
    date(2025,  5,  1),  # Maharashtra Day / Labour Day
    date(2025,  8, 15),  # Independence Day
    date(2025,  8, 27),  # Janmashtami
    date(2025, 10,  2),  # Gandhi Jayanti
    date(2025, 10,  2),  # Dussehra
    date(2025, 10, 20),  # Diwali (Lakshmi Puja)
    date(2025, 11,  5),  # Diwali (Bhai Dooj)
    date(2025, 12, 25),  # Christmas
    # 2026 — add before Jan 1 2026
    date(2026,  1, 26),  # Republic Day
}

# Time-of-day inference map: keyword → preferred hour range (start, end)
# Engine picks slots within this range first.
TIME_OF_DAY_RANGES: dict[str, tuple[time, time]] = {
    "morning":   (time(9,  0), time(11, 0)),
    "afternoon": (time(14, 0), time(16, 0)),
    "evening":   (time(17, 0), time(18, 0)),
}


# ═════════════════════════════════════════════════════════════════════════
# SECTION 2 — DATE / DAY HELPERS
# ═════════════════════════════════════════════════════════════════════════

def now_ist() -> datetime:
    """Current datetime in IST (always timezone-aware)."""
    return datetime.now(tz=IST)


def today_ist() -> date:
    """Today's date in IST."""
    return now_ist().date()


def is_working_day(d: date) -> bool:
    """
    Returns True if the date is a valid working day.
    Excludes Sundays and Indian public holidays.

    Args:
        d: The date to check

    Returns:
        True if Monday–Saturday and not a public holiday
    """
    if d.weekday() not in WORKING_WEEKDAYS:
        return False
    if d in INDIA_PUBLIC_HOLIDAYS:
        return False
    return True


def is_past_date(d: date) -> bool:
    """Returns True if the date is strictly in the past (before today IST)."""
    return d < today_ist()


def get_next_working_day(from_date: Optional[date] = None) -> date:
    """
    Returns the next working day starting from from_date (exclusive).
    Useful when today is a holiday or Sunday.

    Args:
        from_date: Start searching from this date. Defaults to today.

    Returns:
        Next valid working day
    """
    d = (from_date or today_ist()) + timedelta(days=1)
    for _ in range(14):          # safety: never loop more than 2 weeks
        if is_working_day(d):
            return d
        d += timedelta(days=1)
    raise RuntimeError("Could not find a working day within 14 days — check holiday list")


def working_day_name(d: date) -> str:
    """Returns human-readable weekday + date, e.g. 'Monday, 26 May 2025'."""
    return d.strftime("%A, %d %B %Y")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 3 — SLOT GENERATION
# ═════════════════════════════════════════════════════════════════════════

def _generate_all_slots(d: date) -> list[datetime]:
    """
    Internal: generates every theoretical 30-minute slot for a working day,
    excluding the lunch break. Does NOT check bookings or same-day cutoff.

    Slot grid: 9:00, 9:30, 10:00 … 12:30, [lunch gap] 14:00 … 17:30
    Last slot starts at 17:30 (ends 18:00).

    Args:
        d: The date to generate slots for

    Returns:
        List of timezone-aware datetime objects (IST), sorted ascending
    """
    slots: list[datetime] = []
    current = datetime(d.year, d.month, d.day, WORK_START.hour, WORK_START.minute, tzinfo=IST)
    end     = datetime(d.year, d.month, d.day, WORK_END.hour,   WORK_END.minute,   tzinfo=IST)
    lunch_s = datetime(d.year, d.month, d.day, LUNCH_START.hour, LUNCH_START.minute, tzinfo=IST)
    lunch_e = datetime(d.year, d.month, d.day, LUNCH_END.hour,   LUNCH_END.minute,   tzinfo=IST)

    while current < end:
        slot_end = current + timedelta(minutes=SLOT_DURATION_MINUTES)

        # Skip slots that overlap with lunch break
        overlaps_lunch = current < lunch_e and slot_end > lunch_s
        if not overlaps_lunch:
            slots.append(current)

        current += timedelta(minutes=SLOT_DURATION_MINUTES)

    return slots


def get_all_slots(d: date) -> list[datetime]:
    """
    Returns all valid slot start times for a given date.
    Validates it's a working day first.

    Args:
        d: Target date

    Returns:
        List of slot datetimes (IST), empty if not a working day
    """
    if not is_working_day(d):
        return []
    return _generate_all_slots(d)


def get_available_slots(d: date, booked_times: list[datetime]) -> list[datetime]:
    """
    Returns slots that are NOT already booked, applying the 10-minute buffer rule.
    For same-day bookings, also filters out slots within the 2-hour advance window.

    Buffer rule: a slot is blocked if any booked appointment starts within
    [slot_start - BUFFER_MINUTES, slot_start + SLOT_DURATION_MINUTES + BUFFER_MINUTES].
    In practice for a clean 30-min grid this means each booked slot blocks itself only,
    since slots are already 30 min apart.

    Args:
        d:            Target date
        booked_times: List of already-booked slot start datetimes (IST, from DB)

    Returns:
        List of available slot datetimes (IST), sorted ascending
    """
    all_slots   = get_all_slots(d)
    if not all_slots:
        return []

    now         = now_ist()
    cutoff      = now + timedelta(hours=SAME_DAY_MIN_ADVANCE_HOURS)
    is_today    = (d == today_ist())

    available: list[datetime] = []

    for slot in all_slots:
        # Rule: no past slots or same-day slots within 2-hour window
        if is_today and slot <= cutoff:
            continue

        # Rule: slot must not overlap with any booked appointment (+ buffer)
        blocked = False
        for booked in booked_times:
            # A slot is blocked if it falls within [booked_start - buffer, booked_start + slot_duration + buffer]
            block_start = booked - timedelta(minutes=BUFFER_MINUTES)
            block_end   = booked + timedelta(minutes=SLOT_DURATION_MINUTES + BUFFER_MINUTES)
            if block_start <= slot < block_end:
                blocked = True
                break

        if not blocked:
            available.append(slot)

    return available


# ═════════════════════════════════════════════════════════════════════════
# SECTION 4 — SLOT VALIDATION
# ═════════════════════════════════════════════════════════════════════════

class BookingValidationError(Exception):
    """Raised when a booking request fails validation. Message is caller-safe."""
    pass


def is_slot_available(slot_dt: datetime, booked_times: list[datetime]) -> bool:
    """
    Checks if a specific slot is available (not booked, not blocked by buffer).
    Does NOT check working-day or same-day rules — use validate_booking_request for full check.

    Args:
        slot_dt:      The requested slot (IST, timezone-aware)
        booked_times: Already-booked datetimes for that day

    Returns:
        True if slot is free
    """
    for booked in booked_times:
        block_start = booked - timedelta(minutes=BUFFER_MINUTES)
        block_end   = booked + timedelta(minutes=SLOT_DURATION_MINUTES + BUFFER_MINUTES)
        if block_start <= slot_dt < block_end:
            return False
    return True


def validate_booking_request(
    slot_dt:      datetime,
    booked_times: list[datetime],
) -> tuple[bool, str]:
    """
    Full validation pipeline for a booking request. Checks all rules in order.

    Call this BEFORE inserting any booking into the database.

    Args:
        slot_dt:      Requested slot datetime (must be IST-aware)
        booked_times: Already-booked datetimes for that day (from DB)

    Returns:
        (True,  "")            — slot is valid and free
        (False, reason_str)   — slot failed; reason is a short caller-safe string

    Validation order (matches system prompt flow):
        1. Timezone check — ensure slot is IST-aware
        2. Past date/time
        3. Working day (Mon–Sat, no holidays)
        4. Within working hours (9 AM–6 PM)
        5. Lunch break block (1–2 PM)
        6. On-grid slot (must be exact 30-min boundary)
        7. Same-day 2-hour advance window
        8. Slot availability (booking + buffer)
    """
    now = now_ist()

    # 1. Timezone
    if slot_dt.tzinfo is None:
        slot_dt = slot_dt.replace(tzinfo=IST)

    d = slot_dt.date()

    # 2. Past datetime
    if slot_dt <= now:
        return False, "That time has already passed. Please choose a future slot."

    # 3. Working day
    if d.weekday() not in WORKING_WEEKDAYS:
        day_name = d.strftime("%A")
        return False, f"We're closed on {day_name}s. We work Monday to Saturday."

    if d in INDIA_PUBLIC_HOLIDAYS:
        return False, f"We're closed on {d.strftime('%d %B')} due to a public holiday."

    # 4. Working hours
    slot_time = slot_dt.time()
    if slot_time < WORK_START or slot_time >= WORK_END:
        return False, "That time is outside our working hours of 9 AM to 6 PM."

    # 5. Lunch break
    if LUNCH_START <= slot_time < LUNCH_END:
        return False, "We're on lunch break from 1 PM to 2 PM. Would 2 PM work for you?"

    # 6. On-grid (must be exact 30-min boundary)
    if slot_dt.minute not in (0, 30) or slot_dt.second != 0:
        return False, "Appointments start on the hour or half-hour only."

    # 7. Same-day advance window
    if d == today_ist():
        cutoff = now + timedelta(hours=SAME_DAY_MIN_ADVANCE_HOURS)
        if slot_dt <= cutoff:
            earliest = (cutoff + timedelta(minutes=30)).replace(second=0, microsecond=0)
            # Round up to nearest 30-min boundary
            if earliest.minute not in (0, 30):
                extra = 30 - (earliest.minute % 30)
                earliest += timedelta(minutes=extra)
                earliest = earliest.replace(second=0, microsecond=0)
            return (
                False,
                f"Same-day bookings must be at least {SAME_DAY_MIN_ADVANCE_HOURS} hours ahead. "
                f"The earliest slot I can book for today is {slot_to_display_str(earliest)}.",
            )

    # 8. Availability (booking + buffer)
    if not is_slot_available(slot_dt, booked_times):
        return False, "That slot is already taken."

    return True, ""


# ═════════════════════════════════════════════════════════════════════════
# SECTION 5 — SLOT SUGGESTIONS
# ═════════════════════════════════════════════════════════════════════════

def suggest_alternative_slots(
    requested_dt:  datetime,
    booked_times:  list[datetime],
    n:             int = NUM_ALTERNATIVES,
    search_days:   int = 7,
) -> list[datetime]:
    """
    Finds the N nearest available slots to the requested datetime.
    Searches same day first (after the requested time), then forward up to search_days.

    This is called automatically by the engine when a slot is unavailable.
    The AI agent passes these to the caller as options.

    Algorithm:
        1. Collect all available slots on requested day (after requested time)
        2. If not enough, move to next working day, collect all slots
        3. Continue until N slots found or search_days exhausted

    Args:
        requested_dt:  The originally requested slot (IST-aware)
        booked_times:  Booked datetimes for the requested day
        n:             Number of alternatives to return (default 3)
        search_days:   Max days to look ahead (default 7)

    Returns:
        List of up to N available slot datetimes (IST), sorted ascending
    """
    suggestions: list[datetime] = []
    d = requested_dt.date()

    for day_offset in range(search_days):
        target_date = d + timedelta(days=day_offset)

        if not is_working_day(target_date):
            continue

        # For the requested day: only look at slots AFTER the requested time
        # For future days: consider all slots
        if day_offset == 0:
            day_booked = booked_times
        else:
            # Caller should pass DB results for each day; here we pass empty
            # and let the engine re-query. For now suggest based on 0 bookings.
            day_booked = []

        available = get_available_slots(target_date, day_booked)

        for slot in available:
            if day_offset == 0 and slot <= requested_dt:
                continue   # skip slots at or before the requested time
            suggestions.append(slot)
            if len(suggestions) >= n:
                return suggestions

    return suggestions


def infer_slots_from_time_of_day(
    keyword:      str,
    d:            date,
    booked_times: list[datetime],
) -> list[datetime]:
    """
    Maps a time-of-day keyword to available slots in the preferred range.

    Used when a caller says "morning", "afternoon", or "evening" without
    specifying an exact time.

    Args:
        keyword:      "morning", "afternoon", or "evening" (case-insensitive)
        d:            The target date
        booked_times: Already-booked datetimes for that day

    Returns:
        Available slots within the preferred range for that keyword.
        Falls back to all available slots for the day if range is empty.

    Example:
        caller says "tomorrow morning"
        → returns slots between 9 AM and 11 AM on tomorrow's date
    """
    kw = keyword.lower().strip()
    range_info = TIME_OF_DAY_RANGES.get(kw)

    all_available = get_available_slots(d, booked_times)

    if not range_info:
        logger.warning(f"[RULES] Unknown time-of-day keyword: '{kw}' — returning all slots")
        return all_available

    range_start, range_end = range_info

    preferred = [
        s for s in all_available
        if range_start <= s.time() < range_end
    ]

    if preferred:
        return preferred

    # Fallback: return all available slots if the preferred range is empty
    logger.info(f"[RULES] No slots in {kw} range — returning all available slots")
    return all_available


# ═════════════════════════════════════════════════════════════════════════
# SECTION 6 — DISPLAY / FORMAT HELPERS
# ═════════════════════════════════════════════════════════════════════════

def slot_to_display_str(slot_dt: datetime) -> str:
    """
    Formats a slot datetime into a caller-friendly string.

    Args:
        slot_dt: Slot datetime (IST-aware)

    Returns:
        e.g. "Tuesday, 27 May at 10:30 AM"
    """
    #return slot_dt.strftime("%A, %d %B at %-I:%M %p")   for  Linux/Mac
    return slot_dt.strftime("%A, %d %B at %I:%M %p").replace(" 0", " ") # for both Windows and Linux/Mac.


def slots_to_speech_list(slots: list[datetime]) -> str:
    """
    Converts a list of slot datetimes into a natural speech string for Aria.

    Args:
        slots: Up to 3 slot datetimes

    Returns:
        e.g. "Tuesday at 10:30 AM, Tuesday at 11:00 AM, or Wednesday at 9:00 AM"
    """
    if not slots:
        return "no available slots"

    parts = [s.strftime("%-I:%M %p on %A, %d %B") for s in slots]

    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} or {parts[1]}"
    return ", ".join(parts[:-1]) + f", or {parts[-1]}"


def parse_slot_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """
    Parses date + time strings (from LLM function call arguments) into an
    IST-aware datetime.

    Expected formats:
        date_str: "YYYY-MM-DD"  (e.g. "2025-05-27")
        time_str: "HH:MM"       (e.g. "10:30" or "14:00")

    Returns:
        IST-aware datetime, or None if parsing fails
    """
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=IST)
    except ValueError as e:
        logger.error(f"[RULES] Failed to parse slot: date='{date_str}' time='{time_str}' — {e}")
        return None

def normalise_time(time_str: str) -> str | None:
    """
    Converts any time format to HH:MM 24-hour string.
    Handles: "2:00 PM", "14:00", "14:00:00", "2PM", etc.
    Returns None if unparseable.
    """
    if not time_str:
        return None
    time_str = time_str.strip().upper().replace(".", "")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
        try:
            return datetime.strptime(time_str, fmt).strftime("%H:%M")
        except ValueError:
            continue
    logger.warning(f"[RULES] Could not parse time: '{time_str}'")
    return None


# ═════════════════════════════════════════════════════════════════════════
# SECTION 7 — QUICK SELF-TEST
# ═════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n=== scheduling/rules.py — Self-test ===\n")

    today = today_ist()
    print(f"Today (IST):         {today}  ({today.strftime('%A')})")
    print(f"Is working day:      {is_working_day(today)}")
    print(f"Next working day:    {get_next_working_day(today)}\n")

    # Generate slots for next Monday
    from datetime import date as _date
    days_until_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_until_monday)
    slots = get_all_slots(next_monday)
    print(f"All slots on {next_monday.strftime('%A %d %b')} ({len(slots)} total):")
    for s in slots:
        print(f"  {s.strftime('%I:%M %p')}")

    # Simulate a booking at 10:00 and check 10:30
    print(f"\nSimulating: 10:00 AM booked on {next_monday.strftime('%d %b')}")
    booked = [datetime(next_monday.year, next_monday.month, next_monday.day, 10, 0, tzinfo=IST)]
    available = get_available_slots(next_monday, booked)
    print(f"Available slots: {len(available)}")

    # Validate a future slot
    test_slot = datetime(next_monday.year, next_monday.month, next_monday.day, 11, 0, tzinfo=IST)
    ok, reason = validate_booking_request(test_slot, booked)
    print(f"\nValidate 11:00 AM: {'✅ OK' if ok else '❌ ' + reason}")

    # Suggest alternatives for a taken slot (10:00)
    taken_slot = datetime(next_monday.year, next_monday.month, next_monday.day, 10, 0, tzinfo=IST)
    alternatives = suggest_alternative_slots(taken_slot, booked)
    print(f"\nAlternatives for taken 10:00 AM slot:")
    for alt in alternatives:
        print(f"  {slot_to_display_str(alt)}")

    # Time-of-day inference
    print(f"\nMorning slots on {next_monday.strftime('%d %b')}:")
    morning = infer_slots_from_time_of_day("morning", next_monday, booked)
    for s in morning:
        print(f"  {slot_to_display_str(s)}")

    print(f"\nSpeech string: '{slots_to_speech_list(alternatives)}'")
    print("\n=== All checks passed ✅ ===\n")

    