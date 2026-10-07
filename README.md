# DataRefinery — Automated Data Cleaning & Quality Management System

> **Disclaimer:** This is a portfolio/demonstration project, not a government system.
> It uses **synthetic data only**. No real CNICs, phone numbers, family IDs or citizen
> records are used anywhere in this repository, its tests or its screenshots.

## Overview

Organizations that receive records from many sources (manual Excel files, mobile apps,
legacy systems, web portals) end up with inconsistent identifiers, missing values,
duplicates, Urdu/English variations and unstructured addresses.

DataRefinery automates the repetitive cleaning and quality-assurance work while keeping
uncertain decisions under human control. It is designed with potential public-sector
data-quality use cases in mind, such as programmes that consolidate records from
multiple sources.

## Roadmap

Validation engine, duplicate detection, audit trail, data profiling, human review
queue, quality dashboard, exports and quality report, Docker deployment.

**Core principle:** correct only what is certain. Anything uncertain is flagged for
human review with a suggested value; nothing is guessed silently.

## Project Breakdown

The project is being built in five phases.

| Phase | Scope |
| --- | --- | 
| Phase 1 | Foundation, database, upload, synthetic data generator | 
| Phase 2 | Cleaning engine (CNIC, phone, names/text, Urdu/English, addresses) | 
| Phase 3 | Profiling, validation engine, duplicate detection, audit trail | 
| Phase 4 | Human review queue, quality dashboard, exports and reports | 
| Phase 5 | Security review, integration testing, Docker, full documentation | 

**Targeted workflow:**

```text
Messy dataset → Profiling → Cleaning → Validation → Duplicate detection
→ Human review → Final validation → Clean dataset + Quality report
```

***Work Under Progress***

## What works today
**Ingestion Layer**
- Upload CSV/XLSX through a Streamlit UI or the REST API.
- File validation: type, size limit, empty files, readable content, header
  normalization, required columns.
- Every column is read as text, so identifiers keep their leading zeros and
  13-digit CNICs are never converted to numbers.
- Each upload becomes a processing session in PostgreSQL. Every row is stored
  unchanged (JSONB), and the original file is preserved under a generated filename.

**Cleaning services**

| Service | Behaviour |
| --- | --- |
| CNIC | Standardizes known formats to `NNNNN-NNNNNNN-N`; rejects lost-information cases (wrong digit count, letters, scientific notation); flags placeholder-like values; suggests fixes for uncertain layouts |
| Phone | Standardizes Pakistani mobile numbers to `03XXXXXXXXX` (E.164 conversion available); detects landlines, invalid lengths and spreadsheet corruption |
| Names / text | Fixes spacing, invisible characters and all-caps/all-lowercase words; never changes spelling; placeholders such as `N/A` treated as missing |
| Gender | Maps variants (`M`, `female`, `مرد`) to standard labels |
| Districts | Maps Urdu script, abbreviations (`BWP`), historical names (`Lyallpur`) and Arabic-keyboard letter forms to standard names; typos receive a suggestion, never an automatic change |
| Addresses | Extracts district, tehsil and Union Council by matching known names (longest match first); conflicts, multiple mentions and inferred districts are sent for review |

Every cleaner returns a status: `VALID`, `CORRECTED`, `MISSING`, `INVALID`,
`SUSPICIOUS` or `REVIEW_REQUIRED`, plus a reason and, where appropriate, a
suggestion for human review.

**Synthetic data generator**
- Generates realistic households (shared family IDs, addresses and phones).
- Injects known problems at three messiness levels (`clean`, `normal`, `high`).
- Writes an **answer key** of every injected problem, so cleaning and detection
  can be measured against ground truth.

## Architecture

