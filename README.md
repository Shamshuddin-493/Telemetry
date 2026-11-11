# High-Throughput Telemetry Gateway & Analytics Engine

[![CI/CD Production Pipeline](https://github.com/Shamshuddin-493/Telemetry/actions/workflows/test-pipeline.yml/badge.svg)](https://github.com/Shamshuddin-493/Telemetry/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16--alpine-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Playwright](https://img.shields.io/badge/Playwright-E2E%20Tested-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)

A distributed, asynchronous telemetry ingestion service designed to process high-velocity application telemetry, client events, and audit logs with sub-millisecond response latency, robust API key tenant isolation, and automated schema migrations.

---

## 🎯 The Core Problem & Philosophy

Modern web applications, mobile clients, and distributed microservices generate thousands of runtime signals every minute—ranging from user interaction metrics and operational heartbeats to telemetry error traces. 

Common bottlenecks when building event ingestion systems include:
1. **Synchronous I/O Blocking:** Synchronously writing large JSON event payloads directly to disk or transactional databases stalls client threads and spikes API latency.
2. **Multi-Tenant Ingestion Security:** Ingest endpoints often lack lightweight yet cryptographically sound authentication, making them vulnerable to telemetry poisoning and unmetered writes.
3. **Operational Overhead in Small Footprints:** Microservices need enterprise reliability (automatic migrations, reverse-proxy SSL termination, health monitoring) without requiring complex Kubernetes infrastructure.

### The Solution: Asynchronous Buffered Telemetry Ingestion
This Telemetry Gateway acts as a hardened edge ingestion buffer:
* **Immediate Client Acknowledgment:** The API ingests single and batch payloads, assigns idempotency tokens, and returns `202 Accepted` immediately, offloading persistence to async database tasks.
* **Tenant Isolation:** Enforces header-based authentication (`X-API-KEY`) per registered client application.
* **Production-Grade Delivery:** Packaged within an automated GitHub Actions CI/CD pipeline, running end-to-end browser and API tests with Playwright before executing zero-downtime rolling deploys to an AWS EC2 instance.

---

## 🏗️ Architecture & Data Flow

```
   [ Client Apps / Browsers / IoT ]
                  │
        (HTTPS / TLS 1.3 - Port 443)
                  │
                  ▼
   ┌───────────────────────────────┐
   │ Host Nginx Reverse Proxy      │  <-- SSL termination (Let's Encrypt / Certbot)
   │ (telemetry-usr.duckdns.org)   │  <-- Request rate buffering & payload caps (10MB)
   └──────────────┬────────────────┘
                  │
        (HTTP Loopback 127.0.0.1:8000)
                  │
                  ▼
   ┌───────────────────────────────┐
   │ Docker: telemetry_api         │
   │ (FastAPI + AsyncPG + Uvicorn) │  <-- API Key validation, JSON payload parsing,
   └──────────────┬────────────────┘      and non-blocking async worker dispatch
                  │
      (Internal Bridge Network: 5432)
                  │
                  ▼
   ┌───────────────────────────────┐
   │ Docker: telemetry_postgres    │
   │ (PostgreSQL 16 Alpine)        │  <-- Relational persistence & analytical queries
   └───────────────────────────────┘
```

---

## ✨ Features

- **Asynchronous Ingestion Pipeline:** Built on top of FastAPI and `asyncpg` for non-blocking database communication under heavy write loads.
- **Single & Batch Processing:** First-class support for bulk telemetry ingestion (`/events` single & batch endpoints) to minimize client HTTP roundtrips.
- **Automated Database Migrations:** Integrated with Alembic to automatically inspect and upgrade schema definitions during startup.
- **Interactive Management Dashboard:** Lightweight static dashboard allowing developers to register client apps, inspect incoming live streams, and view aggregated usage counters in real time.
- **Continuous Integration & Automated Testing:** Every push is validated using Python Playwright, ensuring end-to-end health check verification, client registration, and event lifecycle assertions.
- **Automated Deployment:** Git-driven deployments via GitHub Actions SSH runners that pull changes, rebuild containers, and prune stale cache objects on production.

---

## 🚀 API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck endpoint reporting database and engine status | No |
| `POST` | `/clients` | Registers a new client app and provisions an API key | No (Admin/Public) |
| `POST` | `/events` | Dispatches a single telemetry event (`202 Accepted`) | **Yes** (`x-api-key`) |
| `POST` | `/events/batch`| Ingests a collection of telemetry items in one request | **Yes** (`x-api-key`) |
| `GET` | `/events` | Retrieves recently ingested events for monitoring | **Yes** (`x-api-key`) |
| `GET` | `/analytics` | Summarizes aggregated event counts and unique active users| No |

---

## 🛠️ Quickstart (Local Development)

### Prerequisites
- Docker Engine & Docker Compose
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (fast Python package installer)

### 1. Clone the Repository
```bash
git clone https://github.com/Shamshuddin-493/Telemetry.git
cd Telemetry
```

### 2. Configure Environment Variables
Create a `.env` file in `Telemetry-API/.env`:
```ini
POSTGRES_USER=fapi
POSTGRES_PASSWORD=your_secret_password
POSTGRES_DB=telemetry
DATABASE_URL=postgresql+asyncpg://fapi:your_secret_password@db:5432/telemetry
DATABASE_URL_ALEMBIC=postgresql+psycopg2://fapi:your_secret_password@db:5432/telemetry
ENVIRONMENT=production
```

### 3. Run with Docker Compose
```bash
docker compose up --build -d
```

The gateway console will be available locally at `http://127.0.0.1:8000`.

---

## 🧪 Automated Testing

The suite uses **Playwright for Python** to run end-to-end headless integration tests validating the interactive console and API contracts.

```bash
# Install testing dependencies
uv pip install pytest pytest-playwright
playwright install --with-deps chromium

# Run the test suite against a running local instance
pytest tests/test_e2e_gateway.py -v
```

---

## 🌐 Production Deployment

The production deployment runs on an **AWS EC2 `t2.micro`** instance configured with:
* **Host Nginx:** Serving SSL via Let's Encrypt / Certbot on `telemetry-usr.duckdns.org`.
* **Isolated Networking:** Containers only bind to internal loops (`127.0.0.1:8000`), completely shielding the database and internal services from public scans.
* **CI/CD Automation:** Pushes to `main` automatically trigger GitHub Actions to run the full test pipeline, connect via SSH, run `docker compose up --build -d --remove-orphans`, and prune obsolete build layers.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.