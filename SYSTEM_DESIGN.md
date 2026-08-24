# System Design: Healthcare Booking Platform

This document outlines the architectural mechanics explicitly implemented in the Healthcare Booking Platform, ensuring robust concurrency, automated background processing, and fault tolerance.

## 1. Concurrency Safety: Preventing Double-Booking
A notorious failure point in booking systems is a race condition where two concurrent users request the exact same time slot, resulting in double-booking. Typical application-level checks (e.g., executing a `SELECT` availability check followed by an `INSERT`) are insufficient because concurrent transactions can both successfully read the slot as available before either commits.

To mathematically prevent this, we rely on a database-level constraint. The `appointments` table utilizes a **partial unique index** (`uix_doctor_slot_active`) on `(doctor_id, slot_start)` strictly where `status IN ('held', 'confirmed')`. 

When two users concurrently attempt to hold the same slot:
1. Transaction A inserts the appointment and holds an exclusive lock on that index condition.
2. Transaction B attempts the same insert and is physically blocked at the PostgreSQL level.
3. Transaction A commits successfully.
4. Transaction B's insert fails with a hard `IntegrityError` raised from the unique constraint violation.
The FastAPI backend specifically catches this `IntegrityError` in the `patient.py` router and gracefully returns a `409 Conflict: Slot is no longer available` to User B, completely neutralizing the race condition natively.

## 2. Slot Hold & Time-to-Live (TTL) Mechanism
To ensure fairness during the booking flow, a patient is granted exactly 5 minutes to confirm their booking (handling payments, forms, etc.). If they abandon the flow, the slot must be freed up automatically so other patients aren't permanently locked out.

This is achieved via a TTL mechanism powered natively by `APScheduler`:
- **Hold Creation**: The `POST /api/patient/appointments/hold` endpoint inserts an appointment row with `status = 'held'` and computationally sets `held_until = now() + 5 minutes`. Because of the partial unique index discussed above, this locks the slot globally for all other users.
- **Confirmation**: If confirmed within 5 minutes, the endpoint updates the `status` to `confirmed`.
- **Automated Sweeper**: An in-memory APScheduler job (`cleanup_expired_holds` in `main.py`) runs on an exact 1-minute interval. It executes a highly efficient bulk `DELETE` query against the `appointments` table strictly targeting rows where `status == 'held'` and `held_until < now()`. This instantaneously returns the expired slots back to the global availability pool without any manual administrator intervention.

## 3. Leave-Day Cascading Conflicts
When an administrator marks a doctor as unavailable for a specific day, the system must adapt dynamically and resolve overlapping schedules.

The `POST /api/admin/doctors/{id}/leave` endpoint handles this by executing a cascading automated sequence:
1. **Creation**: It inserts a `DoctorLeaveDay` row, which dynamically removes time blocks for that date from any future patient availability queries.
2. **Detection**: It immediately queries all existing `confirmed` and `held` appointments assigned to that doctor on that specific date.
3. **Cancellation & Notification**: It loops through the affected appointments, updating their status to `cancelled`. Simultaneously, it pushes an event to the notification queue for a `cancellation` email and triggers the Calendar Service to issue an `events().delete()` command, instantly ripping the event from both the patient and doctor's connected Google Calendars. 

## 4. Asynchronous Fault-Tolerant Notifications
Transactional emails (and their network dependencies like SendGrid) can be notoriously slow or unreliable. Processing them inline with HTTP requests actively degrades user experience and creates timeout vulnerabilities.

We implemented an asynchronous fault-tolerant queue using the `notifications_log` database table:
- **Queueing**: Booking, cancelling, or automated scheduling endpoints immediately write a row to the table with `status='retrying'`, `retry_count=0`, and `next_retry_at=now()`. The endpoint then instantly responds to the user.
- **Dispatch**: A background sweeper (`process_pending_notifications`) runs every minute. It grabs pending rows, dynamically parses the required email context (e.g., booking confirmations vs medication reminders), and executes the SendGrid HTTP request.
- **Exponential Backoff**: If SendGrid fails (due to network timeout, API error, or missing keys), the database row is updated. `retry_count` is incremented by 1, and `next_retry_at` is scheduled using an exponential backoff formula: `5 * 3^(retry_count - 1)` minutes (retrying at 5m, 15m, and 45m intervals).
- **Finality**: If an email fails 3 consecutive times, its status permanently changes to `failed` to prevent infinite looping and alert administrators.