```text
Synthetic data generator (offline)
          │  user uploads the file
          ▼
Streamlit frontend ── HTTP ──► FastAPI backend
                                 ├── API routes (thin)
                                 ├── Services (validation, persistence, cleaning)
                                 └── Data layer (models, DB sessions, schemas)
                                          │
                       ┌──────────────────┴──────────────────┐
                       ▼                                      ▼
                  PostgreSQL                       data/uploads/ (original files)
```

The frontend talks to the backend only through the API. Business logic lives in
services, independent of HTTP.

## Tech stack

Python 3.12 · FastAPI · Pandas · SQLAlchemy 2.0 · PostgreSQL · psycopg 3 ·
Pydantic Settings · Streamlit · Pytest

## Project structure

```text
backend/app/
  api/routes/      HTTP endpoints (health, sessions)
  core/            configuration
  db/              engine and session management
  models/          database tables and status enums
  schemas/         API response shapes
  services/        upload validation, persistence and cleaning services
frontend/          Streamlit UI and API client
reference_data/    configurable location, name-variant and gender mappings
scripts/           table creation and synthetic data generator
tests/             Pytest suite
data/              uploads, outputs and generated files (git-ignored)
```

## Getting started

### Prerequisites
- Python 3.11+
- PostgreSQL 14+

### 1. Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create the databases

Run as a PostgreSQL superuser (for example in pgAdmin's Query Tool):

```sql
CREATE ROLE datacleaner WITH LOGIN PASSWORD 'choose_a_strong_password';
CREATE DATABASE data_cleaning_db OWNER datacleaner;
CREATE DATABASE data_refinery_test_db OWNER datacleaner;
```

### 3. Configure

Copy `.env.example` to `.env` and set your own password in both database URLs.
Never commit `.env`.

### 4. Create the tables

```bash
python -m scripts.init_db
```

### 5. Run

```bash
uvicorn backend.app.main:app --reload     # API at http://localhost:8000/health (docs at /docs)
streamlit run frontend/app.py             # UI at http://localhost:8501
```

## Generating synthetic data

```bash
python -m scripts.generate_messy_dataset --rows 1000 --level normal --seed 42
```

Options: 
- `--rows`, `--level` (`clean` | `normal` | `high`), `--seed`,
- `--format` (`csv` | `xlsx` | `both`), `--output-dir`, `--name`.
- Files are written to `data/synthetic/`, together with an `_answer_key.csv`.

## Running tests

```bash
python -m pytest
```

Tests run against a separate test database, and each database test is rolled back,
so development data is never touched. Every cleaner is also checked against the
generator's answer key.

## Design principles

- **Deterministic corrections only.** Formats are standardized only when the result
  is certain.
- **Curated vs inferred.** Mappings written into reference data are applied
  automatically; similarity-based matches are only suggested.
- **Spelling is never changed.** Name variants are equated only in internal
  comparison keys used for duplicate detection.
- **Original data is preserved.** Original files and rows are stored unchanged.
- **Configurable reference data.** Locations and mappings live in `reference_data/`,
  not in code.

## Security & privacy

- Synthetic data only; disclaimer shown in the UI.
- Secrets kept in `.env` (git-ignored); `.env.example` documents the keys.
- Database user with least privilege.
- Unguessable UUID session IDs; generated storage filenames (no path traversal).
- Generic error messages for database failures; internal fields excluded from API
  responses.
- Cleaning reasons never contain the identifier values themselves.
- Test output configured not to expose connection credentials.

## Known limitations

- No authentication (local demonstration only).
- Uploaded files are read fully into memory (20 MB limit).
- Reference data covers 5 districts; unknown districts are sent for review.
- Database schema is created with `create_all`; migrations (Alembic) are a planned
  improvement.
- Only locations present in the reference data can be extracted. Unknown places give MISSING, never a guess.
- Tehsil names are matched in English only. Urdu tehsil names would need entries in locations.json.
- Union Council labels are recognized in English (UC, Union Council). The Urdu label یونین کونسل is not yet supported.
- A bare Chak 12 without a UC label is not extracted, by design.