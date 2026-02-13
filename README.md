# HireSence LangGraph

> FastAPI backend for reviewing job descriptions (JDs) and resumes using LangGraph / LangChain and an LLM.

---

<div style="background:#0f172a; color:#f9fafb; padding:18px 20px; border-radius:12px; border:1px solid #1f2937;">

## 1. Overview

HireSence LangGraph is a FastAPI-based backend service that helps manage and review software job descriptions (JDs) and related resumes.

**Core features:**
- **Chat endpoint** backed by LangGraph / LangChain to interact with an LLM.
- **JD review endpoint** that accepts raw JD text and returns **structured JSON evaluation + improved JD**.
- **JD upload endpoint** that stores JD files on disk and persists metadata in SQLite/Postgres.
- **Resume upload & analysis pipeline** linked to a JD, including background processing.
- **Feedback loop** so reviewers can label resumes (good_fit / bad_fit / maybe) and leave comments.
- **Business status** field to track resume pipeline status (e.g., interview_scheduled, rejected).

**Tech stack:** FastAPI, Uvicorn, SQLAlchemy, LangGraph / LangChain, OpenAI-compatible LLMs, SQLite/Postgres.

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 2. How the Core Resume–JD Analysis Flow Works

This section explains the **end-to-end business flow** the backend implements.

### 2.1 Core business idea

Companies receive **many resumes per JD**, but only a few are a strong fit. Manually screening every resume is:
- Slow and inconsistent between reviewers.
- Hard to trace (why did we shortlist this candidate?).
- Difficult to optimize over time.

HireSence LangGraph turns each JD + resume pair into a **structured evaluation object**:
- A **single match_score** for quick ranking.
- A **dimension-wise breakdown** (skills, domain, seniority, communication, culture fit, stability, red flags, recommendation) so humans understand *why*.
- **Issues and recommendations** that explain risks or gaps.
- **Candidate contact + summary** so the frontend can build a compact review view.
- **Human labels (feedback)** and **business_status** to close the loop.

This data is stored in relational tables and exposed via clean REST APIs so the frontend can:
- Sort and filter by match_score or dimension scores.
- Quickly shortlist / reject / schedule interviews.
- Compare **LLM judgment vs human labels** for quality monitoring.

### 2.2 High-level flow

1. **Upload JD**  
   A recruiter uploads a JD file (`/api/jd/upload`). The backend stores the file, creates a `job_description_details` record, and initializes counters like `resumes_uploaded_count`.

2. **(Optional) JD Review & Improvement**  
   The recruiter can send the raw JD text to `/api/jd/builder`. An LLM (via LangGraph / LangChain) reviews the JD and returns:
   - A **quality score** (`jd_strength_score`).
   - A breakdown of **checkpoints** (e.g., role clarity, requirements specificity, benefits clarity).
   - **Critical gaps** and **DX suggestions**.
   - A fully **improved JD text** ready to publish.

3. **Upload Resumes for that JD**  
   Resumes are uploaded to `/api/resumes/upload?jd_id=<id>`. For each file the service:
   - Saves it under `uploaded_resumes/<jd_id>/...`.
   - Inserts a `resume_details` row with `status='pending'` and basic metadata.

4. **Background LLM Analysis (Resume vs JD)**  
   A worker (triggered via `/api/resumes/process-once` or on a schedule) processes pending resumes:
   - Reads **JD content** and **resume content** from disk.
   - Calls the **resume analysis agent** (LangGraph) with a strict JSON schema defined in `RESUME_ANALYSIS_SYSTEM_PROMPT`.
   - The prompt instructs the LLM to:
     - Extract **candidate_name**, **candidate_email**, **candidate_phone** (top-level keys).
     - Compute an overall **match_score**.
     - Generate a **summary** and an array of **issues**.
     - Score multiple **dimensions** (core_skills, domain_experience, seniority, communication, culture_fit, stability, red_flags, overall_recommendation) each with a `score` and `note`.
     - Return a **single valid JSON object** only.

5. **Persisting Analysis Results**  
   The worker parses the LLM JSON and writes it into the database:
   - Updates `resume_details` with:
     - `candidate_name`, `candidate_email`, `candidate_phone`.
     - `match_score`, `status` (`processed` or `error`), `failure_reason`.
   - Inserts a row into `resume_analysis_details` with:
     - `analysis_json` (raw LLM JSON).
     - `summary`, `issues`.
     - Per-dimension `*_score` and `*_note` columns.
     - Audit fields `processed_at`, `processed_by`.
   - Increments `processed_resumes_count` on the related `job_description_details` row.

