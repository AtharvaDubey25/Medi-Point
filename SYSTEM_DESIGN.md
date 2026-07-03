# System Design Write-Up: Medi Point Platform

This document outlines the architectural details of the **Medi Point** booking engine, focusing on concurrency, reliability, conflict resolution, and notification resiliency.

---

## 1. Double-Booking Prevention

Preventing two users from booking the same availability slot at the exact same millisecond is a core challenge in scheduling platforms. Medi Point addresses this issue using a multi-tiered validation approach combining database-level locking and distributed application locks.

1. **Distributed Locks (Redis)**:
   Before executing a booking request, the backend attempts to acquire an exclusive distributed lock on the specific availability slot ID in Redis using `Redlock` patterns.
   * Lock Key: `lock:slot:{slot_id}`
   * Time-to-Live (TTL): 5 seconds (sufficient to execute database updates).
   If a concurrent request tries to book the same slot, the lock acquisition fails immediately, preventing overlapping executions.

2. **Atomic Database Transactions**:
   Within the execution block, database queries are wrapped in a serializable transaction block (`prisma.$transaction`). 
   * When fetching the slot state, we verify that its status is strictly `AVAILABLE`.
   * The status is updated to `BOOKED` within the same transaction.
   * PostgreSQL enforces constraint-level locking during the write phase. If another transaction changed the status in the brief window between read and write, the update query fails, triggering a transaction rollback.

This ensures zero race conditions even under heavy concurrent traffic spikes.

---

## 2. Doctor Leave Conflict Handling

When a doctor schedules a leave or goes unavailable, existing appointments booked during that period must be handled without leaving the system in an inconsistent state.

1. **Leave Initialization**:
   When a doctor requests leave for a date range, a transaction is initialized to block further scheduling by deleting all `AVAILABLE` slots within that window.

2. **Cascade Cancellation & Rescheduling**:
   For slots that are already `BOOKED` during the leave period:
   * The backend identifies the affected appointments.
   * Their status is updated to `CANCELLED` (or marked as `REFUNDED`/`PENDING_RESCHEDULE`).
   * The system logs the event in the `AuditLog` table for administration tracing.

3. **Background Sync**:
   The cancellation triggers a background event handler. This event automatically removes the corresponding meetings from the doctor's and patient's Google Calendars and dispatches cancellation emails via SendGrid containing a link to reschedule.

---

## 3. Slot Hold Mechanism

To provide a smooth checkout experience, slots are temporarily reserved for 10 minutes when a user begins booking. This prevents other users from selecting the slot while the user enters payment details or logs symptoms.

1. **Redis Cache State**:
   When a user clicks "Book", the slot is marked as `HELD` in Redis.
   * Key: `hold:slot:{slot_id}`
   * Value: `user_id`
   * Expiration (TTL): 600 seconds (10 minutes).

2. **State Resolution**:
   During the hold window, any query for doctor slots checks Redis. Slots with active hold keys are displayed as "Unavailable" to other users.
   * **Success Pathway**: If the user completes the booking within 10 minutes, the database transaction changes the slot status to `BOOKED`, and the Redis hold key is deleted.
   * **Failure/Expiration Pathway**: If the user closes the page or the TTL expires, the key is evicted from Redis automatically, making the slot instantly visible and `AVAILABLE` to the public again without database writes.

---

## 4. Notification Failure Handling

Transactional emails (reminders, booking confirmations, cancellations) are critical. If an external service like SendGrid experiences an outage, the platform must guarantee that notifications are not permanently lost.

1. **Outbox Pattern & Audit Logs**:
   Instead of calling SendGrid inline with the request, emails are recorded in the `AuditLog` database table with a `PENDING` status. The API response returns immediately, decoupling notification dispatch from core booking latency.

2. **Worker Queue & Exponential Backoff**:
   A background task manager (APScheduler) runs every 5 minutes:
   * It queries all `PENDING` notification entries.
   * It attempts transmission via SendGrid.
   * **If successful**: Marks the entry as `SENT`.
   * **If failed**: Increments a retry counter. The system applies an exponential backoff formula (retrying after 5 min, 15 min, 45 min, etc.) to avoid spamming the gateway during outages.

3. **Console Fail-Open fallback**:
   During development or critical infrastructure failovers, the app can run with `EMAIL_BACKEND=console`, logging notification payloads directly to server output to ensure testability without third-party network requests.
