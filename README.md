# HireSence LangGraph

HireSence LangGraph is a FastAPI-based backend service that helps manage and review software job descriptions (JDs) and related resumes, powered by LangGraph / LangChain and an LLM.

Core features:
- **Chat endpoint** backed by LangGraph / LangChain to interact with an LLM.
- **Job Description (JD) review endpoint** (`POST /jd/builder`) that accepts raw JD text and returns a **structured JSON evaluation + improved JD**.
- **JD upload endpoint** (`POST /jd/upload`) that stores JD files on disk and persists metadata in SQLite.
- **Resume upload endpoint** (`POST /resumes/upload`) linked to a JD.
- **Resume listing endpoint** (`GET /resumes`) to fetch resumes for a given JD.
- **Basic user table and login** endpoint (`POST /auth/login`).

The JD review logic uses a strict system prompt that:
- Enforces **no hallucinations** for critical fields (company, location, stack, etc.).
- Evaluates JDs against a **core checklist** (title, stack, infra/DevOps, responsibilities, experience, culture, work model, domain, company context, work culture, growth & impact).
- Always returns an **`improved_jd`** string with clear section headers (Role Title, Role Overview, Responsibilities, Required Skills & Experience, Domain Knowledge, Work Model & Location, Work Culture & Ways of Working), using placeholders for missing information.

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

If the app doesn’t automatically initialize the database, you can run the SQL manually.

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

## 7.1 Authentication & security token

Most endpoints are protected and require a token. The login endpoint `/auth/login` returns a `token` field.

Example response:

```json
{
  "success": true,
  "message": "Login successful",
  "token": "<your-token>"
}
```

To call protected endpoints from tools like Postman or curl, include the token as an `Authorization` header (conventionally as a Bearer token):

```bash
-H "Authorization: Bearer <your-token>"
```

Any request to protected routes without a valid token will receive `401 Not authenticated` or `403 Forbidden` depending on user status.

---

## 8. Available endpoints (overview)

Base URL: `http://127.0.0.1:8000/api`

### 8.1 `POST /chat`

- **Auth**: Required.
- **Body (JSON)**:

  ```json
  { "message": "..." }
  ```

- **Response**:

  ```json
  { "response": "LLM response text" }
  ```

---

### 8.2 `POST /auth/login`

- **Auth**: Not required.
- **Body (JSON)**:

  ```json
  { "user_name": "...", "password": "..." }
  ```

- **Response**:

  ```json
  {
    "success": true,
    "message": "Login successful",
    "token": "<your-token>"
  }
  ```

---

### 8.3 `POST /jd/builder`

JD review & builder endpoint using the new **raw text + structured JSON** contract.

- **Auth**: Required.
- **Headers**:
  - `Authorization: Bearer <your-token>`
  - `Content-Type: text/plain; charset=utf-8`
- **Body**: Raw text containing the job description (can be long, include emojis and special characters).

  Example request (curl):

  ```bash
  curl -X POST "http://127.0.0.1:8000/jd/builder" \
    -H "Authorization: Bearer <your-token>" \
    -H "Content-Type: text/plain; charset=utf-8" \
    --data-binary $'Senior Backend Engineer\n\nWe are looking for a Senior Backend Engineer with experience in Java, Spring Boot, and microservices...' 
  ```

- **Response model**: `JobReviewResponse1`

  ```jsonc
  {
    "message": {
      "jd_strength_score": 0-100,
      "checkpoints": {
        "standardized_job_title": "PASS|WEAK|MISSING",
        "primary_technical_stack": "PASS|WEAK|MISSING",
        "infrastructure_devops": "PASS|WEAK|MISSING",
        "responsibilities": "PASS|WEAK|MISSING",
        "experience": "PASS|WEAK|MISSING",
        "engineering_culture": "PASS|WEAK|MISSING",
        "education_equivalent": "PASS|WEAK|MISSING",
        "soft_skills": "PASS|WEAK|MISSING",
        "work_model_location": "PASS|WEAK|MISSING",
        "domain_knowledge_business_context": "PASS|WEAK|MISSING",
        "company_product_context": "PASS|WEAK|MISSING",
        "work_culture_ways_of_working": "PASS|WEAK|MISSING",
        "growth_impact": "PASS|WEAK|MISSING"
      },
      "critical_gaps_technical": ["..."],
      "critical_gaps_administrative": ["..."],
      "dx_suggestions": ["..."],
      "summary": "short natural-language summary",
      "conclusion": "Ready to Post" | "Revision Needed for Tech Competitiveness and Clarity",
      "improved_jd": "Full improved JD as a single string, with headers like 'Role Title', 'About the Role', 'Key Responsibilities', 'Required Skills & Experience', 'Domain Knowledge', 'Work Model & Location', 'Work Culture & Ways of Working'. Missing critical details are represented with placeholders such as [Insert location], [Insert primary tech stack], etc."
    }
  }
  ```

