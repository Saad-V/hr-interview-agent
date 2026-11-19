# HR Interviewer Agent

An HR screening application for fresher and 0–6 year candidates. It combines resume and
job-description intake, a guided interview, structured evaluation, and an HR scorecard to
support consistent human review.

## What it does

- Accepts candidate resumes and job descriptions, and lets the interviewer configure HR
  policy for a session.
- Runs an interview with text and voice interaction and keeps session and answer history.
- Evaluates answers against structured criteria. Salary-band and notice-period checks use
  configured policy, and evidence-backed flags are included in the scorecard.
- Produces a report with stage scores, interviewer notes, and an ATS-ready CSV export.
- Supports account registration, login, and authenticated interview history.

Interview results are decision support, not an automatic employment decision. A human
reviewer should assess the evidence and make hiring decisions.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL (Neon supported)
- **AI:** Gemini structured generation with model retries and fallback models
- **Frontend:** React, TypeScript, Vite
- **Optional speech service:** Deepgram

## Requirements

- Python 3.10 or later
- Node.js and npm
- A PostgreSQL database
- Gemini API credentials
- Optional: a Deepgram API key for speech-to-text features

## Local development

Run commands from the repository root.

### 1. Configure the backend

Create and activate a virtual environment, then install the Python dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS or Linux, activate the virtual environment with:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and provide the database URL, Gemini API keys, and a secure JWT secret:

```dotenv
DATABASE_URL=postgresql://<user>:<password>@<host>/<database>?sslmode=require
# Optional direct/unpooled connection used for migrations:
DATABASE_URL_UNPOOLED=
GEMINI_API_KEY=<primary-gemini-api-key>
GEMINI_API_KEY_2=<secondary-gemini-api-key>
JWT_SECRET_KEY=<random-secret-at-least-32-characters>

# Optional speech-to-text integration:
DEEPGRAM_STT_KEY=

# Optional deterministic compensation checks; set both or neither:
HR_SALARY_MIN_LPA=
HR_SALARY_MAX_LPA=
HR_NOTICE_MAX_DAYS=60
```

Do not commit `.env`, API keys, database URLs, or candidate documents. The backend loads
settings from the process environment and `.env`. If a tool writes credentials to
`.env.local`, copy the backend variables to `.env` or export them in the shell before
starting the API.

For salary alignment checks, configure both `HR_SALARY_MIN_LPA` and
`HR_SALARY_MAX_LPA`. If neither is configured, the app does not apply a configured salary
band. The notice-period limit defaults to 60 days.

### 2. Apply database migrations

From the repository root, with the virtual environment active and `.env` configured:

```sh
alembic upgrade head
```

When `DATABASE_URL_UNPOOLED` is set, Alembic uses it for migrations; otherwise it uses
`DATABASE_URL`.

### 3. Start the API

```sh
uvicorn app.main:app --reload
```

The API listens at `http://127.0.0.1:8000`. Interactive API documentation is available
at `http://127.0.0.1:8000/docs`.

### 4. Start the frontend

In another terminal:

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

The Vite development server proxies `/api` requests to the local API at
`http://127.0.0.1:8000`. To use another API base URL, set `VITE_API_URL` for the
frontend build or development server; it defaults to `/api/v1`.

## Useful commands

Run from the repository root:

```sh
# Build the frontend (also available as npm --prefix frontend run build)
npm run build

# Lint the frontend
npm --prefix frontend run lint

# Run the Python tests
python -m pip install pytest
python -m pytest
```

## API overview

The API is versioned under `/api/v1`. Common routes include:

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `POST /interview-sessions/` to create a session
- `POST /interview-sessions/{session_id}/resume` to upload a resume
- `POST /interview-sessions/{session_id}/job-description` to upload a job description
- `POST /interview-sessions/{session_id}/hr-policy` to configure session policy
- `POST /interview-sessions/{session_id}/begin` and `/start` to begin an interview
- `POST /interview-sessions/{session_id}/answer` to submit an answer
- `GET /interview-sessions/` and related session routes for history and reports
- `GET /interview-sessions/{session_id}/ats-export` to download a CSV scorecard

See `/docs` for request and response schemas.

## AI generation and report fallback

The default model order starts with `gemini-3.1-flash-lite`, followed by
`gemini-3.5-flash-lite`, `gemini-3.6-flash`, and `gemini-3.5-flash`. Generation requests
have a 60-second timeout and use bounded retries before moving to the next model. When
all configured models fail during report narrative generation, the backend can build a
deterministic summary from the recorded rubric evaluations.

## Neon

The root `neon.ts` declares the project's Neon configuration, including Realtime for
preview environments and branch-expiration behavior for new non-default branches. Use
the Neon CLI or dashboard to provision the project and provide its PostgreSQL connection
strings through environment variables. Keep credentials out of source control.

The application currently connects to PostgreSQL through SQLAlchemy. Uploaded resumes
and job-description files are stored under the local `storage/` directory; production
deployments should provide durable, access-controlled storage and protect candidate data.

## Project layout

```text
app/
  ai/              Gemini client, prompts, and output schemas
  api/v1/          FastAPI routes
  core/            Settings, security, and HR interview design
  db/              SQLAlchemy engine and session dependencies
  models/           Database models
  repositories/     Persistence queries
  schemas/          API request and response schemas
  services/         Interview, evaluation, reporting, and export logic
alembic/            Database migrations
frontend/src/       React application
tests/              Python tests
storage/            Local uploaded documents
```