6. **Frontend Consumption**  
   The frontend then calls:
   - `GET /api/resumes?jd_id=<id>` to list resumes with **candidate contact + match_score + statuses**.
   - `GET /api/jd/<jd_id>/analysis` for a compact list of analysis summaries (per resume).
   - `GET /api/resumes/<resume_id>/analysis` for **full detail** (summary, issues, dimensions, raw JSON).
   - `POST /api/resumes/<resume_id>/feedback` for human feedback (`good_fit` / `bad_fit` / `maybe`).
   - `PATCH /api/resumes/<resume_id>/status` to manage the business pipeline (e.g., `interview_scheduled`).

### 2.3 Why this design

- **Separation of concerns**: File storage, DB models, LLM prompts, and API contracts are cleanly separated.
- **Traceability**: Raw LLM JSON is preserved in `analysis_json`, while key fields are denormalized into columns for fast querying and UI display.
- **Safety & structure**: The resume analysis prompt enforces a strict JSON schema, reducing parsing errors and hallucinations.
- **Feedback loop**: `resume_feedback` records let you compare **LLM scores** vs **human labels**, enabling future model tuning or analytics.

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 3. Database Schema (Tables, Columns & Sample Data)

> Logical schema based on `sql/init.sql`. Types shown for SQLite; Postgres equivalents are similar.

### 3.1 `user_details`

| Column           | Type        | Notes                         |
|------------------|------------|-------------------------------|
| id               | INTEGER PK | Auto-increment user ID        |
| user_name        | TEXT       | Login / username              |
| password_hash    | TEXT       | Hashed password               |
| full_name        | TEXT       | Display name                  |
| is_active        | INTEGER    | 1 = active, 0 = inactive      |
| created_at       | DATETIME   | Creation timestamp            |

**Sample row:**
```sql
INSERT INTO user_details (id, user_name, password_hash, full_name, is_active, created_at)
VALUES (1, 'admin', '<hashed_pw>', 'Admin User', 1, '2026-02-10T12:00:00');
```

---

### 3.2 `job_description_details`

| Column                   | Type        | Notes                                     |
|--------------------------|------------|-------------------------------------------|
| id                       | INTEGER PK | JD ID                                     |
| file_name                | TEXT       | Original JD file name                     |
| file_location            | TEXT       | Path on disk                              |
| uploaded_by              | TEXT       | Username or system                        |
| title                    | TEXT       | Parsed title                              |
| parsed_summary           | TEXT       | Summary from JD review                    |
| status                   | TEXT       | e.g. `active`, `archived`                 |
| is_active                | INTEGER    | 1/0                                       |
| created_date             | DATETIME   | Created at                                |
| updated_at               | DATETIME   | Last update                               |
| last_reviewed_at         | DATETIME   | Last JD analysis time                     |
| last_reviewed_by         | TEXT       | User who last reviewed                    |
| resumes_uploaded_count   | INTEGER    | Total resumes uploaded for this JD        |
| processed_resumes_count  | INTEGER    | Resumes that have been analyzed           |

**Sample row:**
```sql
INSERT INTO job_description_details
(id, file_name, file_location, uploaded_by, title, parsed_summary, status, is_active,
 created_date, updated_at, last_reviewed_at, last_reviewed_by,
 resumes_uploaded_count, processed_resumes_count)
VALUES
(1, 'backend_jd.pdf', 'uploaded_jds/backend_jd.pdf', 'admin',
 'Senior Backend Engineer', 'Backend role in fintech team', 'active', 1,
 '2026-02-10T10:00:00', '2026-02-10T10:00:00', NULL, NULL,
 0, 0);
```

---

### 3.3 `resume_details`

