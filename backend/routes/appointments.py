"""
backend/routes/appointments.py  —  Sameer's file
==================================================
All appointment API endpoints.

Changes from previous version:
  - Generates short human-readable booking ID (APT-XXXX)
  - Cancel/reschedule use short_id OR phone — not UUID
  - WhatsApp notification sent after every booking/cancel/reschedule
  - SMS fallback if WhatsApp fails (handled inside notifications.py)

Endpoints:
  GET  /appointments/available-slots  → check free slots
  POST /appointments/book             → create booking + send WhatsApp
  POST /appointments/cancel           → cancel + send WhatsApp
  POST /appointments/reschedule       → reschedule + send WhatsApp
  GET  /appointments/all              → list all (Deepak's dashboard)
"""

import sys
import random
import string
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi import APIRouter, HTTPException
from database import db
from models.appointment import (
    BookingRequest,
    CancelRequest,
    RescheduleRequest,
)
from scheduling.engine import (
    get_available_slots,
    is_slot_available,
    find_nearest_slots,
    normalise_time,
)
from notifications import (
    send_booking_notification,
    send_cancellation_notification,
    send_reschedule_notification,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Helper: generate unique short booking ID ──────────────────────────────
def generate_unique_short_id() -> str:
    """
    Generates APT-XXXX format ID that doesn't already exist in DB.
    e.g. APT-2847, APT-9031
    Easy to say on a phone: "A-P-T dash 2-8-4-7"
    """
    while True:
        short_id = f"APT-{''.join(random.choices(string.digits, k=4))}"
        existing = db.table("appointments") \
            .select("id") \
            .eq("short_id", short_id) \
            .execute()
        if not existing.data:
            return short_id


# ── Helper: find appointment by short_id or phone ─────────────────────────
def find_appointment(short_id: str = None, phone: str = None):
    """Find confirmed appointment by short_id OR phone number."""
    try:
        if short_id:
            result = db.table("appointments") \
                .select("*") \
                .eq("short_id", short_id.strip().upper()) \
                .eq("status",   "confirmed") \
                .execute()
        elif phone:
            result = db.table("appointments") \
                .select("*") \
                .eq("phone",  phone) \
                .eq("status", "confirmed") \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
        else:
            return None
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"[find_appointment] {e}")
        return None


# ── GET /appointments/available-slots ─────────────────────────────────────
@router.get("/available-slots")
def available_slots(date: str):
    """Returns all free slots for a given date."""
    logger.info(f"[CHECK SLOTS] date={date}")
    slots = get_available_slots(date)
    return {
        "date":            date,
        "available_slots": slots,
        "total_available": len(slots),
    }


