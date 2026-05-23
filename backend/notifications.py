"""
backend/notifications.py  —  Raunit's file
===========================================
Notification system for booking confirmations.

Current: WhatsApp via Twilio WhatsApp API (SMS as fallback)
Future upgrade: Send BOTH SMS + WhatsApp simultaneously

Logic RIGHT NOW:
  1. Try WhatsApp first
  2. If WhatsApp fails → fall back to SMS automatically

Future upgrade logic (uncomment the block at the bottom):
  if caller has both WhatsApp + SMS:
      send both simultaneously
  elif only WhatsApp:
      send WhatsApp only
  elif only SMS:
      send SMS only

Twilio WhatsApp sandbox setup (for testing):
  1. twilio.com → Messaging → Try it out → Send a WhatsApp message
  2. Scan the QR code or send the join message from your phone
  3. After joining sandbox → you'll receive test WhatsApp messages
  4. For production → apply for WhatsApp Business API (takes a few days)

.env keys needed:
  TWILIO_ACCOUNT_SID=ACxxxxxxxx
  TWILIO_AUTH_TOKEN=xxxxxxxx
  TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
  TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID     = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN      = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER    = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")


def normalise_phone(phone: str) -> str:
    """Converts phone to E.164 format: 9876543210 → +919876543210"""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.lower().startswith("whatsapp:"):
        phone = phone[9:]
    if phone.startswith("+"): return phone
    if phone.startswith("0"): phone = phone[1:]
    if len(phone) == 10: return f"+91{phone}"
    return f"+{phone}"


def format_message(template: str, name: str, date: str,
                   time: str, short_id: str, **kwargs) -> str:
    """Formats notification message with booking details."""
    try:
        formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d %B %Y")
    except Exception:
        formatted_date = date
    try:
        formatted_time = datetime.strptime(time, "%H:%M") \
                                 .strftime("%I:%M %p").lstrip("0")
    except Exception:
        formatted_time = time

    return template.format(
        name=name,
        date=formatted_date,
        time=formatted_time,
        short_id=short_id,
        **kwargs
    )


# ── Message templates ─────────────────────────────────────────────────────
BOOKING_MSG = (
    "📅 *Booking Confirmed!*\n\n"
    "Hi {name},\n"
    "Your appointment has been successfully booked.\n\n"
    "🆔 *Booking ID* : {short_id}\n"
    "📆 *Date*       : {date}\n"
    "⏰ *Time*       : {time}\n\n"
    "To *cancel* or *reschedule*, call us and quote your Booking ID: *{short_id}*\n\n"
    "_— Aria, AI Receptionist_"
)

CANCELLATION_MSG = (
    "❌ *Booking Cancelled*\n\n"
    "Hi {name},\n"
    "Your appointment has been cancelled.\n\n"
    "🆔 *Booking ID* : {short_id}\n"
    "📆 *Date*       : {date}\n"
    "⏰ *Time*       : {time}\n\n"
    "If this was a mistake, please call us to rebook.\n\n"
    "_— Aria, AI Receptionist_"
)

RESCHEDULE_MSG = (
    "🔄 *Appointment Rescheduled*\n\n"
    "Hi {name},\n"
    "Your appointment has been rescheduled.\n\n"
    "🆔 *Booking ID* : {short_id}\n"
    "📆 *New Date*   : {date}\n"
    "⏰ *New Time*   : {time}\n\n"
    "Your Booking ID remains *{short_id}*.\n\n"
    "_— Aria, AI Receptionist_"
)


# ── Core send functions ───────────────────────────────────────────────────
def _send_whatsapp(to_phone: str, message: str) -> bool:
    """Sends a WhatsApp message via Twilio."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("[WHATSAPP] Credentials not set")
        return False
    try:
        from twilio.rest import Client
        client     = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        sender = TWILIO_WHATSAPP_NUMBER.strip()
        if not sender.lower().startswith("whatsapp:"):
            sender = f"whatsapp:{sender}"
            
        to_number  = normalise_phone(to_phone)
        recipient  = f"whatsapp:{to_number}"
        
        msg = client.messages.create(
            body  = message,
            from_ = sender,
            to    = recipient,
        )
        logger.info(f"[WHATSAPP] ✅ Sent to {to_number} SID={msg.sid}")
        return True
    except Exception as e:
        logger.error(f"[WHATSAPP] ❌ Failed: {e}")
        return False


