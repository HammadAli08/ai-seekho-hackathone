from twilio.rest import Client
from config import settings
from .firebase_service import log_sms_event
from datetime import datetime
import logging, asyncio

logger = logging.getLogger(__name__)


async def send_sms_blast(message: str, recipient_count: int, city: str) -> dict:
    if settings.SMS_MODE == "real":
        return await _send_real_sms(message, recipient_count, city)
    else:
        return await _send_mock_sms(message, recipient_count, city)


async def _send_real_sms(message: str, recipient_count: int, city: str) -> dict:
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        msg = client.messages.create(
            body=message[:160],
            from_=settings.TWILIO_FROM_NUMBER,
            to=settings.SMS_DEMO_TO_NUMBER
        )

        await log_sms_event(city, recipient_count, "real", msg.sid)

        return {
            "mode": "real",
            "sent_count": recipient_count,
            "real_sms_sid": msg.sid,
            "demo_recipient": settings.SMS_DEMO_TO_NUMBER,
            "sample_message": message[:160],
            "estimated_delivery": "2-3 minutes",
            "cost_pkr": round(recipient_count * 0.5, 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Twilio SMS failed: {e}")
        return await _send_mock_sms(message, recipient_count, city)


async def _send_mock_sms(message: str, recipient_count: int, city: str) -> dict:
    await asyncio.sleep(1.2)  # Simulate network delay

    await log_sms_event(city, recipient_count, "mock", None)

    logger.info(f"[MOCK SMS] Would send to {recipient_count} recipients in {city}:")
    logger.info(f"[MOCK SMS] Message: {message[:160]}")

    return {
        "mode": "mock",
        "sent_count": recipient_count,
        "sample_message": message[:160],
        "simulated_recipients": [
            f"+923{str(i).zfill(9)[-9:]}" for i in range(min(5, recipient_count))
        ],
        "estimated_delivery": "45 minutes",
        "cost_pkr": round(recipient_count * 0.5, 2),
        "timestamp": datetime.now().isoformat()
    }