# ── POST /appointments/book ───────────────────────────────────────────────
@router.post("/book")
def book_appointment(req: BookingRequest):
    """
    Books an appointment if the slot is free.
    Sends WhatsApp confirmation (SMS fallback) with booking ID.
    """
    logger.info(f"[BOOK] {req.name} | {req.phone} | {req.date} {req.time}")

    normalised_time = normalise_time(req.time)
    if not normalised_time:
        raise HTTPException(
            status_code=400,
            detail=f"Could not understand time '{req.time}'"
        )

    # ── Check availability ────────────────────────────────────────────────
    if not is_slot_available(req.date, normalised_time):
        suggestions  = find_nearest_slots(req.date, normalised_time, count=3)
        suggest_text = ", ".join([s["label"] for s in suggestions]) \
                       if suggestions else "no nearby slots found"
        return {
            "status":   "unavailable",
            "message":  f"Sorry, {normalised_time} on {req.date} is already booked. "
                        f"Nearest available: {suggest_text}",
            "short_id": None,
        }

    # ── Generate short ID ─────────────────────────────────────────────────
    short_id = generate_unique_short_id()

    # ── Insert into Supabase ──────────────────────────────────────────────
    try:
        result = db.table("appointments").insert({
            "name":     req.name,
            "phone":    req.phone,
            "date":     req.date,
            "time":     normalised_time,
            "status":   "confirmed",
            "short_id": short_id,
        }).execute()

        if not result.data:
            raise Exception("Insert returned no data")

        booking = result.data[0]
        logger.info(f"[BOOKED] short_id={short_id}")

        # ── Send WhatsApp notification (SMS fallback handled inside) ──────
        notify_result = send_booking_notification(
            phone    = req.phone,
            name     = req.name,
            date     = req.date,
            time     = normalised_time,
            short_id = short_id,
        )
        logger.info(f"[NOTIFY RESULT] {notify_result}")

        # Build response message based on notification result
        notify_msg = ""
        if notify_result["whatsapp"]:
            notify_msg = "I've also sent you a WhatsApp confirmation with your booking details."
        elif notify_result["sms"]:
            notify_msg = "I've also sent you an SMS confirmation with your booking details."
        else:
            notify_msg = "Please save your booking ID as you may need it to cancel or reschedule."

        return {
            "status":     "booked",
            "message":    (
                f"Appointment confirmed for {req.name} on {req.date} "
                f"at {normalised_time}. "
                f"Your booking ID is {short_id}. "
                f"{notify_msg}"
            ),
            "short_id":        short_id,
            "booking_id":      booking["id"],
            "name":            req.name,
            "phone":           req.phone,
            "date":            req.date,
            "time":            normalised_time,
            "notification":    notify_result,
        }

    except Exception as e:
        logger.error(f"[BOOK ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /appointments/cancel ─────────────────────────────────────────────
@router.post("/cancel")
def cancel_appointment(req: CancelRequest):
    """
    Cancels an appointment using short_id OR phone number.
    Sends WhatsApp cancellation confirmation.
    """
    logger.info(f"[CANCEL] short_id={req.short_id} phone={req.phone}")

    if not req.short_id and not req.phone:
        return {
            "status":  "error",
            "message": "Please provide your booking ID (e.g. APT-2847) "
                       "or your registered phone number.",
        }

    appt = find_appointment(short_id=req.short_id, phone=req.phone)

    if not appt:
        identifier = req.short_id or req.phone
        return {
            "status":  "error",
            "message": f"No confirmed appointment found for {identifier}. "
                       f"Please check your booking ID or phone number.",
        }

    try:
        db.table("appointments") \
            .update({"status": "cancelled"}) \
            .eq("id", appt["id"]) \
            .execute()

        logger.info(f"[CANCELLED] short_id={appt.get('short_id')}")

        appt_time = str(appt["time"])[:5]

        # ── Send cancellation WhatsApp ─────────────────────────────────
        notify_result = send_cancellation_notification(
            phone    = appt["phone"],
            name     = appt["name"],
            date     = str(appt["date"]),
            time     = appt_time,
            short_id = appt.get("short_id", "N/A"),
        )

        return {
            "status":     "cancelled",
            "message":    (
                f"Your appointment on {appt['date']} at {appt_time} "
                f"has been successfully cancelled. "
                f"{'A WhatsApp confirmation has been sent to you.' if notify_result['whatsapp'] else 'An SMS confirmation has been sent to you.' if notify_result['sms'] else ''}"
            ),
            "short_id":      appt.get("short_id"),
            "name":          appt["name"],
            "date":          str(appt["date"]),
            "time":          appt_time,
            "notification":  notify_result,
        }

    except Exception as e:
        logger.error(f"[CANCEL ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /appointments/reschedule ─────────────────────────────────────────
@router.post("/reschedule")
def reschedule_appointment(req: RescheduleRequest):
    """
    Reschedules appointment using short_id OR phone.
    Sends WhatsApp reschedule confirmation.
    """
    logger.info(
        f"[RESCHEDULE] short_id={req.short_id} phone={req.phone} "
        f"→ {req.new_date} {req.new_time}"
    )

    if not req.short_id and not req.phone:
        return {
            "status":  "error",
            "message": "Please provide your booking ID or phone number.",
        }

    normalised_time = normalise_time(req.new_time)
    if not normalised_time:
        raise HTTPException(status_code=400, detail=f"Invalid time '{req.new_time}'")

    appt = find_appointment(short_id=req.short_id, phone=req.phone)

    if not appt:
        identifier = req.short_id or req.phone
        return {
            "status":  "error",
            "message": f"No confirmed appointment found for {identifier}.",
        }

    # ── Check new slot availability ───────────────────────────────────────
    if not is_slot_available(req.new_date, normalised_time):
        suggestions  = find_nearest_slots(req.new_date, normalised_time)
        suggest_text = ", ".join([s["label"] for s in suggestions])
        return {
            "status":  "unavailable",
            "message": f"Sorry, {normalised_time} on {req.new_date} is already taken. "
                       f"Nearest available: {suggest_text}",
        }

    try:
        db.table("appointments").update({
            "date":   req.new_date,
            "time":   normalised_time,
            "status": "confirmed",
        }).eq("id", appt["id"]).execute()

        logger.info(f"[RESCHEDULED] short_id={appt.get('short_id')}")

        # ── Send reschedule WhatsApp ───────────────────────────────────
        notify_result = send_reschedule_notification(
            phone    = appt["phone"],
            name     = appt["name"],
            new_date = req.new_date,
            new_time = normalised_time,
            short_id = appt.get("short_id", "N/A"),
        )

        return {
            "status":     "rescheduled",
            "message":    (
                f"Your appointment has been rescheduled to "
                f"{req.new_date} at {normalised_time}. "
                f"Your booking ID remains {appt.get('short_id')}. "
                f"{'A WhatsApp confirmation has been sent.' if notify_result['whatsapp'] else 'An SMS confirmation has been sent.' if notify_result['sms'] else ''}"
            ),
            "short_id":      appt.get("short_id"),
            "name":          appt["name"],
            "date":          req.new_date,
            "time":          normalised_time,
            "notification":  notify_result,
        }

    except Exception as e:
        logger.error(f"[RESCHEDULE ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /appointments/all ─────────────────────────────────────────────────
@router.get("/all")
def get_all_appointments(limit: int = 50):
    """Returns all appointments — used by Deepak's frontend dashboard."""
    try:
        result = db.table("appointments") \
            .select("*") \
            .order("date", desc=True) \
            .limit(limit) \
            .execute()
        return {
            "total":        len(result.data),
            "appointments": result.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))