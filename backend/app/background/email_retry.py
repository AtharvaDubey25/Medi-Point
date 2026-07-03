"""
Email retry mechanism.
Failed email sends are logged and retried with exponential backoff.
Uses in-memory queue since we don't have Redis. In production, use a proper
message queue (Celery + Redis/RabbitMQ).
"""

import asyncio
from typing import List, Dict
from dataclasses import dataclass
from app.services.email_service import send_email


@dataclass
class PendingEmail:
    to_email: str
    subject: str
    body: str
    to_name: str = None
    retries: int = 0
    max_retries: int = 3


_email_queue: List[PendingEmail] = []


def queue_email(to_email: str, subject: str, body: str, to_name: str = None):
    _email_queue.append(PendingEmail(
        to_email=to_email,
        subject=subject,
        body=body,
        to_name=to_name,
    ))


async def _requeue_after_delay(email: PendingEmail, delay: int):
    await asyncio.sleep(delay)
    _email_queue.append(email)


async def process_email_queue():
    global _email_queue
    if not _email_queue:
        return

    pending = _email_queue
    _email_queue = []

    for email in pending:
        try:
            await send_email(email.to_email, email.subject, email.body, email.to_name, retry_on_failure=False)
        except Exception as e:
            if email.retries < email.max_retries:
                email.retries += 1
                asyncio.create_task(_requeue_after_delay(email, 2 ** email.retries))
            print(f"Failed to send email to {email.to_email} after {email.retries} retries: {e}")
