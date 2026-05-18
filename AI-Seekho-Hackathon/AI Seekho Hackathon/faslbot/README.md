# 🌾 FaslBot: Autonomous AI Market Intelligence for Pakistan's Agriculture

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flutter](https://img.shields.io/badge/Flutter-3.4+-02569B?style=flat&logo=flutter&logoColor=white)](https://flutter.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-orange?style=flat)](https://langchain.dev/langgraph/)
[![Gemini](https://img.shields.io/badge/Gemini-1.5%20Flash-4285F4?style=flat&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=flat&logo=firebase&logoColor=white)](https://firebase.google.com/)

---

## 🏆 AI Seekho 2026 Hackathon | Challenge 1: Content-to-Action

> **Transforming passive agricultural data into autonomous, actionable intelligence for Pakistan's 22+ million farmers**

---

## 🚨 The Problem

Pakistan's agricultural sector faces a **crisis of information asymmetry**:

- **Price Volatility**: Wheat prices swing from PKR 115/kg in Karachi to PKR 162/kg in Quetta — a 40% spread that goes undetected by farmers
- **Market Exploitation**: Without real-time data, farmers sell at mandis where traders dictate prices, losing 15-40% of potential earnings
- **Data Gap**: Government data (PBS) exists but remains inaccessible in spreadsheets — farmers cannot act on it
- **Crisis Blindness**: Price spikes (onions, tomatoes) emerge without warning; by the time farmers learn, the opportunity is gone

**The result?** Pakistani farmers lose PKR 200+ billion annually to middlemen and market inefficiencies.

---

## 💡 The Solution

**FaslBot (فصل بوٹ)** is an autonomous multi-agent AI system that bridges the gap between government data and the farmer's field:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FaslBot Autonomous Pipeline                        │
│                                                                              │
│  📊 DATA INGESTION          🧠 AI ANALYSIS              📱 AUTOMATED ACTION  │
│                                                                              │
│  ┌─────────────┐           ┌─────────────────┐         ┌─────────────────┐ │
│  │ PBS Prices │──────────▶│ Gemini 1.5 Flash│────────▶│   Telenor SMS   │ │
│  │ (Weekly)    │           │ (LangGraph)     │         │   (Urdu)        │ │
│  └─────────────┘           └─────────────────┘         └─────────────────┘ │
│         │                         │                           │             │
│  ┌─────────────┐           ┌─────────────────┐         ┌─────────────────┐ │
│  │ WFP Data   │──────────▶│ 6-Agent Pipeline│────────▶│  Firestore      │ │
│  │ (Global)   │           │ (Orchestrated)  │         │  (Audit Log)    │ │
│  └─────────────┘           └─────────────────┘         └─────────────────┘ │
│                                                                              │
│  Result: Real-time arbitrage detection → Urdu SMS alerts → Empowered farmers│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Core Features

### 🔄 Autonomous Ingestion
- **PBS Data**: Weekly scraping of Pakistan Bureau of Statistics commodity prices
- **WFP Data**: World Food Programme global price benchmarks for cross-validation
- **RSS News**: Real-time agricultural news from Dawn, ARY News, Geo News
- **Fallback System**: Seed data auto-loads on API failures — never goes down

### 🧠 AI Orchestration (6-Agent LangGraph Pipeline)
| Agent | Role | Capability |
|-------|------|------------|
| 🔷 **DataIngestor** | Data Collection | Fetches PBS/WFP prices + RSS news |
| 🔷 **InsightExtractor** | AI Analysis | Gemini 1.5 Flash finds arbitrage & spikes |
| 🔷 **ImpactAnalyst** | Stakeholder Impact | Calculates severity, value at stake |
| 🔷 **ActionPlanner** | Action Ranking | Ranks SMS, Mandi updates, procurement |
| 🔷 **ActionExecutor** | Execution | Sends Urdu SMS via Telenor API |
| 🔷 **AuditLogger** | Compliance | Full Firestore audit trail |

### 📱 Localized Action
- **Automated SMS**: Urdu-language alerts sent directly to farmers via Telenor
- **Smart Routing**: Alerts targeted by city/commodity relevance
- **Mock Mode**: Test without real SMS credentials

### 🗺️ Interactive Heatmap
- **5 Cities**: Karachi, Lahore, Islamabad, Peshawar, Multan
- **Real-time Updates**: Live price spreads visualization
- **Premium UI**: Glassmorphic cards with neon accents (#00FFA3, #FFD700)

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | Python 3.11+ | Core logic |
| **API** | FastAPI | High-performance REST endpoints |
| **AI Orchestration** | LangGraph | Multi-agent pipeline coordination |
| **LLM** | Google Gemini 1.5 Flash | Natural language understanding & generation |
| **Database** | Firebase Firestore | Real-time audit logs & action history |
| **SMS** | Telenor API | Automated farmer notifications |
| **Frontend** | Flutter (Web/Mobile) | Cross-platform UI |
| **Design** | Glassmorphism + Neon | Premium dark theme aesthetic |

---

## 🚀 Installation Guide

### Backend Setup

```bash
# Navigate to backend
cd faslbot/backend

# Create virtual environment
uv venv --python 3.11 venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Frontend Setup

```bash
cd faslbot/mobile

# Install Flutter dependencies
flutter pub get

# Run the app
flutter run
```

---

## 📁 Project Structure

```
faslbot/
├── 📂 backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment configuration
│   ├── scheduler.py               # APScheduler for auto-runs
│   ├── agents/                    # 6-Agent LangGraph pipeline
│   │   ├── orchestrator.py        # Pipeline orchestration
│   │   ├── data_ingestor.py       # Agent 1: Data fetching
│   │   ├── insight_extractor.py   # Agent 2: AI analysis
│   │   ├── impact_analyst.py      # Agent 3: Impact calculation
│   │   ├── action_planner.py      # Agent 4: Action planning
│   │   ├── action_executor.py     # Agent 5: SMS execution
│   │   └── audit_logger.py        # Agent 6: Firestore logging
│   ├── data/
│   │   ├── fetchers/              # PBS, WFP, RSS fetchers
│   │   ├── processors/            # Price arbitrage/spike detection
│   │   └── seeds/                 # Fallback sample data
│   ├── services/
│   │   ├── gemini_service.py      # Gemini API wrapper
│   │   ├── sms_service.py          # Telenor SMS integration
│   │   └── firebase_service.py    # Firestore CRUD operations
│   └── requirements.txt
│
├── 📂 mobile/
│   ├── lib/
│   │   ├── main.dart              # App entry + dark theme
│   │   ├── config/
│   │   │   └── api_config.dart     # Centralized API configuration
│   │   └── screens/
│   │       ├── dashboard_screen.dart
│   │       ├── market_heatmap_screen.dart
│   │       └── action_log_screen.dart
│   └── pubspec.yaml
│
└── 📂 scripts/
    └── setup.sh                   # One-command setup
```

---

## 📊 Sample Output

### Arbitrage Detection
```json
{
  "type": "price_arbitrage",
  "commodity": "Wheat",
  "buy_city": "Karachi",
  "sell_city": "Quetta",
  "spread_pct": 40.9,
  "net_spread_pkr": 47.0,
  "viability": "high"
}
```

### Urdu SMS Alert
> **فصل بوٹ:** گندم کی قیمت میں 40.9% فرق! کراچی سے کوئٹہ بیچنے سے 47 روپے فی کلو کا فائدہ۔

### Heatmap Visual
| City | Wheat (PKR/kg) | Tomato (PKR/kg) |
|------|----------------|-----------------|
| Karachi | 118 | 85 |
| Lahore | 128 | 88 |
| Islamabad | 132 | 90 |
| Peshawar | 135 | 210 |
| Multan | 155 | 82 |

---

## 🔑 Key Innovation Points

1. **Autonomous Pipeline**: No human intervention required — data → analysis → action
2. **Multi-Source Validation**: PBS + WFP + RSS for comprehensive market view
3. **Urdu Localization**: Every insight translated for farmer accessibility
4. **Full Auditability**: Every decision logged to Firestore for compliance
5. **Graceful Degradation**: Seed data ensures system never fails completely

---

## 📄 License

MIT License — Open for contributions and learning!

---

## 🙏 Acknowledgments

- [LangGraph](https://langchain.dev/langgraph/) — Agentic AI orchestration
- [Google Gemini](https://deepmind.google/technologies/gemini) — Intelligence engine
- [Pakistan Bureau of Statistics](https://www.pbs.gov.pk/) — Price data source
- [World Food Programme](https://www.wfp.org/) — Global price benchmarks
- [Telenor Pakistan](https://www.telenor.com/) — SMS integration partner

---

<div align="center">

**Built with ❤️ for Pakistan's Farmers**

*FaslBot — فصل بوٹ*
*Autonomous Agricultural Intelligence*

</div>