| Column             | Type        | Notes                                                   |
|--------------------|------------|---------------------------------------------------------|
| id                 | INTEGER PK | Resume ID                                               |
| jd_id              | INTEGER FK | References `job_description_details.id`                 |
| file_name          | TEXT       | Original resume filename                                |
| file_location      | TEXT       | Stored path `UPLOAD_DIR_RESUME/<jd_id>/...`            |
| candidate_name     | TEXT       | Extracted from resume (may be NULL)                     |
| candidate_email    | TEXT       | Extracted email (may be NULL)                           |
| candidate_phone    | TEXT       | Extracted phone (may be NULL)                           |
| parsed_summary     | TEXT       | Optional extracted summary                              |
| parsed_skills      | TEXT       | Optional skills list (comma-separated / JSON)          |
| match_score        | REAL       | Overall match score (0.0–1.0 or 0–100 scaled)          |
| status             | TEXT       | Processing status: `pending` / `processed` / `error`   |
| business_status    | TEXT       | Human pipeline status (e.g., `interview_scheduled`)    |
| failure_reason     | TEXT       | Error message if processing failed                      |
| created_at         | DATETIME   | Uploaded at                                             |
| updated_at         | DATETIME   | Last updated                                            |

**Sample rows:**
```sql
INSERT INTO resume_details
(id, jd_id, file_name, file_location, candidate_name, candidate_email, candidate_phone,
 parsed_summary, parsed_skills, match_score, status, business_status, failure_reason,
 created_at, updated_at)
VALUES
(1, 1, 'Rahul_Kodati_Resume.pdf', 'uploaded_resumes/1/Rahul_Kodati_Resume.pdf',
 'Rahul Kodati', 'rahul@example.com', '+1-555-123-4567',
 'Backend engineer with 6+ years in Python and microservices.',
 'Python, FastAPI, PostgreSQL, Docker, Kubernetes', 0.89,
 'processed', 'interview_scheduled', NULL,
 '2026-02-11T09:00:00', '2026-02-11T09:15:00');
```

---

### 3.4 `resume_analysis_details`

Detailed scores & notes per dimension for each processed resume.

| Column                     | Type        | Notes                                           |
|----------------------------|------------|-------------------------------------------------|
| id                         | INTEGER PK | Analysis ID                                     |
| resume_id                  | INTEGER FK | References `resume_details.id`                  |
| jd_id                      | INTEGER FK | References `job_description_details.id`         |
| analysis_json              | TEXT       | Raw JSON output from LLM                        |
| match_score                | REAL       | Overall match score                             |
| summary                    | TEXT       | Human-readable summary                          |
| issues                     | TEXT       | JSON/CSV of issues from LLM                    |
| core_skills_score          | REAL       | Dimension: core skills score                    |
| core_skills_note           | TEXT       | Dimension: core skills note                     |
| domain_experience_score    | REAL       | Dimension: domain experience score              |
| domain_experience_note     | TEXT       | Dimension: domain experience note               |
| seniority_score            | REAL       | Dimension: seniority score                      |
| seniority_note             | TEXT       | Dimension: seniority note                       |
| communication_score        | REAL       | Dimension: communication score                  |
| communication_note         | TEXT       | Dimension: communication note                   |
| culture_fit_score          | REAL       | Dimension: culture fit score                    |
| culture_fit_note           | TEXT       | Dimension: culture fit note                     |
| stability_score            | REAL       | Dimension: tenure / stability score             |
| stability_note             | TEXT       | Dimension: tenure / stability note              |
| red_flags_score            | REAL       | Dimension: red flags score                      |
| red_flags_note             | TEXT       | Dimension: red flags note                       |
| overall_recommendation_score | REAL     | Dimension: overall recommendation score         |
| overall_recommendation_note  | TEXT     | Dimension: overall recommendation note          |
| processed_at               | DATETIME   | When the analysis was completed                 |
| processed_by               | TEXT       | User / system identifier                        |

**Sample row:**
```sql
INSERT INTO resume_analysis_details
(id, resume_id, jd_id, analysis_json, match_score, summary, issues,
 core_skills_score, core_skills_note,
 domain_experience_score, domain_experience_note,
 seniority_score, seniority_note,
 communication_score, communication_note,
 culture_fit_score, culture_fit_note,
 stability_score, stability_note,
 red_flags_score, red_flags_note,
 overall_recommendation_score, overall_recommendation_note,
 processed_at, processed_by)
VALUES
(1, 1, 1,
 '{"match_score":0.89,"summary":"Strong backend fit"}',
 0.89,
 'Strong backend engineer with solid Python/FastAPI experience.',
 '["Missing AWS certification"]',
 0.9, 'Excellent Python and microservices experience',
 0.85, 'Relevant fintech and SaaS domain exposure',
 0.8, 'Mid-senior level, can work independently',
 0.9, 'Clear communication based on profile',
 0.8, 'Good culture fit indicators',
 0.75, 'Reasonable job stability with 2 prior roles',
 0.2, 'Minor concern about lack of AWS certification',
 0.88, 'Recommend progressing to technical interview',
 '2026-02-11T09:10:00', 'system');
```

