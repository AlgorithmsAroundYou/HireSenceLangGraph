# HireSence LangGraph

HireSence LangGraph is a FastAPI-based backend service that helps manage and review job descriptions and related resumes.

Core features:
- Chat endpoint backed by LangGraph / LangChain to interact with an LLM.
- Job Description (JD) review endpoint (`/jd/builder`) that refines and scores a raw JD.
- JD upload endpoint (`/jd/upload`) that stores JD files on disk and persists metadata in SQLite.
- Resume upload endpoint (`/resumes/upload`) linked to a JD.
- Resume listing endpoint (`/resumes`) to fetch resumes for a given JD.
- Basic user table and login endpoint (`/auth/login`).

The app uses:
- FastAPI
- Uvicorn
- SQLAlchemy (SQLite by default via `dev.db`)
- LangGraph / LangChain OpenAI

---

## 1. Prerequisites

- **Python 3.11+** (your environment is currently using Python 3.13)
- Git (optional, for source control)
- Internet access for LLM calls (OpenAI or compatible API), and the relevant API key set in your environment.

On both macOS and Windows you should know how to open a terminal:
- **macOS**: Terminal or iTerm2
- **Windows**: Command Prompt or PowerShell

---

## 2. Clone or copy the project

If you have not already, place the project at a location of your choice.

Example (if using Git):

```bash
git clone <your-repo-url> HireSenceLangGraph
cd HireSenceLangGraph
```

---

## 3. Create and activate a virtual environment

### macOS / Linux (bash / zsh)

```bash
cd HireSenceLangGraph
python -m venv .venv
source .venv/bin/activate
```

You should now see `(.venv)` at the beginning of your terminal prompt.

### Windows (Command Prompt)

```bat
cd HireSenceLangGraph
python -m venv .venv
.venv\Scripts\activate
```

### Windows (PowerShell)

```powershell
cd HireSenceLangGraph
python -m venv .venv
.venv\Scripts\Activate.ps1
```

To deactivate the environment on any OS:

```bash
deactivate
```

---

## 4. Install dependencies

With the virtual environment **activated**, install the Python requirements:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install FastAPI, Uvicorn, SQLAlchemy, LangGraph, LangChain OpenAI, and `python-multipart` (needed for file uploads).

---

## 5. Database initialization

By default, the app uses a SQLite database file named `dev.db` at the project root. Schema initialization SQL lives in `sql/init.sql` and includes:

- `user_details`
- `job_description_details`
- `resume_details`

If the app doesnt automatically initialize the database, you can run the SQL manually.

### Run the init script with SQLite (macOS & Windows)

Ensure `sqlite3` is installed and in your PATH, then run:

```bash
sqlite3 dev.db < sql/init.sql
```

> On Windows you may need to install SQLite from https://www.sqlite.org/download.html or use a DB GUI to run `sql/init.sql`.

---

## 6. Environment variables (LLM configuration)

The application uses LangGraph / LangChain OpenAI. Configure your OpenAI-compatible credentials as environment variables.

Example (OpenAI):

### macOS / Linux

```bash
export OPENAI_API_KEY="your_api_key_here"
```

### Windows (Command Prompt)

```bat
set OPENAI_API_KEY=your_api_key_here
```

### Windows (PowerShell)

```powershell
$env:OPENAI_API_KEY = "your_api_key_here"
```

Adjust names/values according to how `app/core/config.py` expects them (e.g. `OPENAI_API_KEY`, `OPENAI_BASE_URL`, etc.).

---

## 7. Run the application

From the project root, with the virtual environment active:

### macOS / Linux

```bash
python run.py
```

### Windows

```bat
python run.py
```

By default, Uvicorn will usually start on `http://127.0.0.1:8000` (or whatever `run.py` configures). Check the console output for the exact host/port.

---

## 8. Available endpoints (overview)

Base URL: `http://127.0.0.1:8000`

- `POST /chat`
  - Body: `{ "message": "..." }`
  - Returns: LLM response.

- `POST /auth/login`
  - Body: `{ "user_name": "...", "password": "..." }`
  - Returns: login result; uses `user_details` table.

- `POST /jd/builder`
  - Body: `{ "raw_jd_content": "..." }`
  - Returns: structured JD review (`updated_jd_content`, `score`, `suggestions`).

- `POST /jd/upload`
  - Multipart form-data
    - `file`: JD file (`.txt`, `.pdf`, `.doc`, `.docx`)
    - `uploaded_by`: optional string (e.g. username)
  - Saves file under `uploaded_jds/` and metadata to `job_description_details`.

- `GET /jd/{jd_id}`
  - Path parameter: `jd_id`
  - Returns JD metadata including `download` path.

- `POST /resumes/upload`
  - Multipart form-data + query/field:
    - `jd_id`: integer (required)  must reference an existing JD
    - `file`: resume file (`.txt`, `.pdf`, `.doc`, `.docx`)
    - `uploaded_by`: optional string
  - Saves file and metadata to `resume_details`.

- `GET /resumes?jd_id={id}`
  - Query parameter: `jd_id`
  - Returns list of resumes for that JD, including file locations.

You can also explore and test the API using FastAPIs automatic docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 9. Common troubleshooting

**1. Command `python` points to the wrong version**

- On macOS, you may need to use `python3` instead of `python` when creating the venv:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- On Windows, ensure Python is added to PATH during installation.

**2. `ModuleNotFoundError` for FastAPI or others**

- Make sure the virtual environment is activated and `pip install -r requirements.txt` has been run successfully.

**3. Database table not found errors**

- Ensure `dev.db` exists and `sql/init.sql` has been executed (either manually via `sqlite3` or automatically by the app initialization logic).

**4. File upload errors (415 / 422)**

- Confirm the request is `multipart/form-data` and that you are sending the `file` field (and `jd_id` for resume uploads).

---

## 10. Project structure (high level)

- `run.py`  Application entrypoint (starts FastAPI/Uvicorn).
- `app/`
  - `main.py` / `__init__.py`  FastAPI app wiring.
  - `api/routes.py`  All REST API endpoints.
  - `agents/`  LLM / LangGraph agent construction.
  - `core/`  Configuration and settings.
  - `models/`  SQLAlchemy models and DB session configuration.
  - `prompts/`  Prompt templates (e.g. JD review system prompt).
- `sql/init.sql`  Database schema initialization.
- `dev.db`  SQLite database file (created after init).
- `requirements.txt`  Python dependencies.

This README should give you enough to set up and run the application on both macOS and Windows.
