from __future__ import annotations

from celery.utils.log import get_task_logger
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from sms_service.celery_app import celery
from sms_service.config import settings
from sms_service.storage import append_event, redis_client, twilio_sid_key

logger = get_task_logger(__name__)


def _twilio_client() -> Client:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise RuntimeError("Twilio credentials missing. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


@celery.task(
    bind=True,
    autoretry_for=(TwilioRestException, OSError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_sms_task(self, *, message_id: str, to: str, body: str, sender_id: str, status_callback_url: str | None = None) -> dict:
    r = redis_client()
    append_event(r, message_id=message_id, status="sending")

    client = _twilio_client()
    try:
        msg = client.messages.create(
            to=to,
            from_=sender_id,
            body=body,
            status_callback=status_callback_url or None,
        )
    except Exception as e:
        append_event(r, message_id=message_id, status="failed", detail=str(e))
        raise

    r.set(twilio_sid_key(msg.sid), message_id)
    append_event(r, message_id=message_id, status="sent", provider_message_id=msg.sid)
    logger.info("Sent SMS message_id=%s twilio_sid=%s", message_id, msg.sid)
    return {"message_id": message_id, "provider_message_id": msg.sid, "status": "sent"}