---

### 3.5 `resume_feedback`

| Column        | Type        | Notes                                      |
|---------------|------------|--------------------------------------------|
| id            | INTEGER PK | Feedback ID                                |
| resume_id     | INTEGER FK | References `resume_details.id`             |
| jd_id         | INTEGER FK | References `job_description_details.id`    |
| label         | TEXT       | `good_fit` / `bad_fit` / `maybe`           |
| comment       | TEXT       | Free-text reviewer comment                 |
| created_by    | TEXT       | Username                                   |
| created_at    | DATETIME   | When feedback was created                  |

**Sample rows:**
```sql
INSERT INTO resume_feedback
(id, resume_id, jd_id, label, comment, created_by, created_at)
VALUES
(1, 1, 1, 'good_fit', 'Strong match to backend role, move to next round.', 'admin', '2026-02-11T10:00:00');
```

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 4. Authentication

Most endpoints are protected and require a **Bearer token**.

### 4.1 Login
- **Method**: `POST`
- **URL**: `/api/auth/login`
- **Request (JSON body)**
```json
{
  "user_name": "admin",
  "password": "root"
}
```

- **Successful Response (200)**
```json
{
  "success": true,
  "message": "Login successful",
  "token": "<your-jwt-token>"
}
```

Use the token in subsequent calls:
```http
Authorization: Bearer <your-jwt-token>
```

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 5. REST API Reference (Inputs & Outputs)

Base URL for all endpoints below: `http://127.0.0.1:8000/api`

### 5.1 Chat

**Endpoint**: `POST /chat`

**Auth**: Bearer token required

**Request (JSON)**
```json
{
  "message": "Explain event-driven microservices in simple terms."
}
```

**Response (200 JSON)**
```json
{
  "response": "Event-driven microservices are ..."
}
```

---

### 5.2 Job Description (JD) Endpoints

#### 5.2.1 `POST /jd/builder` – Review JD text & build improved JD

- **Headers**:
  - `Authorization: Bearer <token>`
  - `Content-Type: text/plain; charset=utf-8`
- **Body**: Raw JD text, e.g.

```text
We are looking for a Senior Backend Engineer with 5+ years of experience in Python...
```

**Sample Response (200, JSON)**
```json
{
  "message": {
    "jd_strength_score": 82,
    "checkpoints": {
      "role_clarity": "PASS",
      "requirements_specificity": "WEAK",
      "benefits_clarity": "MISSING"
    },
    "critical_gaps_technical": [
      "Missing explicit mention of API design experience"
    ],
    "critical_gaps_administrative": [
      "No mention of working hours or location"
    ],
    "dx_suggestions": [
      "Clarify on-call expectations",
      "Add salary range if possible"
    ],
    "summary": "Overall a strong JD with a few missing details.",
    "conclusion": "Ready to publish after adding admin details.",
    "improved_jd": "<full improved JD text>"
  }
}
```

---

#### 5.2.2 `POST /jd/upload` – Upload JD file

- **Method**: `POST`
- **URL**: `/api/jd/upload`
- **Auth**: Required
- **Content-Type**: `multipart/form-data`
- **Fields**:
  - `file`: JD file (`.txt`, `.pdf`, `.doc`, `.docx`)

**Sample Response (201)**
```json
{
  "jd_id": 1,
  "file_name": "backend_jd.pdf",
  "file_saved_location": "uploaded_jds/backend_jd.pdf"
}
```

---

#### 5.2.3 `POST /jd/{jd_id}/analyze` – Analyze stored JD

**Request**
- **Method**: `POST`
- **URL**: `/api/jd/1/analyze`

**Sample Response (200)**
```json
{
  "jd_id": 1,
  "title": "Senior Backend Engineer",
  "parsed_summary": "Backend role in fintech team ...",
  "last_reviewed_at": "2026-02-10T12:34:56.000000",
  "last_reviewed_by": "admin"
}
```

---

#### 5.2.4 `GET /jd/{jd_id}` – Get JD metadata