def _send_sms(to_phone: str, message: str) -> bool:
    """Sends an SMS via Twilio. Used as fallback when WhatsApp fails."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("[SMS] Credentials not set")
        return False
    if not TWILIO_PHONE_NUMBER:
        logger.warning("[SMS] TWILIO_PHONE_NUMBER not set")
        return False
    try:
        from twilio.rest import Client
        client    = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        to_number = normalise_phone(to_phone)
        # Strip WhatsApp markdown for plain SMS
        sms_msg   = message.replace("*","").replace("_","") \
                           .replace("📅","").replace("🆔","") \
                           .replace("📆","").replace("⏰","") \
                           .replace("❌","").replace("🔄","").strip()
        msg = client.messages.create(
            body  = sms_msg,
            from_ = TWILIO_PHONE_NUMBER,
            to    = to_number,
        )
        logger.info(f"[SMS] ✅ Sent to {to_number} SID={msg.sid}")
        return True
    except Exception as e:
        logger.error(f"[SMS] ❌ Failed: {e}")
        return False


# ── Smart notification dispatcher ────────────────────────────────────────
def _dispatch(phone: str, message: str) -> dict:
    """
    Smart notification dispatcher.

    CURRENT BEHAVIOUR:
      Try WhatsApp → if fails → try SMS fallback

    FUTURE UPGRADE — to send BOTH simultaneously, replace this function with:
      whatsapp_sent = _send_whatsapp(phone, message)
      sms_sent      = _send_sms(phone, message)
      return {
          "whatsapp": whatsapp_sent,
          "sms":      sms_sent,
          "any_sent": whatsapp_sent or sms_sent,
      }
    """
    results = {"whatsapp": False, "sms": False, "any_sent": False}

    # Try WhatsApp first
    logger.info(f"[NOTIFY] Trying WhatsApp → {phone}")
    wa_sent = _send_whatsapp(phone, message)
    results["whatsapp"] = wa_sent

    if wa_sent:
        results["any_sent"] = True
        logger.info(f"[NOTIFY] ✅ WhatsApp delivered")
    else:
        # WhatsApp failed — try SMS fallback
        logger.warning(f"[NOTIFY] WhatsApp failed → SMS fallback")
        sms_sent = _send_sms(phone, message)
        results["sms"]      = sms_sent
        results["any_sent"] = sms_sent

        if sms_sent:
            logger.info(f"[NOTIFY] ✅ SMS fallback delivered")
        else:
            logger.error(f"[NOTIFY] ❌ Both channels failed for {phone}")

    return results


# ── Public notification functions ─────────────────────────────────────────
def send_booking_notification(phone: str, name: str,
                               date: str, time: str, short_id: str) -> dict:
    """Send booking confirmation — call this right after booking is created."""
    msg = format_message(BOOKING_MSG, name, date, time, short_id)
    return _dispatch(phone, msg)


def send_cancellation_notification(phone: str, name: str,
                                    date: str, time: str, short_id: str) -> dict:
    """Send cancellation confirmation — call this right after booking is cancelled."""
    msg = format_message(CANCELLATION_MSG, name, date, time, short_id)
    return _dispatch(phone, msg)


def send_reschedule_notification(phone: str, name: str,
                                  new_date: str, new_time: str, short_id: str) -> dict:
    """Send reschedule confirmation — call this right after booking is rescheduled."""
    msg = format_message(RESCHEDULE_MSG, name, new_date, new_time, short_id)
    return _dispatch(phone, msg)


# ── Quick test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Notification System Test ===")
    print(f"Twilio SID set:   {'YES' if TWILIO_ACCOUNT_SID  else 'NO — add to .env'}")
    print(f"Twilio Token set: {'YES' if TWILIO_AUTH_TOKEN   else 'NO — add to .env'}")
    print(f"WhatsApp number:  {TWILIO_WHATSAPP_NUMBER}")
    print(f"SMS number:       {TWILIO_PHONE_NUMBER or 'NOT SET (optional for now)'}")

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        test_phone = input("\nEnter your phone number to test (e.g. 9876543210): ").strip()
        print("\nSending test booking notification...")
        result = send_booking_notification(
            phone    = test_phone,
            name     = "Test User",
            date     = "2026-05-20",
            time     = "14:00",
            short_id = "APT-0001",
        )
        print(f"\nResult: {result}")
        if result["any_sent"]:
            print("SUCCESS! Check your WhatsApp or SMS.")
        else:
            print("FAILED. Make sure you joined the Twilio WhatsApp sandbox first.")
            print("Instructions: twilio.com → Messaging → Try it out → WhatsApp")
    else:
        print("\nSteps to activate:")
        print("  1. Sign up at twilio.com (Raunit does this)")
        print("  2. Add TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN to .env")
        print("  3. Add TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886 to .env")
        print("  4. Run this file again")