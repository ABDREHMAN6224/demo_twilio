import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from redis import Redis

from sms_service.config import settings


Status = Literal["queued", "sending", "sent", "delivered", "failed"]


@dataclass(frozen=True)
class StatusEvent:
    status: Status
    at: str
    detail: Optional[str] = None
    provider_message_id: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def key_for(message_id: str) -> str:
    return f"sms:{message_id}"


def twilio_sid_key(twilio_sid: str) -> str:
    return f"twilio_sid:{twilio_sid}"


def set_message(
    r: Redis,
    *,
    message_id: str,
    to: str,
    body: str,
    sender_id: str,
    status: Status,
    provider_message_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    payload: dict[str, Any] = {
        "message_id": message_id,
        "to": to,
        "body": body,
        "sender_id": sender_id,
        "status": status,
        "provider_message_id": provider_message_id,
        "detail": detail,
        "updated_at": _now_iso(),
        "events": [asdict(StatusEvent(status=status, at=_now_iso(), detail=detail, provider_message_id=provider_message_id))],
    }
    r.set(key_for(message_id), json.dumps(payload, ensure_ascii=False))


def append_event(
    r: Redis,
    *,
    message_id: str,
    status: Status,
    provider_message_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> dict[str, Any]:
    raw = r.get(key_for(message_id))
    if not raw:
        payload: dict[str, Any] = {
            "message_id": message_id,
            "to": None,
            "body": None,
            "sender_id": None,
            "status": status,
            "provider_message_id": provider_message_id,
            "detail": detail,
            "updated_at": _now_iso(),
            "events": [],
        }
    else:
        payload = json.loads(raw)

    payload["status"] = status
    payload["provider_message_id"] = provider_message_id or payload.get("provider_message_id")
    payload["detail"] = detail
    payload["updated_at"] = _now_iso()
    payload.setdefault("events", []).append(
        asdict(StatusEvent(status=status, at=_now_iso(), detail=detail, provider_message_id=provider_message_id))
    )
    r.set(key_for(message_id), json.dumps(payload, ensure_ascii=False))
    return payload


def get_message(r: Redis, message_id: str) -> Optional[dict[str, Any]]:
    raw = r.get(key_for(message_id))
    if not raw:
        return None
    return json.loads(raw)