**Sample Response (200)**
```json
{
  "jd_id": 1,
  "file_name": "backend_jd.pdf",
  "file_location": "uploaded_jds/backend_jd.pdf",
  "uploaded_by": "admin",
  "title": "Senior Backend Engineer",
  "parsed_summary": "Backend role in fintech team",
  "status": "active",
  "is_active": true,
  "created_date": "2026-02-10T10:00:00",
  "updated_at": "2026-02-10T10:00:00",
  "last_reviewed_at": "2026-02-10T12:34:56",
  "last_reviewed_by": "admin",
  "resumes_uploaded_count": 5,
  "processed_resumes_count": 3,
  "download": "/api/jd/1/download"
}
```

---

### 5.3 Resume Upload & Listing

#### 5.3.1 `POST /resumes/upload` – Upload resumes for a JD

- **Method**: `POST`
- **URL**: `/api/resumes/upload?jd_id=1`
- **Auth**: Required
- **Content-Type**: `multipart/form-data`
- **Fields**:
  - `file`: 1–10 resume files

**Sample Response (201)**
```json
[
  {
    "resume_id": 1,
    "jd_id": 1,
    "file_name": "Rahul_Kodati_Resume.pdf",
    "file_saved_location": "uploaded_resumes/1/Rahul_Kodati_Resume.pdf"
  }
]
```

---

#### 5.3.2 `GET /resumes?jd_id={id}` – List resumes for a JD

**Sample Request**
```http
GET /api/resumes?jd_id=1
Authorization: Bearer <token>
```

**Sample Response (200)**
```json
{
  "items": [
    {
      "resume_id": 1,
      "jd_id": 1,
      "file_name": "Rahul_Kodati_Resume.pdf",
      "file_location": "uploaded_resumes/1/Rahul_Kodati_Resume.pdf",
      "candidate_name": "Rahul Kodati",
      "candidate_email": "rahul@example.com",
      "candidate_phone": "+1-555-123-4567",
      "status": "processed",
      "business_status": "interview_scheduled",
      "match_score": 0.89,
      "created_at": "2026-02-11T09:00:00",
      "updated_at": "2026-02-11T09:15:00"
    }
  ]
}
```

---

### 5.4 Resume Analysis

#### 5.4.1 `POST /resumes/process-once` – Process pending resumes

**Request**
```http
POST /api/resumes/process-once
Authorization: Bearer <token>
```

**Sample Response (200)**
```json
{
  "processed_count": 3
}
```

---

#### 5.4.2 `GET /jd/{jd_id}/analysis` – List per-resume analysis summaries

**Sample Response (200)**
```json
{
  "items": [
    {
      "resume_id": 1,
      "jd_id": 1,
      "file_name": "Rahul_Kodati_Resume.pdf",
      "match_score": 0.89,
      "status": "processed",
      "failure_reason": null
    }
  ]
}
```

---

#### 5.4.3 `GET /resumes/{resume_id}/analysis` – Detailed analysis

**Sample Response (200)**
```json
{
  "resume_id": 1,
  "jd_id": 1,
  "file_name": "Rahul_Kodati_Resume.pdf",
  "candidate_name": "Rahul Kodati",
  "candidate_email": "rahul@example.com",
  "candidate_phone": "+1-555-123-4567",
  "match_score": 0.89,
  "summary": "Strong backend engineer with solid Python/FastAPI experience.",
  "issues": [
    "Missing AWS certification"
  ],
  "issues_raw": "[\"Missing AWS certification\"]",
  "dimensions": {
    "core_skills": {
      "score": 0.9,
      "note": "Excellent Python and microservices experience"
    },
    "domain_experience": {
      "score": 0.85,
      "note": "Relevant fintech and SaaS domain exposure"
    },
    "seniority": {
      "score": 0.8,
      "note": "Mid-senior level"
    },
    "communication": {
      "score": 0.9,
      "note": "Clear communicator"
    },
    "culture_fit": {
      "score": 0.8,
      "note": "Good culture fit"
    },
    "stability": {
      "score": 0.75,
      "note": "Reasonable job stability"
    },
    "red_flags": {
      "score": 0.2,
      "note": "Minor concern about lack of AWS certification"
    },
    "overall_recommendation": {
      "score": 0.88,
      "note": "Recommend progressing to technical interview"
    }
  },
  "analysis_json": {
    "match_score": 0.89,
    "summary": "Strong backend fit",
    "issues": ["Missing AWS certification"],
    "candidate_name": "Rahul Kodati",
    "candidate_email": "rahul@example.com",
    "candidate_phone": "+1-555-123-4567"
  },
  "status": "processed",
  "failure_reason": null,
  "processed_at": "2026-02-11T09:10:00",
  "processed_by": "system"
}
```

