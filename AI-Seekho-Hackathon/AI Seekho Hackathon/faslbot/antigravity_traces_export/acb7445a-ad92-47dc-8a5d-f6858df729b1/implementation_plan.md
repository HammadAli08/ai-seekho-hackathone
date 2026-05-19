# Complete Production-Grade Dockerization Plan

The goal is to automatically analyze and containerize the FaslBot project into a robust, easily distributable Docker package, removing all local machine dependencies.

## User Review Required

> [!WARNING]
> **API Configuration for Frontend**
> Currently, the Flutter app's `api_config.dart` points to `https://ai-seekho-hackathone.onrender.com/api/v1`. 
> I will parameterize or replace this so it communicates with the local Docker backend when running via Docker (e.g. `http://localhost:8000/api/v1`) or configure it as an environment variable injected during the web build.
> 
> **Service Account Key**
> Your backend depends on `serviceAccountKey.json`. It is unsafe to bake this credential directly into the Docker image. The `docker-compose.yml` will mount this file at runtime securely.

## Open Questions

> [!IMPORTANT]
> 1. Do you want the Flutter mobile app built strictly as a **Web Application** to be served via Nginx in the Docker setup, or are you primarily focused on Dockerizing the backend alone? (My plan currently includes both for a full-stack container experience).
> 2. Are there any other hidden files (like custom certificates) besides `serviceAccountKey.json` that the backend relies on locally?

## Proposed Changes

---
### 1. Root Orchestration (`faslbot/`)
#### [NEW] `docker-compose.yml`
- Defines the multi-service architecture: `backend` and `frontend`.
- Exposes port `8000` for backend, and `80` (or `3000`) for frontend.
- Defines healthchecks, restart policies (`unless-stopped`), and secure path mounts for credentials.

#### [NEW] `.env.example`
- Centralized environment variables for Docker containers.

---
### 2. Backend Service (`faslbot/backend/`)
#### [NEW] `Dockerfile`
- Base: `python:3.11-slim` (Slim image for production).
- Optimization: Prevents writing `.pyc` and uses optimal layer caching.
- Dependency Install: Uses `requirements.txt` correctly without `.venv`.
- Security: Non-root user `appuser` (if possible, considering Firebase mounts).
- Command: `uvicorn main:app --host 0.0.0.0 --port 8000`.

#### [NEW] `.dockerignore`
- Excludes `.venv`, `__pycache__`, `*.log`, `.env`, local scratch spaces.

---
### 3. Frontend Service (`faslbot/mobile/`)
#### [NEW] `Dockerfile`
- **Multi-stage build**:
  - Stage 1 (`build`): Uses a Flutter Docker image to run `flutter pub get` and `flutter build web`.
  - Stage 2 (`serve`): Uses `nginx:alpine` to serve the static generated files.
- Optimization: Keeps the final frontend image extremely small (only HTML/JS/CSS + Nginx).

#### [NEW] `.dockerignore`
- Excludes `build/`, `.dart_tool/`, `linux/`, `macos/`, `windows/`.

---
### 4. Portability Scripts
#### [NEW] `scripts/export_project.sh`
- A script showing the exact commands for `docker save` to compress the images into a `.tar` file that can be shared over WhatsApp.

#### [NEW] `scripts/import_project.sh`
- A script with instructions for Person B to run `docker load` and `docker compose up`.

## Verification Plan

### Automated Tests
- Build all images: `docker compose build`
- Start services: `docker compose up -d`
- Healthcheck: Curl `http://localhost:8000/` and `http://localhost:80/`
- Verify no local python packages or binaries leak into the build.

### Manual Verification
- Request you to run `docker compose build` and ensure dependencies compile inside the container properly.
