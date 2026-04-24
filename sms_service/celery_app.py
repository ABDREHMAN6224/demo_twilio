from celery import Celery

from sms_service.config import settings

celery = Celery(
    "sms_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["sms_service.tasks"],
)

celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue="sms",
)
