# demo_twilio

Minimal SMS backend using **FastAPI + Celery + Redis + Twilio**.

## Requirements

- Docker + Docker Compose
- Twilio credentials

## Environment variables

Create a `.env` in the project root (same folder as `docker-compose.yml`) with:

- `**TWILIO_ACCOUNT_SID`**: your Twilio Account SID
- `**TWILIO_AUTH_TOKEN**`: your Twilio Auth Token
- `**PUBLIC_WEBHOOK_BASE_URL**`:
  - For basic demo sending: `http://localhost:8000`
  - For delivery callbacks (`delivered`): a **public HTTPS URL** (use ngrok)

Example:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PUBLIC_WEBHOOK_BASE_URL=http://localhost:8000
```

## Run the app (Docker)

```bash
docker compose up --build
```

API docs:

- `http://localhost:8000/docs`

## Send an SMS (queues via Redis → Celery worker → Twilio)

Replace `recipient_number` and `sender_id`:

- `recipient_number`: destination in E.164, like `+15551234567`
- `sender_id`: your **Twilio phone number** in E.164 (required by Twilio)

```bash
curl -s -X POST "http://localhost:8000/send-sms" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_number": "+15551234567",
    "message_text": "Hello from Twilio + Celery!",
    "sender_id": "+15557654321" #use your sender id which is your twilio number
  }'
```

Response:

```json
{"message_id":"...","status":"queued"}
```

## Check status

```bash
curl -s "http://localhost:8000/status/<message_id>"
```

Statuses:

- `queued`, `sending`, `sent`, `delivered`, `failed`

## Arabic / Unicode test

```bash
curl -s -X POST "http://localhost:8000/send-sms" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_number": "+15551234567",
    "message_text": "مرحبًا! هذه رسالة عربية للاختبار",
    "sender_id": "+15557654321" #use your sender id which is your twilio number
  }'
```

## Is ngrok required?

- **Not required** to send SMS.
- **Required** only if you want Twilio to call back your webhook so messages can move from `sent` → `delivered/failed`.

To enable delivery callbacks:

1. Run:

```bash
ngrok http 8000
```

1. Set in `.env`:

```bash
PUBLIC_WEBHOOK_BASE_URL=https://<your-ngrok-domain>
```

1. Restart:

```bash
docker compose down
docker compose up --build
```

