# 🌾 FaslBot (فصل بوٹ)
### Autonomous AI Market Intelligence & Causal Reasoning Engine for Pakistan's Agriculture

FaslBot is a production-grade, autonomous, multi-agent AI system designed to solve Pakistan's **agricultural information asymmetry crisis**. Built for the **AI Seekho Hackathon 2026 (Challenge 1: Content-to-Action)**, it bridges the gap between passive spreadsheets and real-world agricultural actions. 

By autonomously scraping commodity prices, analyzing regional spreads, calculating market impacts, ranking solutions, and dispatching localized Urdu SMS alerts to farmers, FaslBot turns raw data into high-impact, immediate action.

---

## 📖 Table of Contents
1. [🚨 The Problem](#-the-problem)
2. [💡 The Solution: Overall Design](#-the-solution-overall-design)
3. [🏗️ Solution Architecture](#️-solution-architecture)
4. [🧠 Developed AI Agents](#-developed-ai-agents)
   - [A. Autonomous 6-Agent LangGraph Pipeline](#a-autonomous-6-agent-langgraph-pipeline)
   - [B. Interactive 3-Layer Causal Reasoning Engine (Chat)](#b-interactive-3-layer-causal-reasoning-engine-chat)
5. [🔌 Integrated APIs (Real & Mock)](#-integrated-apis-real--mock)
6. [📱 Premium Flutter Client App](#-premium-flutter-client-app)
7. [🚀 Installation & Quick Start](#-installation--quick-start)
   - [A. Docker Compose Setup (Recommended)](#a-docker-compose-setup-recommended)
   - [B. Manual Development Setup](#b-manual-development-setup)
8. [☁️ Render Deployment & DevOps](#️-render-deployment--devops)
9. [📂 Trace Logs (Proof of Agentic Development)](#-trace-logs-proof-of-agentic-development)

---

## 🚨 The Problem

Pakistan's agricultural ecosystem suffers from severe market inefficiencies:
- **Price Arbitrage Exploitation:** Commodity prices vary drastically between cities (e.g., a 40% wheat spread between Karachi and Quetta). Farmers are unaware of these spreads, allowing middlemen to buy low and pocket the profits.
- **Data Accessibility Gap:** Government price metrics (Pakistan Bureau of Statistics) and international datasets (WFP) exist, but they are buried in complex Excel sheets inaccessible to farmers.
- **Logistics & Weather Vulnerabilities:** Price surges and crop failures are heavily correlated with weather anomalies and logistics shocks, but there is no integrated forecasting system to alert stakeholders *before* the market collapses.

---

## 💡 The Solution: Overall Design

FaslBot implements a dual-mode intelligence architecture:

```
                  ┌──────────────────────────────┐
                  │   Data Ingestion Sources     │
                  │   (PBS, WFP, Weather, News)  │
                  └──────────────┬───────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
┌────────────────────────┐               ┌────────────────────────┐
│  Autonomous LangGraph  │               │ 3-Layer Causal Chat    │
│  6-Agent Pipeline      │               │ Reasoning Engine       │
│  (Triggered by Cron)   │               │ (Natural Query, UI)    │
└───────────┬────────────┘               └────────────┬───────────┘
            ▼                                         ▼
┌────────────────────────┐               ┌────────────────────────┐
│   Urdu SMS Broadcast   │               │ Interactive Heatmap,   │
│  (Mandi Arbitrage)     │               │ Action Logs & Causal   │
│   Sent to Farmers      │               │ Simulation on Flutter  │
└────────────────────────┘               └────────────────────────┘
```

1. **Autonomous Ingestion & Alerting (Cron-Triggered):** Runs in the background using a 6-agent LangGraph workflow. It detects price anomalies and automatically blasts targeted Urdu SMS alerts to affected farmers.
2. **Interactive War Room Chat (On-Demand):** Allows commodity managers and policy experts to chat with the system to ask complex causal questions (e.g., *"Why did wheat prices spike in Multan?"*), simulate policy interventions, and view interactive price heatmaps.

---

## 🏗️ Solution Architecture

The project is structured into three clean, decoupled layers:

*   **Backend (Python, FastAPI, LangGraph):** Handles API routing, background scheduling, multi-agent pipeline execution, LLM-based analysis, and database integrations.
*   **Frontend (Flutter - Mobile & Web):** A premium, glassmorphic dark-theme UI featuring Google Fonts (Outfit), interactive 5-city price heatmaps (Karachi, Lahore, Islamabad, Peshawar, Multan), chat logs, policy simulations, and action dispatchers.
*   **Infrastructure (Docker, Nginx, Firebase, SQLite):** Docker Compose manages the containerized runtimes. SQLite persists local baseline telemetry, while Firebase Firestore stores dynamic pipeline execution logs, insights, and actions.

```
faslbot/
├── backend/                  # FastAPI Application
│   ├── main.py               # Entrypoint & endpoint declarations
│   ├── scheduler.py          # Cron jobs for autonomous pipeline runs
│   ├── config.py             # Environment configuration
│   ├── agents/               # 6-Agent LangGraph Pipeline definition
│   ├── chat_agent/           # Causal Reasoning Engine & SQLite database
│   ├── services/             # Firebase, Gemini, and SMS integrations
│   └── data/                 # Raw scrapers (PBS, WFP, News, Weather)
├── mobile/                   # Flutter App (Mobile, Desktop, and Web)
│   ├── lib/
│   │   ├── main.dart         # Material 3 entry & global dark theme
│   │   ├── config/           # API environment routing
│   │   └── screens/          # Dashboard, Heatmap, Action Logs, and Chat screens
│   ├── Dockerfile            # Multi-stage Flutter Nginx container configuration
│   └── nginx.conf            # Nginx reverse proxy configuration
└── docker-compose.yml        # Multi-container local/prod orchestrator
```

---

## 🧠 Developed AI Agents

FaslBot leverages Google Gemini (1.5 Flash & 2.0 Flash) and LangGraph to orchestrate intelligence at scale:

### A. Autonomous 6-Agent LangGraph Pipeline
Our background workflow coordinates the following agents sequentially:
1.  **DataIngestor Agent:** Aggregates live price feeds from the Pakistan Bureau of Statistics (PBS), cross-validates them against World Food Programme (WFP) historical records, and scrapes RSS agricultural news.
2.  **InsightExtractor Agent:** Analyzes the ingested datasets to extract significant insights like city-to-city price arbitrage, sudden price spikes, and policy anomalies.
3.  **ImpactAnalyst Agent:** Projects the socio-economic impacts on Pakistani farming demographics, calculates the financial PKR value-at-stake, and computes a dynamic market severity score (0–10).
4.  **ActionPlanner Agent:** Weighs the urgency and feasibility of potential actions to generate exactly three concrete interventions (e.g., strategic grain reserve release, targeted SMS blasts, or procurement advisories).
5.  **ActionExecutor Agent:** Executes the highest-ranked action (such as sending automated Urdu SMS alerts to regional farmers via Telenor).
6.  **AuditLogger Agent:** Saves the complete pipeline execution trace, agent thoughts, and results to Firestore to ensure absolute transparency.

### B. Interactive 3-Layer Causal Reasoning Engine (Chat)
For natural language queries, FaslBot implements a custom **3-layer reasoning framework** inside the Chat Agent:
*   **Layer 1 (Historical Baseline):** Queries SQLite to compile historical averages, baseline price volatility, and climate standards.
*   **Layer 2 (Current Reality):** Automatically fetches live telemetry (Apify scrapers, weather conditions, disaster bulletins) matching the user's geographical and temporal query intent.
*   **Layer 3 (Reasoning Fusion):** Combines Layers 1 and 2 to build causal chains, resolve contradictions (e.g., warning if news reports crop damage while weather telemetry shows zero recent rainfall), predict forward-looking risk forecasts, and formulate actionable recommendations.

---

## 🔌 Integrated APIs (Real & Mock)

FaslBot incorporates a hybrid API architecture to ensure reliability:
*   **Google Gemini API (Real):** Used for advanced agent processing, translation, and causal reasoning.
*   **WeatherAPI (Real):** Fetches real-time weather logs (temperatures, precipitation, and humidity anomalies) for Pakistani regions.
*   **News Scrapers (Real):** Custom scraper searching RSS feeds (Dawn, ARY News, Geo) and DuckDuckGo search queries via LangChain.
*   **Telenor SMS Gateway (Mock/Real):** Operates in two modes. If credentials are empty, it defaults to Mock mode to simulate successful regional SMS campaigns. In Production mode, it integrates with a gateway (or Twilio fallback) to dispatch real SMS messages to target coordinates.
*   **Firebase Firestore (Real):** Synchronizes database states instantly with the Flutter client dashboard.
*   **SQLite (Real local file):** Serves as a localized database for fast query mapping, causal simulation records, and historical agricultural benchmarks.

---

## 📱 Premium Flutter Client App

The Flutter client dashboard acts as a digital "war room" for agricultural commodity managers:
*   **Onboarding Tour:** Smooth introductions outlining FaslBot's core features.
*   **Main Dashboard:** Displays real-time severity ratings, estimated financial value-at-stake, latest extracted insights, and manual triggers to run the background agent pipeline instantly.
*   **Market Heatmap:** Highlights real-time commodity prices and city spreads (Karachi, Lahore, Islamabad, Peshawar, Multan) using glassmorphic UI elements and neon status markers (#00FFA3 for normal, #FFD700 for warning, #FF4757 for emergency).
*   **Action Log:** Shows detailed history of sent SMS alerts, simulation steps, and gateway logs.
*   **Causal Reasoning Chat:** Features a rich interactive terminal. Users can type queries, view calculated risk level badges, read detailed causal summaries, and view expanded source logs.

---

## 🚀 Installation & Quick Start

### A. Docker Compose Setup (Recommended)
Launch the entire system inside containerized environments with a single command:

1.  Clone the repository and navigate to the project directory:
    ```bash
    cd AI-Seekho-Hackathon/AI Seekho Hackathon/faslbot
    ```
2.  Configure your environment variables:
    ```bash
    cp .env.example .env
    ```
    *Open the `.env` file and insert your API tokens (e.g., `GOOGLE_API_KEY`, `FIREBASE_PROJECT_ID`, etc.).*
3.  Add your Firebase Service Account JSON credentials to `backend/serviceAccountKey.json`.
4.  Build and run the containers:
    ```bash
    docker compose up -d --build
    ```
5.  Access the services:
    *   **Flutter Web Frontend:** [http://localhost/](http://localhost/)
    *   **FastAPI Backend Server:** [http://localhost:8000/docs](http://localhost:8000/docs)

### B. Manual Development Setup
If you want to run the components locally without Docker:

#### 1. Backend Setup
Make sure you have Python 3.11+ installed.
```bash
cd backend
python -m venv venv
source venv/bin/activate # Linux/Mac
# or: venv\Scripts\activate on Windows

pip install -r requirements.txt
cp .env.example .env
# Edit .env and verify serviceAccountKey.json is in backend/
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Flutter Setup
Ensure you have the Flutter SDK configured.
```bash
cd ../mobile
flutter pub get
flutter run -d chrome # Run web version
# or run on connected mobile device
```

---

## ☁️ Render Deployment & DevOps

FaslBot is configured for cloud deployment on platforms like Render:
*   **Unified Blueprint (`render.yaml`):** The root repository contains a `render.yaml` template configured to deploy the FastAPI backend and a static/containerized frontend service, setting up automatic environment variables, persistent disks, and build hooks.
*   **Docker Container Packaging:** Includes production-grade Dockerfiles. The frontend container compiles the Flutter web bundle into optimized HTML/JS assets and serves them via an Nginx web server config that reverse-proxies `/api/` calls back to the FastAPI container seamlessly.

---

## 📂 Trace Logs (Proof of Agentic Development)

This project has been developed in a verified agentic workflow using **Antigravity**. The `antigravity_traces_export` directory contains a comprehensive record of the development journey:
*   **Implementation Plans:** Multi-step architecture documents approved before edits.
*   **Task Logs:** Step-by-step checklists representing verified features.
*   **Walkthroughs:** System verification plans, automated testing summaries, and final compliance checks.

These files serve as concrete proof of our iterative design process, showcasing how we collaborated with agentic frameworks to build, deploy, and dockerize this high-impact agricultural platform.

---
<div align="center">

**FaslBot — فصل بوٹ**  
*Empowering Pakistan's Farmers with Autonomous Intelligence.*

</div>
