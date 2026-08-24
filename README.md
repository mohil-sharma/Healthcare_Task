# Healthcare Booking Platform

A full-stack healthcare appointment scheduling and management platform featuring robust concurrency, AI-driven pre/post-visit clinical summarizations (via Google Gemini), asynchronous transactional emails (via SendGrid), and native Google Calendar synchronization.

## Setup Instructions

### 1. Database Setup
This project uses a native local PostgreSQL 16 installation (avoiding Docker).
1. Ensure Homebrew is installed, then install Postgres: `brew install postgresql@16`
2. Run the provided database script to initialize and start the service:
   ```bash
   ./db.sh start
   ```

### 2. Backend Setup
The backend is powered by FastAPI and SQLAlchemy.
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment variables:
   ```bash
   cp .env.example .env
   ```
5. Run the Alembic migrations to build the schema:
   ```bash
   alembic upgrade head
   ```
6. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

---

## Environment Variables (`.env.example`)
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgresql+asyncpg://postgres:password@localhost:5432/healthcare`) |
| `JWT_SECRET` | Cryptographic secret used to sign authorization tokens. |
| `JWT_ALGORITHM` | Algorithm used for JWT (default: `HS256`). |
| `SENDGRID_API_KEY` | SendGrid API key for transactional emails. If left blank, the app gracefully mocks all emails. |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID for Google Calendar sync. If blank, OAuth flow natively mocks the connection. |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 Client Secret for Google Calendar. |
| `LLM_API_KEY` | Google Gemini API key. If left blank, pre/post visit endpoints gracefully fallback to raw text. |

---

## Google Calendar OAuth Setup
To enable real calendar syncing:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., "Healthcare Demo").
3. Enable the **Google Calendar API**.
4. Go to **APIs & Services > Credentials** -> Create Credentials -> **OAuth client ID**.
5. Set Application type to **Web application**.
6. Under **Authorized redirect URIs**, add exactly:
   `http://localhost:8000/api/calendar/callback`
7. Copy the generated **Client ID** and **Client Secret** into your `.env` file.

---

## Database Schema Highlights
- **users**: Central identities. `role` (`patient`, `doctor`, `admin`), `password_hash`, `google_refresh_token`.
- **doctor_profiles**: Links to `users`. Stores `specialisation`, JSON `working_hours`, and `slot_duration_minutes`.
- **doctor_leave_days**: Defines unavailable dates for doctors.
- **appointments**: Core scheduling table. Uses a partial unique index on `(doctor_id, slot_start)` to explicitly block concurrent double-bookings. Tracks `held_until` for TTL timeouts.
- **symptom_forms** & **pre_visit_summaries**: Free-text symptoms submitted by patients are processed into AI summaries containing an urgency level, chief complaint, and suggested questions.
- **prescriptions** & **post_visit_summaries**: Doctor clinical notes are translated into patient-friendly summaries. Prescriptions dictate medication reminder schedules.
- **notifications_log**: Asynchronous email queue table. Tracks `status`, `retry_count`, and `next_retry_at`.
- **calendar_events**: Maps appointments to generated `google_event_id` strings for accurate updating/deleting.

---

## LLM Prompts Used (Gemini 2.5 Flash)

**Pre-Visit Symptom Analysis:**
> `"Analyse these symptoms and return: urgency level (Low / Medium / High), chief complaint, and three suggested questions for the doctor. Symptoms: <{symptoms}>"`
*(Configured via `responseMimeType: application/json` to force strict JSON parsing)*

**Post-Visit Clinical Translation:**
> `"Convert these clinical notes into a patient-friendly summary with medication schedule and follow-up steps: <{notes}>"`

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/patient` | Register a new patient account |
| `POST` | `/api/auth/register/doctor` | Register a new doctor account |
| `POST` | `/api/auth/login` | Retrieve JWT access token |

### Patient Flow
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/patient/doctors` | Search doctors by specialisation |
| `GET` | `/api/patient/doctors/{id}/slots` | Compute dynamic availability slots |
| `POST` | `/api/patient/appointments/hold` | Locks slot for 5 mins (prevents concurrency) |
| `POST` | `/api/patient/appointments/{id}/confirm` | Confirms appointment & submits symptoms (triggers Pre-Visit LLM) |
| `POST` | `/api/patient/appointments/{id}/cancel` | Cancels appointment, triggers notifications & calendar deletion |
| `POST` | `/api/patient/appointments/{id}/reschedule` | Updates slot time and Calendar invite |
| `GET` | `/api/patient/appointments/{id}/post-visit-summary`| Fetches Patient-friendly LLM post-visit summary |

### Doctor Flow
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/doctor/appointments/{id}/pre-visit-summary` | Fetches AI-generated pre-visit breakdown |
| `POST` | `/api/doctor/appointments/{id}/post-visit` | Submits clinical notes & prescriptions |

### Admin Flow
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/admin/doctors` | Create new doctor profiles/settings |
| `POST` | `/api/admin/doctors/{id}/leave` | Sets leave day, cancels/cascades appointments |

### Google Calendar
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/calendar/auth?user_id={id}` | Redirects user to Google OAuth consent screen |
| `GET` | `/api/calendar/callback` | Exchanges code for refresh token, saves to DB |
