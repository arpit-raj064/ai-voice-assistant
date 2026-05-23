"""
backend/models/appointment.py  —  Sameer's file
=================================================
Defines the shape of data for every API request and response.
FastAPI uses these to validate incoming data automatically.

Change from previous version:
  - Added short_id field to AppointmentResponse
    e.g. "APT-2847" — easy for callers to remember and quote back
"""

from pydantic import BaseModel, field_validator
from typing import Optional
import re


class BookingRequest(BaseModel):
    name:  str
    phone: str
    date:  str   # "2026-04-15"
    time:  str   # "14:00" or "2:00 PM"

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v):
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[\d]{7,15}$", cleaned):
            raise ValueError("Phone number must be 7-15 digits")
        return cleaned

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip().title()


class CancelRequest(BaseModel):
    # Caller can use EITHER short_id ("APT-2847") OR phone number
    # AI will ask for one of these — not the full UUID
    short_id: Optional[str] = None   # e.g. "APT-2847"
    phone:     Optional[str] = None  # registered phone number


class RescheduleRequest(BaseModel):
    # Same as cancel — use short_id or phone, not UUID
    short_id: Optional[str] = None
    phone:     Optional[str] = None
    new_date:  str
    new_time:  str


class AppointmentResponse(BaseModel):
    status:     str
    message:    str
    booking_id: Optional[str] = None  # full UUID — internal use only
    short_id:   Optional[str] = None  # e.g. "APT-2847" — show this to caller
    name:       Optional[str] = None
    phone:      Optional[str] = None
    date:       Optional[str] = None
    time:       Optional[str] = None


class AvailabilityResponse(BaseModel):
    date:            str
    available_slots: list[str]
    total_available: int