# Telemetry Gateway: End-to-End Production & CI/CD Runbook

This runbook documents the complete lifecycle of containerizing, testing, provisioning, securing, and continuously deploying the high-throughput Python FastAPI Telemetry Gateway to an AWS EC2 instance backed by PostgreSQL, Nginx, Let's Encrypt SSL, DuckDNS, and GitHub Actions.

---

## 1. System Architecture Overview

```
                      INTERNET / CLIENTS
                              │
                    HTTPS (Port 443 / TLS)
                              ▼
            ┌────────────────────────────────────┐
            │       AWS EC2 (Ubuntu 24.04)       │
            │                                    │
            │   Host-Level Nginx Reverse Proxy   │
            │  (SSL Termination by Certbot/EFF)  │
            └─────────────────┬──────────────────┘
                              │
                    HTTP (127.0.0.1:8000)
                              ▼
            ┌────────────────────────────────────┐
            │          Docker Engine             │
            │                                    │
            │   ┌────────────────────────────┐   │
            │   │ Container: telemetry_api   │   │
            │   │ - FastAPI Gateway Engine   │   │
            │   │ - Alembic Migrations       │   │
            │   └─────────────┬──────────────┘   │
            │                 │                  │
            │      Internal Docker Network       │
            │                 │                  │
            │   ┌─────────────▼──────────────┐   │
            │   │ Container: db (Postgres16) │   │
            │   │ - Named Volume Persistence │   │
            │   │ - Internal Port: 5432      │   │
            │   └────────────────────────────┘   │
            └────────────────────────────────────┘
```

---

## 2. Containerization Specification

### 2.1 Backend Dockerfile (`Dockerfile`)

```dockerfile
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr and writing bytecode files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install native dependencies required for C-extensions, networking, and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for rapid, deterministic dependency resolution
RUN pip install --no-cache-dir uv

# Leverage Docker layer caching for dependency manifests
COPY Telemetry-API/pyproject.toml ./
COPY Telemetry-API/uv.lock ./

# Install application dependencies directly into system Python
RUN uv pip install --system -r pyproject.toml

# Copy project source code and static web dashboard
COPY Telemetry-API/ /app/Telemetry-API
COPY static/ /app/static/

WORKDIR /app/Telemetry-API

EXPOSE 8000
```

### 2.2 Production Docker Compose (`docker-compose.yml`)

The production Compose configuration:
1. Keeps PostgreSQL completely internal to the Docker bridge network.
2. Binds the FastAPI service strictly to the local loopback (`127.0.0.1:8000`), protecting it from direct public ingress.
3. Automatically executes database schema migrations before launching Uvicorn.

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: telemetry_postgres
    restart: always
    environment:
      POSTGRES_USER: fapi
      POSTGRES_PASSWORD: reemas_493
      POSTGRES_DB: telemetry
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fapi -d telemetry"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: 
      context: .
      dockerfile: Dockerfile
    container_name: telemetry_api
    restart: always
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://fapi:reemas_493@db:5432/telemetry
      DATABASE_URL_ALEMBIC: postgresql+psycopg2://fapi:reemas_493@db:5432/telemetry
      ENVIRONMENT: production
    volumes:
      - ./static:/app/static
    command: >
      sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"

volumes:
  postgres_data:
```

---

## 3. Automated CI/CD Pipeline (`.github/workflows/test-pipeline.yml`)

The GitHub Actions workflow implements continuous testing and deployment:
* **CI Phase:** Runs on all branches and PRs. Boots a transient PostgreSQL service container, runs Alembic migrations, starts Uvicorn, and executes the Playwright E2E browser test suite.
* **CD Phase:** Runs strictly when commits land on `main` and all CI tests pass. Connects to EC2 over SSH to pull changes, rebuild containers, and prune stale images.

```yaml
name: CI/CD Production Pipeline

