# TIDE — Trusted Intelligent Digital Ecosystem Registry
### A Living, Self-Verifying Blue Carbon MRV System
**Unified plan — merged from both source documents, best approach selected from each**

> **Note on sources:** Doc 1 (the architecture/slide plan) is strong on team structure, the Digital Twin concept, and demo storytelling, but light on domain grounding. Doc 2 (the SIH research document) is strong on domain research, database/API design, a realistic 3-day plan, and judge defense — but its team split and demo narrative are thinner. This plan takes doc 2 as the operational backbone (it's the more execution-ready of the two) and grafts in doc 1's sharper product ideas: the "one person, one subsystem" ownership model, the Digital Twin's temporal state examples, the Sensor Trust Score, and the six-scene demo script.

---

## 1. Core Idea (why this beats a plain "carbon token")

Most blockchain-carbon hackathon projects mint a token once and stop. The differentiated pitch here — present in both docs, and the strongest idea in either — is the **Living Carbon Credit**: a credit whose blockchain status is continuously tied to the real-world health of the ecosystem that backed it, not a one-time certification.

```
Evidence → Intelligence → Trust
(IoT, satellite,      (Digital Twin,      (Blockchain,
 community)            AI estimate,        Living Credits,
                        anomaly,            freeze/reverify)
                        uncertainty,
                        MRV confidence)
```

**One-line pitch (doc 2, kept as-is — it's the tightest version):**
> "We do not tokenize a one-time claim about a wetland; we maintain an auditable claim whose validity changes with the wetland."

---

## 2. Problem Statement

- Field surveys happen infrequently; degradation can occur *between* verification cycles.
- Carbon stock estimates carry real uncertainty that is often hidden from buyers.
- Satellite, IoT, and community data usually live in disconnected systems.
- Carbon credits often stay tradable even after the ecosystem backing them is damaged.
- Local communities are treated as passive data sources, not verification stakeholders.
- No shared, tamper-evident audit trail across stakeholders.

**Disclaimer to state explicitly in the pitch (doc 2):** *"The project is inspired by established blue-carbon accounting principles but is not itself a certified methodology or an approved carbon-credit registry."* Do not claim scientific/legal certification for the prototype's estimates.

---

## 3. Domain Grounding (keep — this is what makes the pitch credible to judges)

- **Blue carbon** = carbon stored by mangroves, seagrass meadows, and tidal salt marshes, largely in waterlogged sediment where decomposition is slow.
- **India context:** a 2025 parliamentary response citing the India State of Forest Report 2023 puts India's mangrove cover at 4,991.68 km² (~0.15% of land area) — cite the source and year, since this figure changes across assessments.
- **MISHTI** (Mangrove Initiative for Shoreline Habitats & Tangible Incomes), launched by MoEFCC in 2023, targets ~540 km² of restoration across nine states and three UTs over five years. Position TIDE as a *possible future digital MRV layer* for such programs — not a replacement for government systems.
- **Methodology reference:** Verra's VM0033 (tidal wetland/seagrass restoration) is the right thing to cite for baselines, uncertainty deduction, permanence, and reversal risk — plus the VCS AFOLU Non-Permanence Risk Tool for erosion/sea-level-rise risk. Reference these as inspiration, not compliance.

---

## 4. System Architecture (merged)

```
                         BLUE CARBON PROJECT REGISTRATION
                              (GPS boundary polygon)
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │   DIGITAL CARBON TWIN    │
                          └────────────┬─────────────┘
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                   ▼
                 IoT Data       Satellite Data       Community Reports
                    │                  │                   │
                    └──────────────────┼───────────────────┘
                                       ▼
                        DATA FUSION + VALIDATION (data-quality checks,
                          timestamping, geolocation, sensor trust score)
                                       ▼
                            ┌─────────────────────┐
                            │     AI/ML ENGINE      │
                            ├───────────┬───────────┤
                            ▼           ▼           ▼
                     Carbon Model  Anomaly Model  Uncertainty Model
                            └───────────┼───────────┘
                                       ▼
                       MRV ENGINE — fused Confidence Score
                                       ▼
                              > threshold? ── NO → human review
                                       │YES
                                       ▼
                        LIVING CARBON CREDIT ENGINE
                        (mints conservative lower-bound quantity)
                                       ▼
                               ORACLE → BLOCKCHAIN
                                       ▼
                                  MONITORING LOOP
                              ┌────────┴─────────┐
                        No degradation      Degradation event
                              ▼                    ▼
                           ACTIVE            AT-RISK → smart contract
                                                    FREEZE + create
                                                    reverification request
                                                    │
                                          ┌─────────┴─────────┐
                                          ▼                   ▼
                                    REVERIFIED            REVOKED
                                     → ACTIVE
```

**Registry / access layer** on top of this: Government/Admin dashboard, Project-owner dashboard, Buyer/marketplace view (with full evidence trail), Community reporting app.

### Recommended tech stack (merged, de-duplicated)

| Layer | Technology |
|---|---|
| Frontend | React + Tailwind |
| Maps | Leaflet (OpenStreetMap) |
| Backend | Python FastAPI |
| Database | PostgreSQL + PostGIS |
| AI/ML | Python, NumPy/pandas, scikit-learn (avoid deep learning — no time) |
| Satellite | Sentinel-2 imagery → NDVI/EVI via GeoPandas + Rasterio |
| IoT | ESP32 (2–4 real sensors) + Python simulator for the rest |
| Communication | MQTT |
| Evidence storage | IPFS (hash-anchored on-chain) |
| Blockchain | Solidity on Polygon Amoy testnet or local Hardhat network |
| Token model | ERC-1155 (credit *batches* per plot + reporting period — better than plain ERC-20, and simpler than a fully custom token) |
| Smart-contract tooling | Hardhat/Foundry + OpenZeppelin |
| Blockchain API | ethers.js / Web3.py |
| Charts | Plotly |
| Auth | JWT |
| Deployment | Docker |

*Why ERC-1155 over the "just build an ERC-20 token" instinct in doc 1:* it lets one token ID represent one plot + monitoring period, which maps naturally onto the Living Credit lifecycle and avoids needing a separate registry contract per project.

---

## 5. The AI/ML Layer (three outputs, not one)

**A. Carbon estimation** — inputs: NDVI, EVI, mangrove area, vegetation density, water/soil parameters, restoration age, historical biomass.

```
biomass = a + b·NDVI + c·NDVI²
carbon  = biomass × carbon_fraction
CO2e    = carbon × 44/12
```
Coefficients configurable; label clearly as a prototype estimate, not certified.

**B. Anomaly detection** — flag: impossible sensor readings, sudden biomass jumps or vegetation loss, suspicious plantation claims, sensor tampering, satellite/IoT disagreement, inconsistent community reports. Use transparent rule-based thresholds for the demo (NDVI drop >20%, salinity above threshold for 3 consecutive readings) — an Isolation Forest is a reasonable stretch goal, but don't burn hackathon time training deep models.

**C. Uncertainty + conservative crediting** (doc 2's formula — this is the more defensible version and should be the one used):

```
C_lower = C_estimate − 1.645σ        (≈ 90% one-sided lower bound)
```
Example: estimate 42 tCO₂e, σ = 6 → lower bound ≈ 32.1 tCO₂e. **Mint no more than this lower-bound quantity.**

**REST response contract:**
```json
{
  "plotId": "MNG-001",
  "carbon_estimate": 42.0,
  "standard_deviation": 6.0,
  "confidence_level": 0.90,
  "creditable_carbon": 32.1,
  "anomaly_score": 0.08,
  "health_score": 87
}
```

**Sensor Trust Score (doc 1's idea, worth keeping):** cross-check IoT readings against satellite/environment expectations (e.g. sensor reports salinity 32 ppt but the environment model expects 10–18 ppt) → flag a *sensor reliability warning* and assign the device a trust score (e.g. 62/100). This means the MRV engine never blindly trusts a single IoT reading, and it's a nice differentiator to mention to judges.

---

## 6. Digital Carbon Twin (doc 1's strongest visual feature — keep and lead with it)

One live record per plot: ID, boundary, area, mangrove density, carbon stock, biomass, health score, biodiversity, water/soil conditions, restoration age, carbon confidence, permanence score — and **it changes over time**, which is the point:

| | Day 1 | After cyclone | After restoration |
|---|---|---|---|
| Carbon | 4,000 | 3,500 | 3,800 |
| Health | 88 | 51 | 79 |
| Confidence | 91% | 89% | 92% |
| Permanence | 93% | 61% | 84% |

Satellite module for the demo doesn't need a full pipeline: select project → load historical imagery → compute vegetation index → detect change → push the event to the MRV/blockchain layer.

---

## 7. Living Carbon Credit — state machine (merged; doc 2's states are the cleaner set)

```
PROPOSED → VERIFIED → UNDER_REVIEW → FROZEN → REVERIFIED or REVOKED
                                          │
                                          └── (deadline passes, no reverification) → EXPIRED
```

| Status | Mint | Transfer | Reverify | Revoke |
|---|---|---|---|---|
| Proposed | No | No | Yes | Yes |
| Verified | No | Yes | Yes | Yes |
| Under review | No | No | Yes | Yes |
| Frozen | No | No | Yes | Yes |
| Reverified | No | Yes | Yes | Yes |
| Expired | No | No | Yes | Yes |
| Revoked | No | No | No | No |

Each credit carries: Credit ID, Project ID, quantity, creation date, confidence, permanence, health at issuance, evidence hash(es), owner, review deadline, current status.

**Proof-of-Permanence:** never put raw sensor/imagery data on-chain. Flow is raw data → database/IPFS → hash → anchor hash on-chain per monitoring cycle. The chain proves the *record* wasn't silently altered, not that the carbon itself is real — be upfront about this distinction with judges (see §12).

---

## 8. Database Schema (doc 2 — keep, it's the more complete design)

| Table | Key fields |
|---|---|
| `plots` | id, name, lat, lng, area_ha, ecosystem_type, baseline_ndvi, baseline_carbon, health_status |
| `observations` | id, plot_id, timestamp, ndvi, salinity, soil_moisture, temperature, source, quality_score |
| `credits` | id, plot_id, token_id, quantity, lower_bound_quantity, status, last_verified_at, next_review_at, metadata_uri |
| `anomalies` | id, plot_id, type, severity, description, evidence_hash, status, created_at |
| `community_reports` | id, plot_id, submitter, lat, lng, photo_uri, photo_hash, description, vote, created_at |

**Core API endpoints:**
```
POST /api/plots                    GET  /api/plots/:id
GET  /api/plots/:id/observations   POST /api/observations
GET  /api/plots/:id/anomalies      POST /api/community-reports
POST /api/ai/estimate              POST /api/ai/detect-anomaly
POST /api/oracle/process           POST /api/credits/mint
POST /api/credits/:id/reverify
```

**Inter-module contracts (doc 1's naming, useful for keeping six people decoupled):**
```
M1 (AI)        → M5 (Backend):  POST /predict-carbon, /detect-anomaly, /estimate-uncertainty
M2 (Twin/GIS)  → M5 (Backend):  POST /satellite-observation, GET /vegetation-change/{project}
M3 (IoT)       → M5 (Backend):  MQTT → POST /sensor-data
M6 (Frontend)  → M5 (Backend):  REST calls
M5 (Backend)   → M4 (Chain):    MRV verification event → blockchain tx
M4 (Chain)     → M5/M6:         credit state, tx hash, freeze/reverify events
```

---

## 9. Team Structure — Six People, Six Owned Subsystems

Both docs agree on six people; doc 1's framing of the *reasoning* is better ("don't split frontend/backend/blockchain/AI generically — that creates integration seams; give each person one complete, independently demoable subsystem") so that's kept as the operating principle, with doc 2's more precise task lists filled in underneath.

| # | Role | Owns | Concrete Day-3 deliverable |
|---|---|---|---|
| **M1** | AI/ML Lead | Carbon estimator, anomaly detector, uncertainty model | Working `/api/ai/*` service returning the JSON contract in §5 |
| **M2** | Digital Twin + GIS Lead | Digital Carbon Twin state, satellite/NDVI change detection | Functional map + twin dashboard showing temporal state (§6 table) |
| **M3** | IoT/Edge Lead | ESP32 sensors, MQTT, simulator, Sensor Trust Score | End-to-end sensor → backend data bridge |
| **M4** | Blockchain Lead | ERC-1155 Living Credit contract, state machine, freeze/reverify, deploy | Deployed contract on Polygon Amoy/Hardhat with visible state transitions + tx hashes |
| **M5** | Backend/MRV Lead | Database, FastAPI, MRV confidence fusion, IPFS, oracle bridge | Integration backbone — every other module plugs into this person |
| **M6** | Frontend + Community Lead | Admin/owner/buyer/community dashboards, evidence form | All four dashboards wired to live backend data |

*(Doc 2's alternative — a dedicated "Research/pitch lead" as a 6th slot instead of merging that into M6 — is worth considering if your team has 7 people; with exactly six, folding pitch/README duties into M6 alongside community, as done here, keeps every seat technical.)*

**What each person should say to judges (doc 1 — good, concise, keep as-is):**
- **M1:** "Our AI doesn't only estimate carbon — it detects inconsistencies between reported, observed, and predicted ecosystem states and quantifies uncertainty."
- **M2:** "Every project has a living Digital Carbon Twin that maintains its spatial and temporal carbon state."
- **M3:** "Our IoT layer provides ground truth from the physical ecosystem rather than relying solely on reported data."
- **M4:** "Our carbon credits are living assets — they move between active, at-risk, frozen, reverified, and revoked states."
- **M5:** "Our MRV engine fuses independent evidence sources into a measurable confidence score."
- **M6:** "Local communities become active verification participants, not passive beneficiaries."

---

## 10. Execution Plan — 3 Days (doc 2's schedule; more realistic for a hackathon than doc 1's looser "Phase 1/2/3/4")

**Day 1 — Foundation**
- Lock the problem statement, demo story, and one plot ID (e.g. `MNG-001`).
- Freeze MVP scope; create the repo; assign the six roles.
- M4: scaffold contract — credit struct, status enum, minting, event logs.
- M5: database schema + FastAPI skeleton + sensor simulator.
- M1: prepare synthetic NDVI/sensor time series.
- M6: dashboard wireframes.
- **Milestone:** backend boots, one plot renders, one sensor reading can be submitted, contract deploys locally, one prototype credit batch mints.

**Day 2 — Core integration**
- M4: implement freeze, review, reverification, expiry, transfer restriction.
- M1: carbon estimate + uncertainty + lower-bound + anomaly detection live.
- M5: wire simulator → AI service → contract caller (oracle).
- M6: map, health metrics, charts, credit status, event panel.
- Community form: geotagged evidence upload + hashing.
- **Midday checkpoint:** demonstrate observation → AI result → oracle → contract event → dashboard status, end to end, even roughly.

**Day 3 — Demo and presentation**
- Implement reverification + community confirmation flow.
- Add demo reset button, loading states, error handling.
- Run the full anomaly scenario (§11) start to finish, multiple times.
- Capture real transaction hashes and screenshots as backup.
- Build architecture diagram, pitch deck, README, judge-question prep (§12).
- Record a backup demo video — **do this even if the live demo works.**

---

## 11. Demo Script — the "killer feature" (doc 1's cinematic structure + doc 2's concrete numbers)

**Scene 1 — Healthy project.** `MNG-001`, 10 ha mangrove plot registered. Baseline NDVI 0.68 → healthy NDVI 0.70. Estimated carbon increase 42 tCO₂e, uncertainty ±6, creditable lower bound ≈32.1 tCO₂e. Status: **VERIFIED**.

**Scene 2 — IoT monitoring.** Live sensor feed: pH 7.8, salinity 27 ppt, temperature 28.4°C, water level 1.2 m. Digital Twin updates in real time.

**Scene 3 — Community report.** A community user submits "mangrove clearing detected" with photo + GPS. AI image validation returns ~91% confidence.

**Scene 4 — Satellite confirmation.** NDVI falls to 0.47; anomaly severity scored 0.86–0.94. Vegetation change: roughly −18 to −19%.

**Scene 5 — Blockchain reacts (the wow moment).** Oracle hashes the evidence, calls the contract:
```solidity
if (degradation > threshold) {
    freezeCredit(plotId);
    createReverificationRequest();
}
```
Dashboard flips live: `10,000 credits ACTIVE → some AT-RISK → 2,000 FROZEN`. Show the transaction hash on screen.

**Scene 6 — Reverification.** New field/community evidence arrives. Split outcome for realism: e.g. 1,200 credits confirmed damaged → **REVOKED**; 800 credits found to be a false alarm → **ACTIVE** again.

This single script demonstrates IoT + Digital Twin + AI + satellite + community + uncertainty + blockchain + living credits + automated freeze in about two minutes — don't cut it short for a longer feature tour.

---

## 12. Anticipated Judge Questions (doc 2 — keep verbatim logic, this is well-reasoned)

- **"Why blockchain instead of a normal database?"** → Shared auditability, credit ownership, status transitions, and double-counting control across independent parties. Raw images/sensor streams stay off-chain; only hashes and key events go on-chain.
- **"Can blockchain prove the carbon is real?"** → No. It records submitted evidence and state transitions. Independent validation, calibration, and governance are still required — say this proactively, don't wait to be caught on it.
- **"Why is the credit 'living'?"** → Its validity is tied to the plot's ongoing monitoring status; new evidence can freeze, reduce, reverify, or revoke it.
- **"What happens to a credit that's already been sold?"** → Prototype blocks further transfer and logs a freeze/reversal event. Production would need retired-credit rules, buyer notification, buffer pools, and compensation — flag this as future work, not a gap you missed.
- **"How do you handle false satellite alarms?"** → Require multiple observations, data-quality checks, persistence over time, sensor corroboration, and human/community verification before acting.
- **"Why NDVI?"** → Accessible prototype vegetation signal; not sufficient alone for certified accounting — real deployment needs field biomass and sediment-carbon sampling.

---

## 13. Scope Boundaries — what NOT to build (both docs agree; consolidated)

**Skip entirely for the hackathon:**
- A full carbon marketplace or sophisticated token economics
- A custom blockchain (use an existing testnet)
- A complete mobile app (responsive web is enough)
- Dozens of physical IoT sensors (2–4 real + simulate the rest)
- Training large/deep ML models (regression + rule-based anomaly detection is enough, and more defensible)
- Full international registry integration or government-grade identity
- 3D visualization (a clean 2D map + charts beats an unfinished 3D view)

**Spend your time instead on:** the Digital Twin, the Living Credit state machine, AI anomaly + uncertainty, the satellite-triggered freeze, and multi-source MRV fusion. These five things are what make this different from every other "carbon token" hackathon project — a small system that works end to end beats a large architecture with disconnected modules.

---

## 14. Repository Structure

```
blue-carbon/
├── frontend/        (dashboard/, admin/, community/, buyer/)
├── backend/         (api/, models/, services/, mrv/, database/)
├── ai/              (carbon_model/, anomaly_detection/, uncertainty/)
├── digital-twin/    (gis/, satellite/, temporal/)
├── iot/             (esp32/, mqtt/, simulator/)
├── blockchain/      (contracts/, scripts/, tests/)
├── community/       (reports/, verification/)
└── docs/
```

---

## 15. Deliverables Checklist

- [ ] Smart contract deployed (local Hardhat or Polygon Amoy)
- [ ] Credit minting, status machine, freeze, reverification
- [ ] Review deadline + transfer restriction enforced
- [ ] Sensor simulator + backend ingestion API
- [ ] Carbon estimation with confidence interval
- [ ] Anomaly detection service + oracle bridge
- [ ] Digital Carbon Twin dashboard (temporal state)
- [ ] Sensor Trust Score displayed somewhere in the UI
- [ ] Community evidence form + hash anchoring
- [ ] Architecture + state-machine diagrams for the deck
- [ ] README, pitch deck, demo script, judge Q&A prep
- [ ] Backup demo video recorded

---

## 16. Naming

Recommend **TIDE — Trusted Intelligent Digital Ecosystem Registry** (doc 1's suggestion, and the strongest of the three offered: it reads naturally, has a clean acronym, and ties thematically to the coastal/tidal domain). Alternatives if the team prefers: **BlueTwin** (leans on the Digital Twin feature) or **CarbonPulse** (leans on "continuous" monitoring).
