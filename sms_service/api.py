from __future__ import annotations

from typing import Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException
from pydantic import BaseModel, Field

from sms_service.config import settings
from sms_service.storage import append_event, get_message, redis_client, set_message, twilio_sid_key
from sms_service.tasks import send_sms_task

app = FastAPI(title="SMS Service (Twilio + Celery + Redis)")


class SendSMSRequest(BaseModel):
    recipient_number: str = Field(..., description="E.164 formatted number, e.g. +15551234567")
    message_text: str = Field(..., min_length=1, description="SMS body (UTF-8/Unicode supported)")
    sender_id: str = Field(..., description="Twilio phone number (E.164) or alphanumeric sender id (country dependent)")


class SendSMSResponse(BaseModel):
    message_id: str
    status: Literal["queued"]


class StatusResponse(BaseModel):
    message_id: str
    status: Literal["queued", "sending", "sent", "delivered", "failed"]
    provider_message_id: Optional[str] = None
    detail: Optional[str] = None
    updated_at: Optional[str] = None
    events: list[dict] = []


def _public_webhook_base_url() -> str:
    return getattr(settings, "public_webhook_base_url", None) or "http://localhost:8000"


@app.post("/send-sms", response_model=SendSMSResponse)
def send_sms(payload: SendSMSRequest) -> SendSMSResponse:
    r = redis_client()

    message_id = uuid4().hex
    set_message(
        r,
        message_id=message_id,
        to=payload.recipient_number,
        body=payload.message_text,
        sender_id=payload.sender_id,
        status="queued",
    )

    base = _public_webhook_base_url().rstrip("/")
    status_callback_url = f"{base}/twilio/status" if base.startswith("https://") else None
    send_sms_task.delay(
        message_id=message_id,
        to=payload.recipient_number,
        body=payload.message_text,
        sender_id=payload.sender_id,
        status_callback_url=status_callback_url,
    )

    return SendSMSResponse(message_id=message_id, status="queued")


@app.get("/status/{message_id}", response_model=StatusResponse)
def status(message_id: str) -> StatusResponse:
    r = redis_client()
    msg = get_message(r, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Unknown message_id")
    return StatusResponse(**msg)


TwilioMessageStatus = Literal[
    "queued",
    "accepted",
    "sending",
    "sent",
    "delivered",
    "undelivered",
    "failed",
    "canceled",
]


@app.post("/twilio/status")
def twilio_status_callback(
    MessageSid: str = Form(...),
    MessageStatus: TwilioMessageStatus = Form(...),
    ErrorCode: Optional[str] = Form(None),
    ErrorMessage: Optional[str] = Form(None),
):
    """
    Twilio will POST form-encoded updates here if you set `status_callback`.
    We map Twilio statuses into our simplified statuses and store in Redis.
    """
    r = redis_client()
    message_id = r.get(twilio_sid_key(MessageSid))
    if not message_id:
        # Unknown mapping; ignore to keep webhook idempotent / safe.
        return {"ok": True, "ignored": True}

    mapped: Literal["sent", "delivered", "failed", "sending"] | None = None
    if MessageStatus in ("accepted", "queued", "sending"):
        mapped = "sending"
    elif MessageStatus == "sent":
        mapped = "sent"
    elif MessageStatus == "delivered":
        mapped = "delivered"
    elif MessageStatus in ("undelivered", "failed", "canceled"):
        mapped = "failed"

    detail = None
    if ErrorCode or ErrorMessage:
        detail = f"{ErrorCode or ''} {ErrorMessage or ''}".strip()

    if mapped:
        append_event(r, message_id=message_id, status=mapped, provider_message_id=MessageSid, detail=detail)

    return {"ok": True}
