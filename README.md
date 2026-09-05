# Spec2Tests — AI-Powered Test Case Generator

Spec2Tests turns software specification documents (Business Requirements
Documents and, optionally, Functional Requirements Documents) into a
structured set of test cases using Google's Gemini API. Upload a **mandatory**
BRD (plus an optional FRD and free-text context) through the web UI, and the
backend extracts the document text, sends it to `gemini-3.6-flash`, and
returns a strict JSON array of test cases — ready to review in an interactive
table and export to Excel, CSV, or JSON.

```
User → React SPA (frontend/) → FastAPI backend (backend/app) → Google Gemini API
```

This repository contains two independently-run projects:

| Directory | What it is | Stack |
|---|---|---|
| `backend/` | FastAPI service exposing `POST /api/generate-test-cases` | Python 3.11, FastAPI, google-generativeai |
| `frontend/` | Single-page React app for uploading documents and viewing/exporting results | Node.js 20, React 18, TypeScript, Vite, Tailwind CSS |

This guide covers everything needed to run **both** locally: prerequisites,
environment configuration, install/run/test commands, the API contract, and
troubleshooting tips.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Repository Layout](#repository-layout)
3. [Quick Start (TL;DR)](#quick-start-tldr)
4. [Backend Setup](#backend-setup)
5. [Frontend Setup](#frontend-setup)
6. [Running the Full Stack Together](#running-the-full-stack-together)
7. [API Contract](#api-contract)
8. [Running Tests](#running-tests)
9. [Linting](#linting)
10. [Building for Production](#building-for-production)
11. [Environment Variables Reference](#environment-variables-reference)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Install the following before you begin:

| Tool | Required version | Check with |
|---|---|---|
| Python | 3.11.x (the backend's `pyproject.toml` pins `>=3.11,<3.12`) | `python3 --version` |
| Node.js | 20 LTS | `node --version` |
| npm | bundled with Node 20 (npm 10+) | `npm --version` |
| A Google Gemini API key | free tier available at [Google AI Studio](https://ai.google.dev/) | — |

Git is assumed to already be installed since you have this repository
checked out.

> **macOS/Linux vs Windows:** the commands below use POSIX shell syntax
> (`cp`, `source`, forward-slash paths). On Windows, use PowerShell/WSL
> equivalents (e.g. `copy` instead of `cp`, `venv\Scripts\activate` instead
> of `source venv/bin/activate`).

---

## Repository Layout

```
spec2tests/
├── requirements.txt          # convenience copy of backend/requirements.txt (repo root)
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py            # create_app(): FastAPI factory, CORS, routers
│   │   ├── config.py          # get_settings(): env-driven Settings singleton
│   │   ├── models/            # Pydantic schemas (TestCase, etc.)
│   │   ├── routers/           # HTTP endpoints (generate_test_cases, documents, generation)
│   │   └── services/          # extraction.py (pypdf/docx), gemini_service.py
│   ├── tests/                 # pytest suite (12 modules)
│   ├── requirements.txt       # backend Python dependencies
│   ├── pyproject.toml         # ruff config + pytest options
│   ├── pytest.ini             # canonical pytest config
│   └── .env.example           # backend environment variable template
└── frontend/                  # React + TypeScript + Vite SPA
    ├── src/
    │   ├── main.tsx / App.tsx
    │   ├── lib/                # api.ts, export.ts, types.ts, utils.ts
    │   ├── hooks/               # useTestCaseGeneration.ts
    │   └── components/          # FileUploadPanel, TestCaseTable, ExportToolbar, ui/*
    ├── package.json
    ├── vite.config.ts
    └── .env.example            # frontend environment variable template
```

---

## Quick Start (TL;DR)

Open **two terminals** — one for the backend, one for the frontend.

**Terminal 1 — backend (from repo root):**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=<your-key>
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — frontend (from repo root):**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Then open **http://localhost:5173** in your browser. Upload a BRD (required),
optionally an FRD and/or context notes, click **Generate Test Cases**, and
review/export the results.

The sections below walk through each step in detail.

---

## Backend Setup

All commands in this section are run from the `backend/` directory unless
noted otherwise.

### 1. Create and activate a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs (pinned in `backend/requirements.txt`): `fastapi==0.115.0`,
`uvicorn[standard]==0.30.6`, `pydantic==2.9.2`, `pypdf==4.3.1`,
`python-docx==1.1.2`, `google-generativeai==0.8.3`, `python-dotenv==1.0.1`,
`python-multipart==0.0.9`, plus test/lint tooling (`pytest==8.3.3`,
`pytest-mock==3.14.0`, `httpx==0.27.2`, `ruff==0.6.9`).

> A convenience copy of the same dependency list also exists at the repo
> root (`requirements.txt`) if you prefer to install without `cd`-ing into
> `backend/` first — e.g. `pip install -r requirements.txt` from the repo
> root followed by `cd backend`.

### 3. Configure environment variables

Copy the example file and fill in your Gemini API key:

```bash
cp .env.example .env
```

Open `backend/.env` and set, at minimum:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-key-here
```

See [Environment Variables Reference](#environment-variables-reference) for
every supported variable and its default. `backend/app/config.py` loads
`.env` automatically on startup via `python-dotenv` (values already present
in your shell environment always take precedence over the file).

> **Note:** without a valid `GEMINI_API_KEY`, the server still starts (it
> logs a warning), but any call to `POST /api/generate-test-cases` will fail
> with an HTTP 502 once it reaches the Gemini API call.

### 4. Run the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload` enables hot-reload on source changes (development only).
- The server binds to `0.0.0.0:8000` by default (overridable via `HOST`/`PORT`
  env vars, though the `uvicorn` CLI flags above take precedence over the
  in-app `Settings.host`/`Settings.port` values unless you instead run
  `python -m app.main` style — the `--host`/`--port` CLI flags shown here are
  the recommended way to run locally).

### 5. Verify it's running

```bash
curl http://localhost:8000/health
# => {"status":"ok"}
```

Interactive API docs (Swagger UI) are available at
**http://localhost:8000/docs**, and the raw OpenAPI schema at
**http://localhost:8000/openapi.json**.

---

## Frontend Setup

All commands in this section are run from the `frontend/` directory unless
noted otherwise.

### 1. Install dependencies

```bash
cd frontend
npm install
```

Key dependencies (see `frontend/package.json`):
- Runtime: `react`, `react-dom`, `class-variance-authority`, `clsx`,
  `tailwind-merge`, `lucide-react`, `xlsx`
- Dev/build: `vite`, `@vitejs/plugin-react`, `typescript`, `tailwindcss`,
  `postcss`, `autoprefixer`, `eslint` + `@typescript-eslint/*`
- Testing: `vitest`, `@testing-library/react`, `@testing-library/user-event`,
  `@testing-library/jest-dom`, `jsdom`

### 2. Configure environment variables

```bash
cp .env.example .env
```

`frontend/.env` should contain:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

This must point at wherever your backend from the previous section is
running. Vite only exposes variables prefixed with `VITE_` to client code
(via `import.meta.env`, consumed in `frontend/src/lib/api.ts`). If this
variable is unset, the app falls back to `http://localhost:8000` in code.

### 3. Run the development server

```bash
npm run dev
```

Vite starts the dev server on **http://localhost:5173** (configured in
`frontend/vite.config.ts`). Open that URL in your browser.

> **CORS reminder:** the backend's default `CORS_ORIGINS` already includes
> `http://localhost:5173` and `http://localhost:3000` (see
> `backend/app/config.py`), so no backend changes are needed for the default
> ports. If you change the frontend's dev port, add it to `CORS_ORIGINS` in
> `backend/.env`.

---

## Running the Full Stack Together

1. Start the backend first (Terminal 1): follow [Backend Setup](#backend-setup)
   steps 1–4, ending with `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
   running and listening on port 8000.
2. Start the frontend (Terminal 2): follow [Frontend Setup](#frontend-setup)
   steps 1–3, ending with `npm run dev` running on port 5173.
3. Browse to **http://localhost:5173**.
4. Upload a BRD file (`.pdf`, `.docx`, or `.txt`) — this is mandatory; the
   "Generate Test Cases" button stays disabled with an inline error until a
   BRD is selected.
5. Optionally upload an FRD file and/or type free-text context.
6. Click **Generate Test Cases**. The app calls
   `POST http://localhost:8000/api/generate-test-cases` with a
   `multipart/form-data` body (`brd_file`, `frd_file`, `context`), and
   Gemini returns a structured list of test cases rendered in a table.
7. Use the export toolbar to download the results as **Excel (.xlsx)**,
   **CSV**, or **JSON** — all generated fully client-side, no additional
   backend calls required.

---

## API Contract

The frontend is built against this contract; if you build your own client
against the backend, adhere to the same shape.

### `POST /api/generate-test-cases`

- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `brd_file` (file, **required**) — `.pdf`, `.docx`, or `.txt`. Missing or
    empty filename → `400 Bad Request` with
    `{"detail": "BRD file is mandatory. Please upload a Business Requirements Document (.pdf, .docx, or .txt) to generate test cases."}`.
  - `frd_file` (file, optional) — same accepted types as BRD.
  - `context` (string, optional) — free-text notes appended to the prompt.
- **Success response:** `200 OK` with a **raw JSON array** (not wrapped in
  an envelope) of test case objects:

```json
[
  {
    "id": "TC-001",
    "requirement_reference": "BRD-2.1",
    "title": "User can log in with valid credentials",
    "description": "Verifies that a registered user can successfully authenticate using a valid username and password.",
    "preconditions": ["A registered user account exists."],
    "steps": [
      "Navigate to the login page.",
      "Enter a valid username and password.",
      "Click the 'Log In' button."
    ],
    "expected_result": "The user is authenticated and redirected to the dashboard.",
    "priority": "High",
    "type": "Functional"
  }
]
```

  These fields map to the seven required table columns: **Test Case ID**
  (`id`), **Requirement Reference** (`requirement_reference`), **Test
  Scenario** (`title`), **Pre-conditions** (`preconditions`), **Test Steps**
  (`steps`), **Expected Result** (`expected_result`), **Priority**
  (`priority`). `description` and `type` are additional fields returned by
  the API but not part of the mandatory seven-column table.

- **Error responses:**
  - `400 Bad Request` — BRD missing, or an uploaded file is unsupported or
    unreadable. Body: `{"detail": "<human-readable message>"}`.
  - `502 Bad Gateway` — the Gemini API request failed or its response could
    not be parsed into valid test cases. Body: `{"detail": "<message>"}`.

Other existing endpoints (`/api/documents/extract`, `/api/generate/test-cases`,
`/`, `/health`) are documented interactively at `http://localhost:8000/docs`
once the backend is running.

---

## Running Tests

### Backend (pytest)

From `backend/` (with the virtual environment activated):

```bash
cd backend
pytest
```

This runs the full suite (12 test modules) using the configuration in
`backend/pytest.ini` (`testpaths = tests`, `pythonpath = .`). To run a single
file or filter by keyword:

```bash
pytest tests/test_generate_test_cases_endpoint.py
pytest -k "gemini"
```

Tests that exercise the Gemini integration mock the `google-generativeai`
client, so a real `GEMINI_API_KEY` is **not** required to run the test
suite.

### Frontend (Vitest)

From `frontend/`:

```bash
cd frontend
npm test
```

This runs `vitest run` (configured in `frontend/vitest.config.ts`, using
`jsdom` and `@testing-library/react`) against all `*.test.ts`/`*.test.tsx`
files (e.g. `useTestCaseGeneration.test.ts`, `FileUploadPanel.test.tsx`,
`TestCaseTable.test.tsx`, `export.test.ts`).

---

## Linting

**Backend** (ruff, configured in `backend/pyproject.toml`):

```bash
cd backend
ruff check .
```

**Frontend** (ESLint + `@typescript-eslint`, configured in
`frontend/.eslintrc.cjs`):

```bash
cd frontend
npm run lint
```

---

## Building for Production

**Frontend production build:**

```bash
cd frontend
npm run build      # runs `tsc -b && vite build`, outputs to frontend/dist/
npm run preview    # serve the production build locally for a smoke test
```

The build output in `frontend/dist/` is a fully static bundle (HTML/CSS/JS)
that can be served by any static file host or reverse-proxied behind the
backend; it still calls the backend over HTTP using `VITE_API_BASE_URL`
baked in at build time, so set that variable correctly (e.g. to your
production backend's public URL) before running `npm run build`.

**Backend production run:**

For local/POC purposes, running Uvicorn directly (without `--reload`) is
sufficient:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For a real production deployment, put Uvicorn behind a process
manager/ASGI server setup of your choice (e.g. Gunicorn with Uvicorn
workers, or a container orchestrator) and ensure `DEBUG=false` and a
restrictive `CORS_ORIGINS` are set via environment variables rather than a
committed `.env` file.

---

## Environment Variables Reference

### Backend (`backend/.env`, see `backend/.env.example`)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Spec2Tests` | Human-readable application name (logs/docs). |
| `APP_ENV` | `development` | Deployment environment identifier: `development` \| `staging` \| `production`. |
| `DEBUG` | `true` | Enables verbose debug behaviour (FastAPI docs, detailed errors). Accepted truthy values: `1`, `true`, `yes`, `on`. |
| `HOST` | `0.0.0.0` | Host the app's internal `Settings` records (informational; the `uvicorn` CLI `--host` flag is what actually binds the socket when using the command in this guide). |
| `PORT` | `8000` | Same caveat as `HOST` — pair with `uvicorn ... --port`. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed CORS origins for the frontend SPA. |
| `GEMINI_API_KEY` | *(empty)* | **Required** for test case generation to function. Get one from [Google AI Studio](https://ai.google.dev/). |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model used for generation. |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum accepted upload size per file, in megabytes. |
| `ALLOWED_UPLOAD_EXTENSIONS` | `.pdf,.docx,.txt` | Comma-separated list of accepted BRD/FRD file extensions. |
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL`. |

### Frontend (`frontend/.env`, see `frontend/.env.example`)

| Variable | Default (if unset) | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL of the Spec2Tests backend, with no trailing slash. Consumed via `import.meta.env.VITE_API_BASE_URL` in `frontend/src/lib/api.ts`. |

---

## Troubleshooting

**"BRD file is mandatory" error even though I selected a file.**
Make sure the file has a filename (some drag-and-drop flows can produce a
`File` object without one) and that you're using the "Generate Test Cases"
button, not submitting an empty form. This message also surfaces if the
backend receives no `brd_file` field at all — check the Network tab to
confirm the request is `multipart/form-data` with a `brd_file` part.

**Frontend shows "Could not reach the Spec2Tests backend at http://localhost:8000".**
The backend isn't running, is bound to a different port, or
`VITE_API_BASE_URL` in `frontend/.env` doesn't match where it's actually
listening. Confirm with `curl http://localhost:8000/health`, then restart
the Vite dev server after editing `.env` (Vite only reads env files at
startup).

**Browser console shows a CORS error.**
The frontend's origin (e.g. `http://localhost:5173`) isn't present in the
backend's `CORS_ORIGINS`. Add it to `backend/.env` and restart the backend.

**`POST /api/generate-test-cases` returns `502 Bad Gateway`.**
This means the request reached the backend and passed validation, but the
call to the Gemini API failed or returned an unparsable response. Common
causes: missing/invalid `GEMINI_API_KEY`, network connectivity issues to
Google's API, or exceeding a quota. Check the backend's server logs (stdout)
for the underlying error message.

**`pip install -r requirements.txt` fails on Python version.**
The backend requires Python `>=3.11,<3.12` (see `backend/pyproject.toml`).
Run `python3 --version` to confirm, and use `pyenv`/`asdf`/your OS package
manager to install 3.11 if needed before creating the virtual environment.

**`npm install` fails or produces peer-dependency warnings.**
Confirm you're on Node.js 20 LTS (`node --version`). If issues persist, try
a clean install: `rm -rf node_modules package-lock.json && npm install`.

**Uploaded `.docx`/`.pdf` file is rejected or extraction produces empty text.**
Only `.pdf`, `.docx`, and `.txt` are supported (see
`ALLOWED_UPLOAD_EXTENSIONS`). Password-protected or image-only (scanned)
PDFs with no extractable text layer will fail extraction — the backend
returns a `400` with a descriptive message in that case.

**Tests fail with "GEMINI_API_KEY not configured" style errors.**
The backend test suite mocks the Gemini client and does not require a real
API key. If you see this, ensure you're running `pytest` from the `backend/`
directory (or that `pythonpath = .` in `backend/pytest.ini` is being
respected) so the app's test fixtures load correctly.
