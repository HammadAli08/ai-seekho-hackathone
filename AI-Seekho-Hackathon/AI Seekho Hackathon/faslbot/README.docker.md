# FaslBot Production Deployment

This document contains instructions for building, exporting, and running the FaslBot application securely inside isolated Docker containers.

## Prerequisites

- Docker and Docker Compose installed.

## Setup

1. Copy `.env.example` to `.env` in the root folder and fill in the required API keys.
```bash
cp .env.example .env
```

2. Make sure you place your `serviceAccountKey.json` inside the `backend/` directory. This file is mounted directly into the backend container to ensure security.

## Standard Deployment (Local or Server)

To simply run the application on your own machine or cloud server:

```bash
docker compose up -d --build
```

The application will be available at:
- **Frontend**: http://localhost/
- **Backend API**: http://localhost:8000/

## Exporting for Distribution (WhatsApp, Drive)

If you need to package the app and share it as a file with another developer/user, run the export script. This builds the images using the portable `linux/amd64` architecture and compresses them heavily to save space.

```bash
chmod +x scripts/export_project.sh
./scripts/export_project.sh
```

**Alternative: Docker Hub (Recommended for smaller file sizes)**
If the `.tar.gz` is too large for WhatsApp, push the images to Docker Hub:
```bash
docker compose build
docker tag faslbot-backend:latest yourusername/faslbot-backend:latest
docker tag faslbot-frontend:latest yourusername/faslbot-frontend:latest
docker push yourusername/faslbot-backend:latest
docker push yourusername/faslbot-frontend:latest
```

## Importing and Running (Target Machine)

If you receive the `faslbot_images.tar.gz` file via WhatsApp or another platform, follow these exact steps to run it:

1. Extract/Place the `.tar.gz` file in your root folder.
2. Run the import script:
```bash
chmod +x scripts/import_project.sh
./scripts/import_project.sh
```

Or run manually:
```bash
docker load -i faslbot_images.tar.gz
docker compose up -d
```

## Troubleshooting

- **Database Errors / Missing Data**: Ensure you have placed the valid `serviceAccountKey.json` in the `backend/` folder.
- **Frontend Can't Connect to Backend**: The web frontend routes through Nginx `/api/` -> `http://backend:8000/api/`. If API calls fail, check the browser console and the Nginx logs: `docker compose logs frontend`.
- **AI Libraries Fail to Build**: The backend Dockerfile is configured with `build-essential` and gcc to correctly compile heavy ML dependencies like pandas or Torch. Wait for the build to finish.
