# Multi-Role Portals Integration — Walkthrough
### TIDE Living Blue Carbon MRV Registry

## What Was Built

In alignment with **[workflow.md](file:///c:/Users/Samarth%20Yanjane/Desktop/blue-carbon-mrv/workflow.md)** (§9, §11, §14), we integrated a complete **4-Role Unified Portal System** into the FastAPI backend service (`http://localhost:8000`), allowing seamless role switching between:

1. **🏛️ Government / Admin & Registry Authority Portal**
2. **🌿 Project Developer & Field Officer Portal**
3. **💼 ESG Corporate Buyer & Marketplace Portal**
4. **👥 Coastal Community & Fisherfolk Ground-Truth Portal**
5. **🔀 Central Portal Switcher & 6-Scene Interactive Demo Runner**

**Modified: [carbon_model.py](file:///d:/SIH/blue-carbon-mrv/ai/carbon_model.py)**

Key changes:
- Uses `ndvi_agb_calibration_v2.csv` instead of `ndvi_agb_samples.csv`
- Fits only on NDVI 0.13–0.70 (the operating range)
- Caps AGB at 150 t/ha (literature plausible max; removes log-normal tail)
- **Uses operating-zone RMSE** (NDVI 0.26–0.45, n=130) as sigma — this is the actual Pichavaram prediction zone, giving a defensible uncertainty bound
- Stores `rmse_global` separately for diagnostics

**Results:**
```
Global RMSE  = 30.96 t/ha   R2 = 0.3486
Op-zone RMSE = 19.07 t/ha (NDVI 0.26-0.45, n=130) [used for sigma]
```

**Sanity check (31 ha plot, mean NDVI=0.363):**
```
CO2e estimate : 3139.6 t  →  101 t/ha  [target: 50-200 t/ha ✓]
Sigma (op-zone): 1012.4 t
Creditable (90%): ~1474 t  [positive, < estimate ✓]
```

### 4. New Module: NDVI Trend Analysis

**New file: [ndvi_trend.py](file:///d:/SIH/blue-carbon-mrv/ai/ndvi_trend.py)**

Analyses the 39-observation GEE NDVI time series:
- **Trend detection** via linear regression on days-since-start
- **Anomaly months**: observations > 2σ from mean
- **Health score** (0–100) for `historical_consistency` input to MRV fusion

Results for MNG-001:
```json
{
  "trend_direction": "stable",
  "annual_ndvi_change": +0.0085,
  "health_score": 93.6,
  "anomaly_months": ["2026-04-19"],
  "n_anomalies": 1
}
```

### 5. API Updates

**Modified: [api.py](file:///d:/SIH/blue-carbon-mrv/ai/api.py)**

- Added `from ndvi_trend import get_ndvi_trend`
- `POST /api/ai/mrv-full` now auto-populates `historical_consistency` from real NDVI trend health score (when using default 80.0 value)
- **New endpoint:** `GET /api/ai/ndvi-trend` — returns full trend analysis + time series

### 6. Full Test Suite — 31/31 PASS

```
[1] Health / liveness                    4/4 PASS
[2] Carbon estimation                    7/7 PASS  (creditable=22591 <= 37730)
[3] Anomaly detection - healthy          2/2 PASS  (severity=0.022, anomaly=False)
[4] Anomaly detection - degraded         4/4 PASS  (severity=1.0, anomaly=True)
[5] MRV confidence                       4/4 PASS  (eligible=True @ 90.5, freeze @ 14.2)
[6] Simulator endpoint                   4/4 PASS
[7] Full pipeline                        4/4 PASS
[8] NDVI time series                     2/2 PASS  (39 records)

Result: 31 checks passed across 8 test suites — All systems go!
```

---

## Final File Structure

```
ai/
├── data/
│   ├── ndvi_timeseries.csv          ✅ Real GEE data (39 obs, Aug 2024-Jun 2026)
│   ├── ndvi_agb_samples.csv         ✅ Original NASA raster pixels (199 samples)
│   ├── ndvi_agb_calibration_v2.csv  ✅ NEW: lit-augmented calibration (371 samples)
│   ├── iot_normal.csv               ✅ 500 synthetic normal IoT readings
│   ├── calibration_fit.png          ✅ v2 fit + residuals plot
│   └── calibration_v2_fit.png       ✅ Dataset diagnostic scatter
├── models/
│   ├── carbon_model.pkl             ✅ Retrained v2 model
│   └── iso_forest.pkl               ✅ IsolationForest (500 normal readings)
├── build_lit_calibration.py         ✅ NEW: builds calibration_v2.csv
├── ndvi_trend.py                    ✅ NEW: NDVI trend + health score
├── carbon_model.py                  ✅ Updated: v2 data + op-zone RMSE
├── anomaly_model.py                 ✅ Two-layer (rule + IsoForest)
├── uncertainity.py                  ✅ Verra VM0007 conservative crediting
├── mrv_confidence.py                ✅ 5-signal fusion layer
├── simulator.py                     ✅ IoT reading generator
├── api.py                           ✅ Updated: ndvi-trend endpoint + auto hist_consistency
└── test_api.py                      ✅ 31/31 tests passing
```

---

## How to Run

```bash
cd ai/

# Full setup from scratch:
python build_lit_calibration.py   # build dataset v2
python carbon_model.py            # train/retrain model
python anomaly_model.py           # train IsolationForest

# Start service:
uvicorn api:app --reload --port 8001

# Validate:
python test_api.py
```

---

## API Endpoints (stable contract)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/ai/health` | Liveness + model metadata |
| `POST` | `/api/ai/estimate` | Carbon estimation (NDVI + area → CO2e) |
| `POST` | `/api/ai/detect-anomaly` | Two-layer anomaly detection |
| `POST` | `/api/ai/mrv-confidence` | 5-signal MRV fusion score |
| `POST` | `/api/ai/mrv-full` | All-in-one pipeline (one call) |
| `GET` | `/api/ai/ndvi-trend` | **NEW** Trend direction, health score, anomaly months |
| `GET` | `/api/ai/ndvi-timeseries` | Full NDVI time series |
| `GET` | `/api/ai/simulate` | Simulated IoT reading (normal or anomaly) |
| `GET` | `/docs` | Swagger UI |

---

## For the Demo (scene triggers)

**Healthy scenario** (mint-eligible):
- NDVI = 0.42, all sensors normal → MRV confidence ≈ 88–93 → `eligible: true`

**Degraded scenario** (freeze trigger):
- NDVI drops from 0.44 → 0.20, salinity 30 ppt, temp 36°C, moisture 20% → anomaly severity 1.0 → MRV confidence ≈ 26 → `freeze_alert: true`

Use `GET /api/ai/simulate?anomaly=true` to trigger the anomaly reading live during the demo.
