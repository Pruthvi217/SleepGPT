# SleepGPT — AI-Powered Sleep Apnea Detection System

SleepGPT is an AI-driven clinical decision-support platform that combines
**Retrieval-Augmented Generation (RAG)**, curated sleep-medicine literature,
and validated screening instruments to help assess an individual's risk of
**Obstructive Sleep Apnea (OSA)**. The system grounds its reasoning in a
domain-specific knowledge base (AASM guidelines, STOP-BANG, Berlin
Questionnaire, Epworth Sleepiness Scale, NoSAS score, and peer-reviewed
research from IEEE, Elsevier, Springer, MDPI, and PLOS) and uses a local or
self-hosted LLM (via Ollama) to generate explainable, citation-backed
assessments.

> ⚠️ **Disclaimer:** SleepGPT is a research and educational tool. It is
> **not** a certified medical device and must not be used as a substitute
> for professional diagnosis by a qualified sleep physician or
> polysomnography (PSG).

---

## Table of Contents

- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Knowledge Base](#knowledge-base)
- [API Reference](#api-reference)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

- **Symptom & Risk Assessment** — Interactive intake using validated
  screening tools (STOP-BANG, Berlin Questionnaire, Epworth Sleepiness
  Scale, NoSAS).
- **Retrieval-Augmented Generation (RAG)** — Answers and risk explanations
  are grounded in a vetted, versioned knowledge base rather than relying on
  LLM memory alone, reducing hallucination.
- **Local-First LLM Inference** — Integrates with [Ollama](https://ollama.com)
  for private, on-premise / offline model inference, with LangChain as the
  orchestration layer.
- **Document Ingestion Pipeline** — Supports PDF, DOCX, and unstructured
  clinical/research documents, chunked and embedded into a vector store
  (ChromaDB / FAISS).
- **Explainable Outputs** — Every generated risk summary references the
  underlying clinical guideline or study used to support it.
- **Modular, Production-Ready Backend** — Built on FastAPI with a clean
  separation of routes, services, RAG pipeline, and LLM integration layers.
- **Extensible Frontend** — Framework-agnostic frontend workspace ready for
  React, Vue, or Streamlit-based clients.

---

## System Architecture

```text
┌─────────────┐      ┌──────────────────┐      ┌───────────────────┐
│  Frontend   │─────▶│   FastAPI Backend │─────▶│   RAG Pipeline     │
│ (React/UI)  │◀─────│   (routes/services)│◀─────│ (retriever+prompt)│
└─────────────┘      └──────────────────┘      └───────────┬────────┘
                                                              │
                                   ┌──────────────────────────┼─────────────────────┐
                                   ▼                          ▼                     ▼
                         ┌──────────────────┐      ┌────────────────────┐  ┌─────────────────┐
                         │   Vector Store    │      │   Knowledge Base    │  │  LLM (Ollama)    │
                         │ (ChromaDB/FAISS)  │◀─────│ (AASM, STOP-BANG,   │  │  via LangChain    │
                         └──────────────────┘      │  Berlin, ESS, NoSAS,│  └─────────────────┘
                                                     │  IEEE, Elsevier,    │
                                                     │  Springer, MDPI,    │
                                                     │  PLOS)              │
                                                     └────────────────────┘
```

1. Documents are ingested from `knowledge_base/` and chunked/embedded into
   `vector_db/` using sentence-transformers.
2. User queries and structured assessment inputs are routed through the
   FastAPI backend (`backend/routes/`).
3. The RAG pipeline (`backend/rag/`) retrieves relevant context, and the LLM
   layer (`backend/llm/`) generates a grounded response via Ollama.
4. Results and generated summaries can be exported as reports
   (`reports/`).

---

## Project Structure

```text
SleepGPT/
│
├── backend/                 # FastAPI application
│   ├── app.py                # Application entry point (/health, routers)
│   ├── requirements.txt      # Backend Python dependencies
│   ├── routes/                # API route definitions (FastAPI routers)
│   ├── services/              # Business logic / orchestration layer
│   ├── rag/                   # Retrieval-Augmented Generation pipeline
│   ├── llm/                   # LLM client & prompt management (Ollama)
│   ├── utils/                  # Shared utilities & helpers (storage, patient ID)
│   ├── data/                   # patients.json prototype store (gitignored)
│   └── uploads/                # Runtime file uploads (gitignored)
│
├── frontend-patient/          # PATIENT app — independent React + Vite project
│   ├── src/
│   │   ├── App.jsx              # Routes: / (Welcome), /assessment
│   │   ├── pages/                # Welcome, PatientDashboard
│   │   ├── components/           # Assessment, QuestionCard, Results, PatientLogin, ...
│   │   └── services/api.js       # Only /api/patient and /api/assessment calls
│   ├── package.json              # Its own dependencies, run independently
│   └── vite.config.js            # Dev server on :5173, proxies /api to the backend
│
├── frontend-admin/            # ADMIN app — separate independent React + Vite project
│   ├── src/
│   │   ├── App.jsx              # Routes: /login, / (dashboard)
│   │   ├── pages/                # AdminLogin, AdminDashboard
│   │   ├── components/           # PatientSearch, AdminPatientResults, ...
│   │   └── services/api.js       # Only /api/admin calls
│   ├── package.json              # Its own dependencies, run independently
│   └── vite.config.js            # Dev server on :5174, proxies /api to the backend
│
├── knowledge_base/           # Source documents for the RAG knowledge base
│   ├── AASM/                   # American Academy of Sleep Medicine guidelines
│   ├── STOP_BANG/               # STOP-BANG questionnaire references
│   ├── Berlin/                  # Berlin Questionnaire references
│   ├── ESS/                     # Epworth Sleepiness Scale references
│   ├── NoSAS/                   # NoSAS score references
│   ├── IEEE/                    # IEEE research papers
│   ├── Elsevier/                # Elsevier research papers
│   ├── Springer/                # Springer research papers
│   ├── MDPI/                    # MDPI research papers
│   └── PLOS/                    # PLOS research papers
│
├── vector_db/                # Persisted vector store (ChromaDB/FAISS index)
│
├── reports/                  # Generated patient/assessment reports
│
├── datasets/                  # Structured datasets (e.g., PSG, survey data)
│
├── .gitignore
├── README.md
└── requirements.txt           # Root pointer to backend/requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed locally (for LLM inference)
- pip / virtualenv

### 1. Clone & Set Up the Environment

```bash
git clone <repository-url>
cd SleepGPT
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2. Pull an Ollama Model

```bash
ollama pull llama3
```

### 3. Run the Backend

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Verify the Service

```bash
curl http://localhost:8000/health
# {"status": "running"}
```

### 5. Run the Patient App

In a second terminal:

```bash
cd frontend-patient
npm install
npm run dev
```

Open **http://localhost:5173**. This is a completely independent React
app — its own `package.json`, its own dev server, no admin routes or
admin code anywhere in it. It proxies `/api/*` to the backend (see
`frontend-patient/vite.config.js`).

### 6. Run the Admin App

In a third terminal:

```bash
cd frontend-admin
npm install
npm run dev
```

Open **http://localhost:5174/login**. This is a second, entirely
separate React app with its own `package.json` and dev server, on a
different port. It has no knowledge of the patient app — there is no
link to it anywhere in the patient UI, and no shared login state
(the patient app uses `localStorage` for its Patient ID; the admin app
uses `sessionStorage` for its session, on a different origin/port
entirely). The only thing the two apps have in common is that they both
call the same backend API.

### 7. Try the full flow end-to-end

1. On the patient app (`:5173`), click **New User**, enter a username,
   and note the generated Patient ID (e.g. `SGP-482931`).
2. Click **Start Assessment** and answer the 35-question screening —
   follow-up questions (e.g. snoring loudness/frequency) appear only
   when relevant, controlled entirely by the backend `AssessmentEngine`.
3. After the last question, the patient sees *"submitted for review"* —
   results are hidden until an admin releases them.
4. On the admin app (`:5174/login`), sign in with the default prototype
   credentials: `admin` / `admin123` (override via the
   `SLEEPGPT_ADMIN_USERNAME` / `SLEEPGPT_ADMIN_PASSWORD` environment
   variables — see Configuration below). The patient's completed
   assessment appears in the queue automatically (the admin app polls
   every 8 seconds — no manual refresh needed).
5. Search the Patient ID (or pick it from the patient list), review the
   scores/answers/AI analysis, and click **Show Results to Patient**.
6. Go back to the patient app, log in again with the same Patient ID —
   the results, AI summary, and **Download Report** button are now
   visible.

> The AI/RAG analysis works immediately with a deterministic rule-based
> summary — no Ollama or knowledge-base setup required. Once you add
> documents (see [Knowledge Base](#knowledge-base) below) and Ollama is
> running, it automatically upgrades to true retrieval-augmented
> generation with no code changes.

---

## Configuration

Create a `.env` file in `backend/` (excluded from version control) to
configure runtime settings, e.g.:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
SLEEPGPT_ADMIN_USERNAME=admin
SLEEPGPT_ADMIN_PASSWORD=admin123
```

> ⚠️ The default admin credentials are for local prototyping only.
> Change them via environment variables before sharing this app with
> anyone else, and see the security note in `backend/routes/admin.py`
> about replacing this with real hashed-password + session/JWT auth
> before any non-local deployment.

---

## Knowledge Base

The `knowledge_base/` directory holds source material used to build the
vector index. Each subfolder corresponds to a distinct clinical instrument
or publisher source, allowing for source-level filtering, citation, and
version control of the underlying evidence base. Populate these folders
with PDFs or text documents, then run the ingestion pipeline (see
`backend/rag/`) to (re)build `vector_db/`.

---

## API Reference

| Method | Endpoint                                          | Description                                       |
|--------|----------------------------------------------------|-----------------------------------------------------|
| GET    | `/health`                                          | Health check                                       |
| POST   | `/api/patient/register`                            | Register a new patient, returns a Patient ID       |
| POST   | `/api/patient/login`                                | Log in with a Patient ID, returns status           |
| GET    | `/api/assessment/start?patient_id=`                 | Get the next unanswered question                   |
| POST   | `/api/assessment/answer`                            | Submit an answer, get the next question or completion |
| GET    | `/api/assessment/answers?patient_id=`               | Get all recorded answers for a patient              |
| GET    | `/api/assessment/results?patient_id=`               | Get results (only if admin has released them)       |
| POST   | `/api/admin/login`                                  | Admin login                                         |
| GET    | `/api/admin/patients`                               | List all patients                                   |
| GET    | `/api/admin/patient/{patient_id}`                   | Full patient record                                 |
| POST   | `/api/admin/patient/{patient_id}/release-results`   | Release results to the patient                      |
| POST   | `/api/chat`                                         | General sleep-health chat, grounded in the RAG KB   |
| POST   | `/api/sensors/{patient_id}`                         | *(future)* push a cloud IoT sensor reading — scaffolded, no hardware/cloud integration yet |
| GET    | `/api/sensors/{patient_id}`                         | *(future)* fetch a patient's stored sensor readings   |

> Since the ML integration, every endpoint except `/health`, `/api/ml/health`, `/api/patient/register|login` and `/api/admin/login` requires `Authorization: Bearer <token>` (see below). ML endpoints are listed in the ML section.

Interactive docs are also available at `http://localhost:8000/docs`
(FastAPI's built-in Swagger UI) once the backend is running.

---

## Roadmap

- [ ] Implement STOP-BANG / Berlin / ESS / NoSAS scoring services
- [ ] Build document ingestion & chunking pipeline for `knowledge_base/`
- [ ] Wire up RAG retriever + Ollama LLM chain
- [ ] Add authentication & role-based access control
- [ ] Build frontend assessment UI
- [ ] Add PDF report generation
- [ ] Containerize with Docker Compose (backend + Ollama + vector DB)

---

## Contributing

Contributions are welcome. Please open an issue to discuss significant
changes before submitting a pull request. Follow standard Python style
(PEP 8) and include tests for new functionality where applicable.

---

## License

This project is provided for research and educational purposes. Add your
chosen license (e.g., MIT, Apache 2.0) here before public release.


---

# ML / IoT Integration (SomnNET SpO₂ + Ubidots)

> **Estimated AHI — unvalidated.** This ML-derived estimate is for research/informational use and is not a
> clinical diagnosis. Model normalization requires validation against the original training-data statistics
> and real sensor data.

## 1. Architecture

```text
Existing Patient ID: SGP-XXXXXX   (backend/data/patients.json - unchanged, the only identity store)
      │
      ├── Existing assessments / chatbot+RAG / sensor_data (JSON store)
      └── ML analyses  (SQLite table ml_analyses, patient_id = the same SGP-XXXXXX)
             ├── Manual CSV ─┐
             └── Ubidots ────┤→ ml.pipeline.run_pipeline  (ONE shared pipeline)
                              ↓  clean → resample 8 Hz → 88-sample windows → normalise → SomnNET → merge events → AHI
                         ml_analyses row
                    ┌─────────┴─────────┐
              Patient dashboard    Admin dashboard (+ ML dashboard :5175, chatbot context)
```

Three independent Vite apps share one backend: patient `:5173`, admin `:5174`, **ML dashboard `:5175`**.
The ML dashboard picks patients from the existing store and never creates IDs.

## 2. Folder structure (new/changed)

```text
backend/
  ml/                     config.py  somnnet.py  preprocessing.py  events.py  pipeline.py
                          ubidots.py  db.py  service.py  _h5_fallback.py
    weights/              best_weights_spo2_32layer_binary.hdf5   (your supplied weights)
    reference/            binary_ops.py, binary_layers.py         (your originals, NOT imported at runtime)
  routes/ml.py            /api/ml/*
  utils/tokens.py auth.py session tokens + FastAPI dependencies
  tests/                  test_ml_core.py  test_api.py  data/synthetic_spo2.csv
  .env.example  requirements-dev.txt
frontend-ml/              NEW ML dashboard (:5175)
frontend-patient/src/components/SleepAnalysisPanel.jsx   NEW
frontend-admin/src/components/MlAnalysisSection.jsx      NEW
```
Modified: `app.py`, `routes/{patient,admin,assessment,sensors,chat}.py`, both `services/api.js`, `PatientDashboard.jsx`,
`AdminDashboard.jsx`, `AdminPatientResults.jsx`, `requirements.txt`, `.gitignore`.

## 3. Installation (Windows, PowerShell)

```powershell
cd SleepGPT
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements-dev.txt
copy backend\.env.example backend\.env     # then edit backend\.env
```
No TensorFlow/GPU is needed: the model is a pure NumPy CPU implementation of the supplied architecture.

## 4. Environment variables (`backend/.env`, see `.env.example`)

| Variable | Purpose |
|---|---|
| `SLEEPGPT_ADMIN_USERNAME` / `SLEEPGPT_ADMIN_PASSWORD` | Admin login (**change the default `admin123`**) |
| `SLEEPGPT_SECRET_KEY`, `SLEEPGPT_TOKEN_TTL_HOURS` | Session-token signing key (random file used if empty) / lifetime |
| `SLEEPGPT_CORS_ORIGINS` | Allowed origins (defaults: the three dev servers) |
| `UBIDOTS_TOKEN` | Ubidots API token (server-side only) |
| `UBIDOTS_BASE_URL`, `UBIDOTS_DEVICE_LABEL=esp32_health_monitor` | Account endpoint / default device |
| `UBIDOTS_SPO2_VARIABLE`, `..._HEART_RATE_..`, `..._ECG_..`, `..._RESPIRATORY_PRESSURE_..`, `..._TEMPERATURE_VARIABLE` | Variable labels (only SpO₂ feeds the model) |
| `SOMNNET_NORMALIZATION_MODE` (`window`/`global`), `SOMNNET_TRAIN_MEAN`, `SOMNNET_TRAIN_STD` | Normalization (below) |
| `SOMNNET_APNEA_CLASS_INDEX`(1), `SOMNNET_APNEA_THRESHOLD`(0.5), `SOMNNET_MIN_EVENT_WINDOWS`(1) | Event detection |
| `SPO2_VALID_MIN/MAX`, `ML_MIN_DURATION_MINUTES`, `ML_RELIABLE_DURATION_MINUTES`, `SLEEPGPT_ML_DB` | Validation / DB path |

## 5. Database setup
Nothing to run. `backend/data/ml.sqlite3` and table `ml_analyses` are created on first use. `patient_id` is constrained
(`CHECK GLOB 'SGP-[0-9]x6'`) to the exact existing format and the service refuses IDs that are not in the JSON patient store
(SQLite cannot hold a real foreign key into a JSON file).
Each row keeps: patient_id, source (`manual`/`ubidots`), session_id, device_label, estimated_ahi, detected_events,
sleep_duration_hours, average/minimum/maximum_spo2, analysis_start/end, model_name, model_version, normalization_mode,
validation_status (`unvalidated`), config_json (mean/std, threshold, stride, class index, source sampling interval),
warnings, events, status, error_message, created_at - so how any AHI was produced is reproducible.

## 6-8. Running (three terminals)

```powershell
# 1 backend
cd backend
..\venv\Scripts\activate
uvicorn app:app --reload --host 0.0.0.0 --port 8000
# 2 patient app            3 admin app               4 ML dashboard
cd frontend-patient        cd frontend-admin         cd frontend-ml
npm install; npm run dev   npm install; npm run dev  npm install; npm run dev
```
Patient `http://localhost:5173` · Admin `http://localhost:5174/login` · ML dashboard `http://localhost:5175/login` (same admin account).

End-to-end: register a patient (note `SGP-XXXXXX`) → ML dashboard → select that ID → Manual CSV
`backend/tests/data/synthetic_spo2.csv` → Preview → Run & save → open patient app (login with the ID) and admin app: same result.

## 9. Ubidots
Set `UBIDOTS_TOKEN` in `backend/.env`, restart the backend. The client calls
`GET {base}/api/v1.6/devices/{device}/{variable}/values/?start&end&page_size=1000` with `X-Auth-Token` and follows `next`.
In the ML dashboard choose *Ubidots*, a patient, a time range (≤48 h) → Preview → Run & save.
**Not verified against a live Ubidots account** (none was available); it is covered by tests with a fake HTTP layer only.
The device is shared: the operator chooses which patient a session belongs to; use *Device label* for per-patient devices.

## 10. Manual CSV format
```csv
timestamp,spo2
2026-10-01T22:00:00,96
2026-10-01T22:00:01,95
```
ISO-8601 (naive = UTC) or epoch seconds/ms. Rejected with specific messages: missing columns, unparseable times, non-numeric/missing
SpO₂, values outside 50-100 %, >50 % invalid rows, <5 min recording, median sampling interval >5 s, no 11 s window without gaps (>10 s).

## 11-13. Model, CPU inference, AHI
* From `Binary_spo2.ipynb`: input **88 samples at 8 Hz = 11 s** (notebook: 1408 samples @128 Hz, decimated by 16); architecture
  BN → 3×BinaryConv1D(6/25, 50/10, 30/15) with pooling+ReLU → BN → BinaryDense(2) → softmax. Verified against tensor shapes in the HDF5; all
  kernels are exactly ±1. The implementation is NumPy, so `BinaryConv1D` (missing from your `binary_layers.py`) is not needed.
* **Normalization:** the notebook z-scores with the *global training mean/std*, which are not in the supplied files and were not invented.
  Default is therefore `window` (per-window z-score), a fallback that is **not** the original preprocessing. When you obtain the constants set
  `SOMNNET_NORMALIZATION_MODE=global`, `SOMNNET_TRAIN_MEAN`, `SOMNNET_TRAIN_STD` and restart - no code change.
  Sensitivity check on synthetic data showed the output changes a lot with these constants and with sensor noise.
* Resampling arbitrary-rate sensor data to 8 Hz (linear interpolation, gaps masked) is *not* defined by the notebook; it is an
  inference-time necessity and is flagged in each result's warnings when the source rate is low (e.g. 1 Hz).
* Class index 1 is assumed to be "apnea" (LabelEncoder order in the notebook; configurable).
* **AHI = detected events / analysed hours.** Consecutive positive windows are merged into one event. Without sleep staging the denominator is
  *analysed recording time*, not true sleep time, and there is no hypopnea/desaturation-criteria logic: it is a proxy, shown as "Estimated AHI".

## 14. Patient ID flow
`SGP-XXXXXX` (existing) → used verbatim as `ml_analyses.patient_id`, in every `/api/ml/patients/{patient_id}/…` URL, in the patient dashboard
(taken from the logged-in session, never hard-coded), the admin patient view, and the chatbot context.

## 15. API (all need `Authorization: Bearer <token>` unless noted)

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/patient/login`, `/api/admin/login` (return `token`) | public |
| GET | `/api/ml/health` | public (no secrets) |
| GET | `/api/ml/patients/{id}/latest`, `/history`, `/analyses/{analysis_id}` | owner patient or admin |
| GET | `/api/ml/admin/summary` | admin |
| GET | `/api/ml/patients/{id}/sensor-data?start&end&device_label` | admin |
| POST | `/api/ml/patients/{id}/manual/preview`, `/manual` (multipart `file`) | admin |
| POST | `/api/ml/patients/{id}/ubidots/preview`, `/ubidots` (`{start,end,device_label?}`) | admin |
| GET | `/api/admin/patient/{id}` now also returns `ml_latest`, `ml_history` | admin |
| POST | `/api/chat` (`{message, patient_id}`) - injects the saved ML result; says so if none exists | owner/admin |

Authorization: patient tokens work only for their own ID; admin tokens for all. **Inherited limitation:** patient login is still
"Patient ID only" (no password), so a person who knows an ID can log in as that patient. Add a PIN/password before real use.

## 16. Testing
```powershell
cd backend
python -m pytest tests -v          # or: python -m unittest discover -s tests -t .
```
`test_ml_core.py` (31 tests, no web framework): weights/architecture, 88-sample windows, preprocessing/normalization config, inference,
convolution vs. a naive reference, event merging, AHI, CSV validation, Ubidots parsing/pagination/credentials, persistence, patient association,
chat context, tokens. `test_api.py` (10 tests): login, 401/403 authorization, manual upload, dashboards, previews, missing Ubidots credentials.
These show the code is consistent - **not** that the model is clinically accurate.

## 17. Troubleshooting
* `ModuleNotFoundError: routes/ml/utils` → run uvicorn and pytest from inside `backend/`.
* 401 in a dashboard → session expired (or the signing key changed) - log in again.
* 503 "UBIDOTS_TOKEN is not configured" → set it in `backend/.env` and restart.
* 422 on CSV → the `details` list says what is wrong (sampling too sparse, too short, bad rows).
* Model "not loaded" in `/api/ml/health` → check `backend/ml/weights/…hdf5` (or `SOMNNET_WEIGHTS_PATH`).
* Very high or very low AHI → expected until real normalization constants + real ESP32 data are validated.
* PowerShell blocks `activate` → `Set-ExecutionPolicy -Scope Process Bypass`.
