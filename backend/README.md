# AlakhService Backend

A robust, production-ready REST API for the AlakhService platform — a service booking application built with **FastAPI**, **SQLAlchemy (async)**, **PostgreSQL**, **Redis**, and **Celery**.

---

## Overview

AlakhService Backend provides:
- JWT-based authentication (access + refresh tokens)
- Service catalogue management
- Booking lifecycle management
- Payment processing integration (Razorpay)
- Push notifications (FCM)
- Background task processing with Celery

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.111 |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 15 |
| Cache / Broker | Redis 7 |
| Task Queue | Celery 5 |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| Validation | Pydantic v2 |
| Migrations | Alembic |

---

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/AlakhService.git
cd AlakhService/backend

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
# Edit .env and fill in your actual values (SECRET_KEY, DB credentials, SMTP, etc.)
```

---

## Running Locally

```bash
# Start the FastAPI development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

---

## Running with Docker

```bash
# Build and start all services (API, PostgreSQL, Redis, Celery worker & beat)
docker-compose up --build

# Run in detached mode
docker-compose up -d --build
```

---

## Running Tests

```bash
pytest -v
```

---

## API Documentation

| Interface | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # Pydantic settings
│   ├── database.py           # Async SQLAlchemy engine & session
│   ├── dependencies.py       # Global FastAPI dependencies
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py     # Aggregate v1 router
│   │   │   ├── dependencies.py
│   │   │   └── endpoints/    # auth, users, services, bookings, payments, notifications
│   │   └── v2/               # Placeholder for future v2
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic layer
│   ├── core/                 # Security, exceptions, middleware, events
│   ├── utils/                # Helpers, validators, email utilities
│   └── tasks/                # Celery workers
├── migrations/               # Alembic migration scripts
├── tests/                    # pytest test suite
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Migration Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "describe_your_change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# View current revision
alembic current
```