Notes:
- The backend enforces that the LLM returns **a single-line JSON object**, which is parsed and exposed as `message`.
- `improved_jd` is **always populated** and structured with clear headers that map to the core checklist.
- When information is missing, placeholders are used, and corresponding entries are added under `critical_gaps_technical` / `critical_gaps_administrative` with suggestions for what to fill in.

---

### 8.4 `POST /jd/upload`

- **Auth**: Required.
- **Content type**: `multipart/form-data`
- **Fields**:
  - `file`: JD file (`.txt`, `.pdf`, `.doc`, `.docx`)
  - `uploaded_by`: optional string (e.g. username)

- **Response** (`JobUploadResponse`):

  ```json
  {
    "jd_id": 1,
    "file_name": "sample_jd.txt",
    "file_saved_location": "uploaded_jds/sample_jd.txt"
  }
  ```

---

### 8.5 `GET /jd/{jd_id}`

- **Auth**: Required.
- **Path parameter**: `jd_id` (int)
- **Response** (`JobDetailsResponse`):

  ```json
  {
    "jd_id": 1,
    "file_name": "sample_jd.txt",
    "uploaded_by": "user1",
    "created_date": "2026-02-10T12:34:56.000000",
    "download": "uploaded_jds/sample_jd.txt"
  }
  ```

---

### 8.6 `POST /resumes/upload`

- **Auth**: Required.
- **Content type**: `multipart/form-data`
- **Fields**:
  - `jd_id`: integer (required) – must reference an existing JD
  - `file`: resume file (`.txt`, `.pdf`, `.doc`, `.docx`)
  - `uploaded_by`: optional string

- **Response** (`ResumeUploadResponse`):

  ```json
  {
    "resume_id": 1,
    "jd_id": 1,
    "file_name": "candidate_resume.pdf",
    "file_location": "uploaded_resumes/candidate_resume.pdf"
  }
  ```

---

### 8.7 `GET /resumes?jd_id={id}`

- **Auth**: Required.
- **Query parameter**: `jd_id` (int)
- **Response** (`ResumeListResponse`):

  ```json
  {
    "resumes": [
      {
        "resume_id": 1,
        "jd_id": 1,
        "file_name": "candidate_resume.pdf",
        "file_location": "uploaded_resumes/candidate_resume.pdf",
        "uploaded_by": "user1",
        "created_date": "2026-02-10T12:40:00.000000"
      }
    ]
  }
  ```

---

### 8.8 `GET /jd/{jd_id}/analysis`

List analysis results (match scores and processing status) for all resumes belonging to a given JD.

- **Auth**: Required.
- **Path parameter**: `jd_id` (int)
- **Response** (`ResumeAnalysisListResponse`):

  ```json
  {
    "items": [
      {
        "resume_id": 1,
        "jd_id": 1,
        "file_name": "candidate_resume.pdf",
        "match_score": 0.87,
        "status": "processed",
        "failure_reason": null
      }
    ]
  }
  ```

---

## 9. API docs

FastAPI provides automatic interactive documentation:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Use these to explore schemas (including the JSON published by `/jd/builder`) and test endpoints.

---

## 10. Project structure (high level)

- `run.py` – Application entrypoint (starts FastAPI/Uvicorn).
- `app/`
  - `main.py` / `__init__.py` – FastAPI app wiring.
  - `api/routes.py` – All REST API endpoints.
  - `agents/` – LLM / LangGraph agent construction.
  - `core/` – Configuration and settings.
  - `models/` – Pydantic API models & SQLAlchemy models / DB session configuration.
  - `prompts/` – Prompt templates (e.g. JD review system prompt with JSON output).
- `sql/init.sql` – Database schema initialization.
- `dev.db` – SQLite database file (created after init).
- `requirements.txt` – Python dependencies.

---

## 11. Common troubleshooting

1. **`python` points to the wrong version**
   - On macOS, you may need to use `python3` instead of `python` when creating the venv:

     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

   - On Windows, ensure Python is added to PATH during installation.

2. **`ModuleNotFoundError` for FastAPI or others**
   - Make sure the virtual environment is activated and `pip install -r requirements.txt` has been run successfully.

3. **Database table not found errors**
   - Ensure `dev.db` exists and `sql/init.sql` has been executed (either manually via `sqlite3` or automatically by the app initialization logic).

4. **File upload errors (415 / 422)**
   - Confirm the request is `multipart/form-data` and that you are sending the `file` field (and `jd_id` for resume uploads).

5. **`/jd/builder` returns 500 with `"Model returned invalid JSON"`**
   - This means the LLM response was not valid JSON. Retry the request; if it persists, inspect logs and the raw LLM output. The system prompt is designed to strongly enforce a single-line JSON object.

This README reflects the current `/jd/builder` behavior (raw text in, structured JSON out) and the no-hallucination, placeholder-based JD improvement logic.