on:
  push:
    branches: [ main, master, featureBranch, 'feature/**' ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    name: Run Migrations & Python Playwright E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15

    env:
      POSTGRES_USER: fapi
      POSTGRES_PASSWORD: reemas_493
      POSTGRES_DB: telemetry_test
      DATABASE_URL: postgresql+asyncpg://fapi:reemas_493@127.0.0.1:5432/telemetry_test
      DATABASE_URL_ALEMBIC: postgresql+psycopg2://fapi:reemas_493@127.0.0.1:5432/telemetry_test
      ENVIRONMENT: test

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: fapi
          POSTGRES_PASSWORD: reemas_493
          POSTGRES_DB: telemetry_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U fapi -d telemetry_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          pip install --upgrade pip uv
          uv pip install --system -r Telemetry-API/pyproject.toml
          uv pip install --system pytest pytest-playwright

      - name: Install Playwright Chromium Browser
        run: |
          playwright install --with-deps chromium

      - name: Apply Alembic Migrations
        working-directory: ./Telemetry-API
        run: |
          alembic -c alembic.ini upgrade head

      - name: Start FastAPI Background Server
        working-directory: ./Telemetry-API
        run: |
          nohup uvicorn main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
          timeout 30 bash -c 'until curl -s http://127.0.0.1:8000/health | grep -q "ok"; do sleep 1; done'

      - name: Run Playwright E2E Tests
        run: |
          pytest tests/test_e2e_gateway.py -v

      - name: Output Server Logs on Failure
        if: failure()
        run: |
          echo "=== Uvicorn Server Logs ==="
          cat Telemetry-API/uvicorn.log || true

  deploy:
    name: Deploy to AWS EC2
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - name: Deploy Application via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/Telemetry
            git pull origin main
            docker compose up --build -d --remove-orphans
            docker system prune -f
```

---

## 4. End-to-End Test Suite (`tests/test_e2e_gateway.py`)

```python
import time
from playwright.sync_api import Page, expect

def test_telemetry_ui_full_flow(page: Page):
    # Verify local server rendering
    page.goto("http://127.0.0.1:8000")

    # 1. Verify Page Title Header
    expect(page.locator("h1")).to_contain_text("Telemetry Gateway Console")

    # 2. Register New Client via Dashboard
    unique_client_name = f"e2e_client_{int(time.time())}"
    page.locator("#client-name-input").fill(unique_client_name)
    page.locator("#register-client-btn").click()

    # 3. Assert API Key is auto-populated in the Active Header input
    api_key_input = page.locator("#api-key-input")
    expect(api_key_input).not_to_have_value("", timeout=5000)

    # 4. Dispatch a Single Event
    page.locator("#event-user-id").fill("e2e_tester_4")
    page.locator("#event-type").fill("playwright_login")
    page.locator("#send-event-btn").click()
    expect(page.locator("#ingest-status-msg")).to_contain_text("202 Accepted", timeout=5000)

    # 5. Dispatch a Batch Payload
    page.locator("#send-batch-btn").click()
    expect(page.locator("#ingest-status-msg")).to_contain_text("Batch ingested: 3 events", timeout=5000)

    # 6. Allow background workers to commit, then refresh tables
    page.wait_for_timeout(1000)
    page.locator("#refresh-events-btn").click()

    # 7. Assert Table Render
    expect(page.locator("#events-table-body")).to_contain_text("playwright_login", timeout=5000)

    # 8. Test Analytics Aggregation
    page.locator("#refresh-analytics-btn").click()
    expect(page.locator("#metric-total-events")).not_to_have_text("0", timeout=5000)
```

---

## 5. Live Infrastructure Setup (AWS EC2 & Linux Host)

### 5.1 AWS Instance Configuration
* **Instance Type:** `t2.micro` (1 vCPU, 1 GB RAM, Free Tier eligible).
* **Storage:** 20 GB gp3 root volume.
* **Security Group Inbound Rules:**
  * Port 22 (SSH): Accessible from your IP or administrative CIDR.
  * Port 80 (HTTP): Open to `0.0.0.0/0` (required for ACME challenge & HTTPS upgrade).
  * Port 443 (HTTPS): Open to `0.0.0.0/0`.

### 5.2 Server Initialization Script (Ubuntu Host)

Open PowerShell on Windows and lock down permissions on the .pem file so SSH doesn't complain:

PowerShell
  icacls "C:\Users\samee\.ssh\telemetry-key.pem" /inheritance:r
  icacls "C:\Users\samee\.ssh\telemetry-key.pem" /grant:r "$($env:USERNAME):(R)"
Connect to the EC2 server (Ubuntu AMIs use the username ubuntu):

```PowerShell
ssh -i "C:\Users\samee\.ssh\telemetry-key.pem" ubuntu@<YOUR_EC2_PUBLIC_IP>
```

Verification: Your prompt changes to ubuntu@ip-xxx-xx-xx-xx:~$

Execute on initial server connection to prevent OOM errors and set up Docker:

```bash
# 1. Allocate 2 GB Swap Memory to prevent t2.micro compiler/build crashes
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 2. System updates & tools
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw

# 3. Install Docker Engine & Compose plugin
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```
Clone & Run the Telemetry Stack
Clone your project:

```bash
git clone https://github.com/Shamshuddin-493/Telemetry.git
cd Telemetry
```
Launch the stack:

```bash
docker compose up --build -d

Verify containers:
docker compose ps
```
---

## 6. Domain, SSL, and Nginx Reverse Proxy Setup

### 6.1 DuckDNS Configuration
1. Log in to [DuckDNS](https://www.duckdns.org).
2. Create your sub-domain (e.g., `telemetry-usr`).
3. Set the target IP address to your EC2 public IPv4 address (`3.27.95.95`).

### 6.2 SSL Issuance via Certbot
Run Certbot using the Nginx authenticator plugin:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d telemetry-usr.duckdns.org
```

### 6.3 Host Nginx Configuration (`/etc/nginx/sites-available/default`)

Update `/etc/nginx/sites-available/default` so that incoming HTTPS traffic on port 443 terminates SSL and proxies internally to `http://127.0.0.1:8000`:

```nginx
# 1. Automatic HTTP to HTTPS redirection
server {
    if ($host = telemetry-usr.duckdns.org) {
        return 301 https://$host$request_uri;
    }

    listen 80 default_server;
    listen [::]:80 default_server;
    server_name telemetry-usr.duckdns.org;
    return 404;
}

# 2. Authenticated, TLS-Encrypted Reverse Proxy
server {
    listen [::]:443 ssl ipv6only=on;
    listen 443 ssl;
    server_name telemetry-usr.duckdns.org;

    # SSL Certificates managed by Certbot
    ssl_certificate /etc/letsencrypt/live/telemetry-usr.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/telemetry-usr.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        # Forward real client connection headers to FastAPI
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Validate and reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```
