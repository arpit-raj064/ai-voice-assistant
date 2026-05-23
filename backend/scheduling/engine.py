"""
backend/scheduling/engine.py  —  Sameer's file
================================================
Smart scheduling logic:
  - Generate all time slots in a day
  - Check if a specific slot is available
  - Find nearest available slots when requested one is taken
  - Apply business rules (working hours, closed days)
"""

import os
import sys
import logging
from datetime import datetime, date, time, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from database import db

logger = logging.getLogger(__name__)

# ── Business rules ────────────────────────────────────────────────────────
WORK_START    = time(9, 0)    # 9:00 AM
WORK_END      = time(18, 0)   # 6:00 PM
SLOT_DURATION = 30            # minutes
BUFFER        = 0             # gap between slots
MAX_PER_SLOT  = 1             # max bookings per slot
CLOSED_DAYS   = [6]           # 6 = Sunday


def generate_all_slots(for_date: date) -> list[str]:
    """Returns all possible time slots for a given date."""
    if for_date.weekday() in CLOSED_DAYS:
        return []

    slots  = []
    cursor = datetime.combine(for_date, WORK_START)
    end    = datetime.combine(for_date, WORK_END)

    while cursor + timedelta(minutes=SLOT_DURATION) <= end:
        slots.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=SLOT_DURATION + BUFFER)

    return slots


def normalise_time(time_str: str) -> str | None:
    """Converts any time format to HH:MM 24-hour format."""
    if not time_str:
        return None

    time_str = time_str.strip()

    # Already HH:MM:SS
    if len(time_str) == 8 and time_str[2] == ":" and time_str[5] == ":":
        return time_str[:5]

    formats = [
        "%H:%M", "%H:%M:%S",
        "%I:%M %p", "%I:%M%p",
        "%I %p", "%I%p",
        "%I:%M %P", "%I:%M%P",
    ]

    normalised = time_str.upper().replace(".", "")

    for fmt in formats:
        try:
            parsed = datetime.strptime(normalised, fmt)
            return parsed.strftime("%H:%M")
        except ValueError:
            continue

    logger.warning(f"[normalise_time] Could not parse: '{time_str}'")
    return None


def is_slot_available(check_date: str, check_time: str) -> bool:
    """Returns True if the slot is free, False if taken or invalid."""
    try:
        normalised = normalise_time(check_time)
        if not normalised:
            return False

        parsed_date = datetime.strptime(check_date, "%Y-%m-%d").date()

        if parsed_date.weekday() in CLOSED_DAYS:
            return False

        slot_time = datetime.strptime(normalised, "%H:%M").time()
        if slot_time < WORK_START or slot_time >= WORK_END:
            return False

        result = db.table("appointments") \
            .select("id") \
            .eq("date",   check_date) \
            .eq("time",   normalised) \
            .eq("status", "confirmed") \
            .execute()

        return len(result.data) < MAX_PER_SLOT

    except Exception as e:
        logger.error(f"[is_slot_available] Error: {e}")
        return False


def get_available_slots(check_date: str) -> list[str]:
    """Returns all free slots for a given date."""
    try:
        parsed_date = datetime.strptime(check_date, "%Y-%m-%d").date()
        all_slots   = generate_all_slots(parsed_date)

        if not all_slots:
            return []

        result = db.table("appointments") \
            .select("time") \
            .eq("date",   check_date) \
            .eq("status", "confirmed") \
            .execute()

        booked_times = {row["time"][:5] for row in result.data}
        return [s for s in all_slots if s not in booked_times]

    except Exception as e:
        logger.error(f"[get_available_slots] Error: {e}")
        return []


def find_nearest_slots(
    requested_date: str,
    requested_time: str,
    count: int = 3
) -> list[dict]:
    """
    Finds nearest available slots when requested one is taken.
    Searches same day first, then next days up to 7 days ahead.
    """
    suggestions = []
    parsed_date = datetime.strptime(requested_date, "%Y-%m-%d").date()

    for day_offset in range(7):
        search_date     = parsed_date + timedelta(days=day_offset)
        search_date_str = search_date.strftime("%Y-%m-%d")
        available       = get_available_slots(search_date_str)

        if not available:
            continue

        if day_offset == 0:
            try:
                req_dt = datetime.strptime(normalise_time(requested_time), "%H:%M")
                available.sort(key=lambda s: abs(
                    (datetime.strptime(s, "%H:%M") - req_dt).total_seconds()
                ))
            except Exception:
                pass

        for slot_time in available:
            if len(suggestions) >= count:
                break

            if day_offset == 0:
                day_label = "Today"
            elif day_offset == 1:
                day_label = "Tomorrow"
            else:
                day_label = search_date.strftime("%A, %B %d")

            time_label = datetime.strptime(slot_time, "%H:%M") \
                .strftime("%I:%M %p").lstrip("0")

            suggestions.append({
                "date":  search_date_str,
                "time":  slot_time,
                "label": f"{day_label} at {time_label}"
            })

        if len(suggestions) >= count:
            break

    return suggestions