If analysis is not yet available, the API will return basic resume info with `status` such as `pending` and `match_score` = `null`.

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 6. Feedback Endpoints

### 6.1 `POST /resumes/{resume_id}/feedback?jd_id={jd_id}` – Create feedback

**Request (example)**
```http
POST /api/resumes/1/feedback?jd_id=1
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "label": "good_fit",
  "comment": "Strong backend experience and good culture fit."
}
```

**Sample Response (201)**
```json
{
  "id": 1,
  "resume_id": 1,
  "jd_id": 1,
  "label": "good_fit",
  "comment": "Strong backend experience and good culture fit.",
  "created_by": "admin",
  "created_at": "2026-02-11T10:00:00"
}
```

---

### 6.2 `GET /resumes/{resume_id}/feedback`

**Sample Response**
```json
{
  "items": [
    {
      "id": 1,
      "resume_id": 1,
      "jd_id": 1,
      "label": "good_fit",
      "comment": "Strong backend experience and good culture fit.",
      "created_by": "admin",
      "created_at": "2026-02-11T10:00:00"
    }
  ]
}
```

---

### 6.3 `GET /jd/{jd_id}/feedback`

**Sample Response**
```json
{
  "items": [
    {
      "id": 1,
      "resume_id": 1,
      "jd_id": 1,
      "label": "good_fit",
      "comment": "Strong backend experience and good culture fit.",
      "created_by": "admin",
      "created_at": "2026-02-11T10:00:00"
    }
  ]
}
```

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 7. Resume Business Status & Deletion

### 7.1 `PATCH /resumes/{resume_id}/status`

Update the **business_status** of a resume (human pipeline stage).

**Request**
```http
PATCH /api/resumes/1/status
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "business_status": "interview_scheduled"
}
```

**Sample Response (200)**
```json
{
  "resume_id": 1,
  "business_status": "interview_scheduled"
}
```

---

### 7.2 `DELETE /resumes/{resume_id}`

Deletes the resume, its analysis, its feedback, and attempts to remove the file from disk.

**Request**
```http
DELETE /api/resumes/1
Authorization: Bearer <token>
```

**Sample Response (200)**
```json
{
  "resume_id": 1,
  "deleted": true
}
```

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 8. Docker Usage (Optional)

### 8.1 Build Image
```bash
docker build -t hiresence-backend .
```

### 8.2 Run with SQLite
```bash
docker run --rm -it \
  --env-file .env \
  -p 8000:8000 \
  hiresence-backend
```

To persist DB and uploads:
```bash
docker run --rm -it \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/dev.db:/app/dev.db" \
  -v "/path/to/jds:/external_uploads/jds" \
  -v "/path/to/resumes:/external_uploads/resumes" \
  hiresence-backend
```

### 8.3 Run with Postgres
```bash
docker run --rm -it \
  -e DB_TYPE=postgres \
  -e POSTGRES_HOST=db-host \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=hiresence \
  -e POSTGRES_USER=hiresence_user \
  -e POSTGRES_PASSWORD=change_me \
  -p 8000:8000 \
  hiresence-backend
```

</div>

---

<div style="background:#020617; color:#e5e7eb; padding:18px 20px; border-radius:12px; border:1px solid #1e293b;">

## 9. Troubleshooting

1. **ModuleNotFoundError (FastAPI or others)**
   - Ensure venv is active and `pip install -r requirements.txt` ran successfully.

2. **Database table not found errors**
   - Confirm `sql/init.sql` exists and app startup logs show successful execution.

3. **File upload errors (415 / 422)**
   - Use `multipart/form-data` with `file` field and `jd_id` query parameter where required.

4. **401/403 on protected endpoints**
   - Call `POST /api/auth/login` first and include `Authorization: Bearer <token>`.

5. **LLM-related 500s (invalid JSON)**
   - Inspect logs and raw LLM output. The prompts try to enforce strict JSON; retry usually helps.

</div>