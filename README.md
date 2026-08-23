# 🌊 TIDE — Trusted Intelligent Digital Ecosystem Registry
### *A Living, Self-Verifying Blue Carbon MRV & Living Credit System*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.24-363636.svg?style=flat&logo=solidity&logoColor=white)](https://soliditylang.org)
[![ERC-1155](https://img.shields.io/badge/Standard-ERC--1155%20Living%20Credits-blue.svg?style=flat&logo=ethereum&logoColor=white)](https://eips.ethereum.org/EIPS/eip-1155)
[![Sentinel-2](https://img.shields.io/badge/EO%20Data-Sentinel--2%20%7C%20GEE-4B8BBE.svg?style=flat&logo=google-earth&logoColor=white)](https://earthengine.google.com)
[![Tests](https://img.shields.io/badge/Tests-136%2F136%20Passed-10b981.svg?style=flat)]()
[![License](https://img.shields.io/badge/License-MIT-blue.svg)]()

---

## 📌 Executive Summary

Most blockchain carbon projects mint a static token once and stop. The fundamental flaw is that **conventional credits remain tradable on secondary markets even if the underlying mangrove forest dies, degrades, or is cleared** between rare multi-year verification audits.

**TIDE (Trusted Intelligent Digital Ecosystem Registry)** solves this by introducing **Living Carbon Credits**:
> *"We do not tokenize a one-time claim about a wetland; we maintain an auditable claim whose validity dynamically changes with the real-world health of the wetland."*

TIDE fuses continuous **Sentinel-2 Earth Observation**, **on-ground IoT water/soil sensors**, and **local community ground-truth reports** into a tamper-evident **ERC-1155 Living Credit smart contract** that automatically freezes trading the moment degradation is detected.

---

## 🏛️ Domain Grounding & Methodology

* **Ecosystem Target:** Coastal blue carbon ecosystems (Mangroves, Seagrass Meadows, Tidal Marshes) storing up to $10\times$ more carbon per hectare than terrestrial rainforests.
* **National Alignment:** Aligned with India's **MISHTI** (*Mangrove Initiative for Shoreline Habitats & Tangible Incomes*) targeting $\sim 540\text{ km}^2$ of coastal mangrove restoration.
* **Methodological Basis:**
  * **Verra VM0007 / VM0033** principles for baseline carbon accounting and conservative lower-bound crediting:
    $$C_{lower} = C_{estimate} - 1.645\sigma \quad (\text{90\% One-Sided Conservative Confidence Interval})$$
  * Only $C_{lower}$ is minted, protecting buyers against over-crediting risk.
  * **VCS AFOLU Non-Permanence Risk Tool** for tidal volatility penalties and permanence scoring.

---

## 🏗️ System Architecture

```
                         BLUE CARBON PROJECT REGISTRATION
                      (GPS polygon boundary, Area Ha, Baseline NDVI)
                                     │
                                     ▼
                        ┌─────────────────────────┐
                        │   DIGITAL CARBON TWIN    │ (Time-versioned snapshot history)
                        └────────────┬─────────────┘
                  ┌──────────────────┼──────────────────┐
                  ▼                  ▼                   ▼
            IoT Edge Data     Satellite Imagery   Community Field Alerts
         (Salinity, pH, Temp,  (Sentinel-2 NDVI,   (Geotagged photos +
          Soil, Water Table)    Change Detection)    IPFS CID verification)
                  │                  │                   │
                  └──────────────────┼───────────────────┘
                                     ▼
                       DATA FUSION + VALIDATION
                     (Sensor Trust Score T_sensor,
                      Spatial & Temporal Consistency)
                                     ▼
                          ┌─────────────────────┐
                          │     AI/ML ENGINE     │
                          ├───────────┬─────────┤
                          ▼           ▼         ▼
                    Carbon Model  Anomaly ML  Uncertainty Model
                     (Pham 2019)  (IsoForest)  (Verra VM0007)
                          └───────────┼─────────┘
                                     ▼
                      MRV FUSION ENGINE — Confidence Score
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
               Score ≥ 85%                      Score < 60%
                     │                               │
                     ▼                               ▼
       LIVING CARBON CREDIT ENGINE        ORACLE → SMART CONTRACT
        (Mints conservative C_lower)       (Triggers Automatic FREEZE)
                     │                               │
                     ▼                               ▼
             Polygon / Hardhat                 Transfers Locked!
           ERC-1155 ACTIVE Token           Reverification Requested
```

---

## 🔄 The Living Credit State Machine

```
    ┌──────────┐
    │ PROPOSED │  (Project registered with GPS boundary & baseline)
    └────┬─────┘
         │ Auditor approval & conservative minting (C_lower)
         ▼
    ┌──────────┐
    │  ACTIVE  │ ◄──────────┐  (Tradeable & transferable in marketplace)
    └────┬─────┘            │
         │                  │ Auditor reverification confirms
         │ Degradation      │ canopy regrowth & field recovery
         │ Anomaly Flag     │
         │ (NDVI drop >15%) │
         ▼                  │
    ┌──────────┐            │
    │  FROZEN  ├────────────┘  (Transfers BLOCKED on-chain!)
    └────┬─────┘
         │ Permanent ecological loss confirmed
         ▼
    ┌──────────┐
    │ REVOKED  │  (Permanently invalidated & burned)
    └──────────┘

    [ RETIRED ] ───► Carbon offset claimed by corporate buyer, tokens permanently burned
```

---

## 🎛️ The 4 Interactive Role Portals

TIDE provides dedicated portals for every stakeholder in the blue carbon lifecycle, unified into a single responsive web interface:

| Portal | Role | Key Capabilities |
|---|---|---|
| **🏛️ Government / Admin** | Registry Authority | System-wide acreage & credit KPIs, MRV threshold policy sliders (`MINT_THRESHOLD`, `FREEZE_THRESHOLD`), manual audit overrides, community report moderation. |
| **🌿 Project Developer** | Restoration Manager | Plot registration, real-time IoT Ground Station telemetry, Sensor Trust Score ($T_{sensor} = 96/100$), Continuous MRV estimation, Verra VM0007 $C_{lower}$ minting. |
| **💼 ESG Corporate Buyer** | Institutional Buyer | Living Credits marketplace, Proof-of-Permanence explorer, on-chain transfer protections (blocks transfers of frozen credits), permanent offset retirement with **Official Certificate of Carbon Retirement**. |
| **👥 Community Steward** | Local Fisherfolk / Wardens | Geotagged field reporting, photographic evidence upload with IPFS CID hashing (`ipfs://Qm...`), community reputation karma points, public transparency feed. |

---

## 🎬 The 6-Scene Hackathon Demo Script

The top demo controller toolbar in the UI enables running the complete end-to-end verification story in 2 minutes:

* **Scene 1 (Healthy Baseline):** `MNG-001` (Pichavaram, 280 Ha) registered. Baseline NDVI 0.42. Verra VM0007 conservative creditable estimate: $32.1\text{ tCO}_2\text{e}$. Status: **`ACTIVE`**.
* **Scene 2 (Real-Time IoT Ground Stream):** Ground station telemeters Salinity 14 ppt, pH 7.8, Temp 28.5°C. Sensor Trust Score: **96/100**.
* **Scene 3 (Community Field Alert):** Coastal warden submits geotagged clearing report with photo evidence anchored to IPFS CID.
* **Scene 4 (Satellite Degradation Detected):** Sentinel-2 NDVI drops 57% ($0.42 \to 0.18$). AI anomaly severity spikes to 1.0. Fused MRV confidence drops below 60%.
* **Scene 5 (Smart Contract Auto-Freeze):** Oracle triggers on-chain freeze. Living Credit status flips to **`FROZEN`**. Attempts to transfer tokens on-chain are immediately blocked!
* **Scene 6 (Reverification & Offset Retirement):** Restoration inspection clears anomaly $\to$ status restored to **`REVERIFIED`**. ESG corporate buyer retires 5.0 tonnes and generates an immutable Certificate of Carbon Retirement.

---

## 📂 Repository Structure

```
blue-carbon-mrv/
├── ai/                          # M1: AI/ML Intelligence Microservice (Port 8001)
│   ├── data/                    # Sentinel-2 NDVI time series & literature calibration
│   ├── models/                  # Trained carbon regression & IsolationForest models
│   ├── carbon_model.py          # Biomass & carbon estimation (Pham et al. 2019 calibrated)
│   ├── anomaly_model.py         # 2-Layer anomaly detector (rule-based + IsolationForest)
│   ├── uncertainity.py          # Verra VM0007 90% confidence conservative lower-bound
│   ├── mrv_confidence.py        # 5-signal weighted fusion engine
│   ├── ndvi_trend.py            # 24-month Sentinel-2 NDVI linear trend detector
│   ├── simulator.py             # IoT sensor reading generator (normal & anomaly modes)
│   ├── api.py                   # FastAPI service (Port 8001)
│   └── test_api.py              # 31/31 passing unit tests
│
├── digital-twin/                # M2: Digital Twin & GIS Microservice (Port 8002)
│   ├── gis/                     # GeoJSON boundary, centroid, GMW extent history (2000-2020)
│   ├── satellite/               # Sentinel-2 composite & NDVI change detection
│   ├── temporal/                # Time-versioned snapshot store, health & permanence scoring
│   ├── map/                     # Folium / Leaflet interactive GIS map render
│   ├── api.py                   # FastAPI service (Port 8002)
│   ├── seed.py                  # 4 demo temporal snapshots (healthy->stressed->frozen->restored)
│   └── test_api.py              # 55/55 passing unit tests
│
├── blockchain/                  # M4: Smart Contracts & Web3 SDK
│   ├── contracts/               # TIDEBlueCarbonRegistry.sol (ERC-1155 Living Credit)
│   ├── test/                    # Hardhat test suite (100% pass)
│   ├── scripts/                 # deploy.js & simulate-oracle-events.js (9-scene simulation)
│   ├── sdk/                     # JavaScript integration SDK & ABI exports
│   └── hardhat.config.js        # Hardhat config (Solidity 0.8.24, Cancun EVM)
│
├── backend/                     # M5: Unified Backend Hub & Multi-Role Portal (Port 8000)
│   ├── templates/
│   │   └── index.html           # Unified 4-Role Portal SPA (Admin, Developer, Buyer, Community)
│   ├── database.py              # SQLite storage (plots, observations, credits, retirements)
│   ├── services.py              # Fast-fail HTTP client proxies for AI & Twin services
│   ├── config.py                # Service URLs, plot defaults, regulatory thresholds
│   ├── seed.py                  # Multi-project sample data seed (Pichavaram, Sundarbans, Mannar)
│   ├── api.py                   # Integration FastAPI app (Port 8000)
│   └── test_api.py              # 50/50 passing integration tests
│
├── workflow.md                  # System specification & hackathon execution blueprint
├── walkthrough.md               # Visual verification report & screenshots
└── README.md                    # Project documentation
```

---

## ⚡ Microservices Architecture

| Service | Subsystem | Port | Technologies | Tests |
|---|---|---|---|---|
| **Backend Hub & Portal** | M5 / M6 | `8000` | FastAPI, SQLite, Vanilla HTML5/CSS3/JS | 50 / 50 ✅ |
| **AI / ML Intelligence** | M1 | `8001` | FastAPI, Scikit-Learn, NumPy, Pandas | 31 / 31 ✅ |
| **Digital Twin & GIS** | M2 | `8002` | FastAPI, GeoPandas, Shapely, Folium | 55 / 55 ✅ |
| **Blockchain Smart Contract** | M4 | Local / Amoy | Solidity 0.8.24, Hardhat, OpenZeppelin v5, Ethers.js | 100% ✅ |

---

## 🚀 Quick Start Guide

### Prerequisites
* Python 3.10 or 3.11
* Node.js v18+ (for blockchain tests)

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/your-username/blue-carbon-mrv.git
cd blue-carbon-mrv

python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Backend Hub dependencies
pip install -r backend/requirements.txt

# AI Engine dependencies
pip install -r ai/requirements.txt

# Digital Twin dependencies
pip install -r digital-twin/requirements.txt

# Blockchain dependencies
cd blockchain && npm install && cd ..
```

### 3. Launch All Services

Open three terminal windows (with virtualenv activated):

```bash
# Terminal 1: AI / ML Microservice (Port 8001)
cd ai
python -m uvicorn api:app --port 8001

# Terminal 2: Digital Twin & GIS Microservice (Port 8002)
cd digital-twin
python -m uvicorn api:app --port 8002

# Terminal 3: Unified Backend Hub & Multi-Role Portal (Port 8000)
cd backend
python -m uvicorn api:app --port 8000
```

### 4. Open the Web Application

Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser to access the live TIDE Portal!
* Swagger API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
* AI API Docs: [http://localhost:8001/docs](http://localhost:8001/docs)
* Digital Twin API Docs: [http://localhost:8002/docs](http://localhost:8002/docs)

---

## 🧪 Automated Testing Suite

Run the automated test suites to verify 100% end-to-end functionality:

```bash
# 1. Backend Hub & Multi-Role Integration Tests (50 checks)
cd backend
python test_api.py

# 2. AI / ML Intelligence Tests (31 checks)
cd ../ai
python test_api.py

# 3. Digital Twin & GIS Tests (55 checks)
cd ../digital-twin
python test_api.py

# 4. Smart Contract Unit Tests
cd ../blockchain
npm run test
```

**Total Test Coverage:** `136 / 136 checks passing (100% PASS)`

---

## 👥 Team & Subsystem Ownership

| Role | Subsystem | Ownership Scope |
|---|---|---|
| **M1 — AI/ML Lead** | `ai/` | Biomass regression model, 2-layer anomaly detector, Verra VM0007 uncertainty crediting, NDVI trend detector. |
| **M2 — Digital Twin & GIS Lead** | `digital-twin/` | Spatial polygon boundary, Sentinel-2 composite change detection, time-versioned twin history, Folium map rendering. |
| **M3 — IoT / Edge Lead** | `ai/simulator.py` | Sensor stream simulator, Bioclimatic range rules, Sensor Trust Score ($T_{sensor}$) computation. |
| **M4 — Blockchain Lead** | `blockchain/` | ERC-1155 Living Credit smart contract, status state machine, on-chain transfer freeze enforcement, retirement certificates. |
| **M5 — Backend / MRV Lead** | `backend/` | Microservices orchestration hub, SQLite persistence, MRV multi-stream confidence fusion. |
| **M6 — Frontend & Community Lead** | `backend/templates/` | 4-Role Unified Portal UI, Proof-of-Permanence explorer, community ground-truth feed, 6-scene demo runner. |

---

## ⚖️ License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<div align="center">
  <sub>Built for the <strong>Smart India Hackathon</strong> • Ministry of Earth Sciences (MoES)</sub><br>
  <sub><strong>TIDE Registry</strong> — <em>Because trust in blue carbon requires continuous verification.</em></sub>
</div>
