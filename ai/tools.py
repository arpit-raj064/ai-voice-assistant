"""
ai/tools.py  —  Arpit's file
==============================
Tool definitions for GPT function calling.

Changes from previous version:
  - cancel_booking now uses short_id (APT-XXXX) OR phone — not UUID
  - reschedule_appointment now uses short_id OR phone — not UUID
  - This matches how a real caller would identify themselves on a phone call
"""

import requests
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure root and backend are in sys.path for direct module calls
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.append(str(PROJECT_ROOT / "backend"))

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a given date",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format e.g. 2026-05-20"
                    }
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment for a caller after confirming slot availability",
            "parameters": {
                "type": "object",
                "properties": {
                    "name":  {
                        "type": "string",
                        "description": "Full name of the caller"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number of the caller"
                    },
                    "date":  {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format"
                    },
                    "time":  {
                        "type": "string",
                        "description": "Appointment time e.g. 14:00 or 2:00 PM"
                    }
                },
                "required": ["name", "phone", "date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": (
                "Cancel an existing appointment. "
                "Ask the caller for their short booking ID (e.g. APT-2847) "
                "OR their registered phone number. Never ask for the long UUID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "short_id": {
                        "type": "string",
                        "description": "Short booking ID like APT-2847 (optional if phone provided)"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Caller's registered phone number (optional if short_id provided)"
                    }
                },
                "required": []   # either short_id or phone — not both required
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": (
                "Reschedule an existing appointment to a new date and time. "
                "Ask for short booking ID (APT-XXXX) OR phone number to identify the booking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "short_id": {
                        "type": "string",
                        "description": "Short booking ID like APT-2847 (optional if phone provided)"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Caller's registered phone number (optional if short_id provided)"
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New appointment date in YYYY-MM-DD format"
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New appointment time e.g. 15:00 or 3:00 PM"
                    }
                },
                "required": ["new_date", "new_time"]
            }
        }
    }
]


def handle_tool_call(tool_call) -> dict:
    """
    Routes GPT's tool call directly to backend logic for 0ms execution.
    Returns result dict — GPT reads this and forms its reply.
    """
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    print(f"\n[TOOL CALLED] {name}")
    print(f"[TOOL ARGS]   {args}")

    try:
        if name == "check_availability":
            try:
                from backend.scheduling.engine import get_available_slots
            except ImportError:
                from scheduling.engine import get_available_slots
            date = args.get("date", "")
            slots = get_available_slots(date)
            return {"date": date, "available_slots": slots, "total_available": len(slots)}

        elif name == "book_appointment":
            try:
                from backend.routes.appointments import book_appointment as direct_book
                from backend.models.appointment import BookingRequest
            except ImportError:
                from routes.appointments import book_appointment as direct_book
                from models.appointment import BookingRequest
            req_obj = BookingRequest(**args)
            res = direct_book(req_obj)
            return res

        elif name == "cancel_booking":
            try:
                from backend.routes.appointments import cancel_appointment as direct_cancel
                from backend.models.appointment import CancelRequest
            except ImportError:
                from routes.appointments import cancel_appointment as direct_cancel
                from models.appointment import CancelRequest
            req_obj = CancelRequest(**args)
            return direct_cancel(req_obj)

        elif name == "reschedule_appointment":
            try:
                from backend.routes.appointments import reschedule_appointment as direct_reschedule
                from backend.models.appointment import RescheduleRequest
            except ImportError:
                from routes.appointments import reschedule_appointment as direct_reschedule
                from models.appointment import RescheduleRequest
            req_obj = RescheduleRequest(**args)
            return direct_reschedule(req_obj)

        else:
            print(f"[TOOL ERROR] Unknown tool: {name}")
            return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        print(f"[TOOL ERROR] {e}")
        return {"error": str(e)}