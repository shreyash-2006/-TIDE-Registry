# AI/ML Work Plan — Blue Carbon MRV System
### For M1 (AI/ML Lead) — TIDE / Blue Carbon Registry Hackathon

This is the detailed, step-by-step version of the AI layer: exact setup, data sources, model logic, code skeletons, API contract, integration points, and an hour-by-hour schedule. Follow it top to bottom.

---

## 0. What you're actually shipping

By end of Day 3, one running service (`/ai`) exposing three capabilities behind a REST API:

| Capability | Input | Output |
|---|---|---|
| Carbon estimation | NDVI/EVI + plot metadata | estimated carbon, uncertainty, conservative creditable amount |
| Anomaly detection | current + historical observations (satellite, IoT) | anomaly flag, severity score, reason |
| Confidence fusion | outputs of the above + IoT/community/satellite reliability | a single MRV confidence score (0–100) that M5's backend uses to decide mint / freeze |

Everything else (dashboards, blockchain, IoT hardware) consumes what you produce. Your job is to make the API contract stable **on Day 1** so the other five people aren't blocked waiting on you.

---

## 1. Environment setup (do this first, today, before writing any model code)

```bash
# Python env
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pydantic numpy pandas scikit-learn matplotlib \
            earthengine-api geemap rasterio geopandas requests python-multipart
```

- **Register for Google Earth Engine access** (non-commercial account) — do this in the first hour. Approval is sometimes near-instant, sometimes takes a few hours. If it's not approved by end of Day 1, fall back to the Copernicus Data Space Ecosystem browser download instead (manual but doesn't need approval).
- **Pick your demo plot now.** One real mangrove site with known coordinates. Good options: Sundarbans (India/Bangladesh border), Bhitarkanika (Odisha), or Pichavaram (Tamil Nadu). Smaller, well-documented sites are easier to pull clean imagery for. Lock this decision with M2 (Digital Twin/GIS) — you're both using the same plot and the same NDVI numbers.
- Assign the plot an ID now: e.g. `MNG-001`. Put it in a shared config file everyone imports.

---

## 2. Data acquisition

### 2a. Satellite / NDVI (real data)

Use Google Earth Engine's Python API to pull Sentinel-2 surface reflectance for your plot's bounding box over the last 12–24 months.

```python
import ee
ee.Authenticate()
ee.Initialize(project='your-gee-project')

plot = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])

collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(plot)
              .filterDate('2024-08-01', '2026-08-01')
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))

def add_ndvi(img):
    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return img.addBands(ndvi)

with_ndvi = collection.map(add_ndvi)

# Extract mean NDVI per image as a time series
def get_mean_ndvi(img):
    mean = img.select('NDVI').reduceRegion(
        reducer=ee.Reducer.mean(), geometry=plot, scale=10)
    return img.set('mean_ndvi', mean.get('NDVI')).set(
        'date', img.date().format('YYYY-MM-dd'))

ts = with_ndvi.map(get_mean_ndvi)
ts_list = ts.aggregate_array('date').getInfo()
ndvi_list = ts.aggregate_array('mean_ndvi').getInfo()
```

Save this as a CSV (`data/ndvi_timeseries.csv`) — this is your real, defensible NDVI trend. You'll reuse the same query pattern for EVI (swap the band formula).

**Fallback if GEE access is delayed:** download a couple of Sentinel-2 scenes manually from the Copernicus Data Space browser for your plot, compute NDVI in Python with `rasterio`, and don't worry about a long time series — 2–3 dates (before/after a known event) is enough for the demo.

### 2b. Biomass calibration data (real data)

Use the NASA/Simard et al. **Global Mangrove Distribution, Aboveground Biomass, and Canopy Height** dataset (30 m resolution, available via NASA's data portal / ORNL DAAC). Download the raster tile covering your plot region.

```python
import rasterio
import numpy as np

with rasterio.open('data/mangrove_agb_tile.tif') as src:
    agb = src.read(1)
    transform = src.transform

# Sample AGB at a grid of points inside your plot polygon
# Pair each point with the NDVI value from the same location/date-nearest Sentinel scene
```

Build a small paired dataset: `(ndvi_value, agb_t_per_ha)` for ~50–200 sample points across your region (doesn't have to be exactly your plot — nearby mangrove areas of similar type are fine, just say so). This is what you fit the calibration regression on.

**Fallback if raster download/processing eats too much time:** use published NDVI–biomass regression coefficients from mangrove literature (cite the source) instead of fitting your own. Less impressive but still defensible — just be upfront that "for the hackathon we used literature-calibrated coefficients rather than re-fitting on raw NASA raster data."

### 2c. IoT sensor data (synthetic — build your own simulator)

This is the one dataset that *should* be synthetic — no real dataset exists for this, and you control the anomaly timing for the demo.

```python
import numpy as np
import time

NORMAL_RANGES = {
    'salinity':      (10, 18),   # ppt
    'temperature':   (26, 30),   # °C
    'ph':            (7.4, 8.1),
    'soil_moisture': (55, 75),   # %
    'water_level':   (0.8, 1.5), # m
}

def generate_reading(anomaly=False):
    reading = {}
    for key, (low, high) in NORMAL_RANGES.items():
        val = np.random.uniform(low, high)
        if anomaly and key in ('salinity', 'soil_moisture'):
            val = val * np.random.choice([0.5, 1.8])  # push out of range
        reading[key] = round(val, 2)
    reading['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ')
    return reading
```

Generate a normal-mode dataset (a few hundred readings) to train the statistical anomaly model on, and keep the `anomaly=True` switch as a manual trigger you and M3 use live during the demo.

### 2d. Community photo validation (stub, don't over-invest)

Skip training a classifier. Either:
- Hardcode a confidence score returned by the endpoint with a comment marking it as a stub, or
- Make a single API call to an existing multimodal model with a fixed prompt ("does this image show signs of vegetation clearing or dieback? respond with a confidence 0–1") if you have spare time on Day 3.

---

## 3. Model 1 — Carbon Estimator

**Step 1 — Fit the calibration regression:**

```python
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import numpy as np

X = ndvi_samples.reshape(-1, 1)
y = agb_samples

poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X)

model = LinearRegression().fit(X_poly, y)
preds = model.predict(X_poly)
rmse = np.sqrt(mean_squared_error(y, preds))   # <- becomes your sigma later

import joblib
joblib.dump({'model': model, 'poly': poly, 'rmse': rmse}, 'models/carbon_model.pkl')
```

**Step 2 — Convert biomass to carbon to CO2e:**

```python
CARBON_FRACTION = 0.47   # cite literature (typical mangrove biomass carbon fraction, ~0.45-0.50)
CO2_CONVERSION = 44 / 12

def estimate_carbon(ndvi, area_ha):
    X_poly = poly.transform([[ndvi]])
    biomass_t_per_ha = model.predict(X_poly)[0]
    biomass_total = biomass_t_per_ha * area_ha
    carbon_total = biomass_total * CARBON_FRACTION
    co2e_total = carbon_total * CO2_CONVERSION
    return co2e_total, rmse * area_ha * CARBON_FRACTION * CO2_CONVERSION  # scaled sigma
```

**Step 3 — Sanity-check against real numbers.** Before you trust this, run it on your actual plot's current NDVI and eyeball whether the output tonnage is plausible for the plot's area (mangrove AGB carbon is typically in the range of tens to a few hundred t/ha — if your output is wildly outside that, check units and the polynomial fit for overfitting on too few points).

---

## 4. Model 2 — Anomaly Detector

**Layer A — rule-based (primary, use this for the live demo):**

```python
def rule_based_anomaly(current, previous, expected_range):
    flags = []
    ndvi_drop = (previous['ndvi'] - current['ndvi']) / previous['ndvi']
    if ndvi_drop > 0.20:
        flags.append(f"NDVI dropped {ndvi_drop:.1%}")

    if not (expected_range['salinity'][0] <= current['salinity'] <= expected_range['salinity'][1]):
        flags.append(f"Salinity out of expected range: {current['salinity']}")

    reported_biomass = current.get('reported_biomass')
    if reported_biomass:
        expected = current.get('model_biomass_estimate')
        deviation = abs(reported_biomass - expected) / expected
        if deviation > 0.20:
            flags.append(f"Reported vs modeled biomass deviates {deviation:.1%}")

    severity = min(1.0, len(flags) * 0.3 + (ndvi_drop if ndvi_drop > 0 else 0))
    return {'anomaly': len(flags) > 0, 'severity': round(severity, 2), 'reasons': flags}
```

**Layer B — statistical, multivariate (secondary signal, nice-to-have):**

```python
from sklearn.ensemble import IsolationForest

iso = IsolationForest(contamination=0.05, random_state=42)
iso.fit(normal_sensor_df[['salinity', 'temperature', 'ph', 'soil_moisture', 'water_level']])

def statistical_anomaly_score(reading):
    X = [[reading['salinity'], reading['temperature'], reading['ph'],
          reading['soil_moisture'], reading['water_level']]]
    return round(float(-iso.decision_function(X)[0]), 3)  # higher = more anomalous
```

Combine: `final_anomaly_score = 0.7 * rule_based_severity + 0.3 * normalized_statistical_score`. Use the rule-based trigger to decide the binary "anomaly: true/false" the demo needs to be reliable; use the blended score for the confidence fusion M5 consumes.

---

## 5. Model 3 — Uncertainty & Conservative Crediting

Not a trained model — this is the formula that makes your crediting defensible.

```python
def creditable_carbon(estimate, sigma, confidence_z=1.645):  # ~90% one-sided
    lower_bound = estimate - confidence_z * sigma
    return max(0.0, round(lower_bound, 1))
```

Where `sigma` comes from the calibration RMSE in §3 (or a literature-cited value if you used the fallback). This is the single most "we did our homework" number in the whole system — when a judge asks about over-crediting, this formula is your answer.

---

## 6. MRV Confidence Score (the fusion layer)

This is what feeds the mint/freeze decision. Combine independent signals into one score:

```python
def mrv_confidence(iot_consistency, satellite_evidence, ai_confidence,
                    community_evidence, historical_consistency):
    weights = {
        'iot': 0.20, 'satellite': 0.25, 'ai': 0.25,
        'community': 0.15, 'historical': 0.15
    }
    score = (iot_consistency * weights['iot'] +
             satellite_evidence * weights['satellite'] +
             ai_confidence * weights['ai'] +
             community_evidence * weights['community'] +
             historical_consistency * weights['historical'])
    return round(score, 1)
```

Each input (0–100) can start as a simple heuristic — e.g. `iot_consistency = 100 - sensor_trust_penalty`, `satellite_evidence = 100 - ndvi_anomaly_severity*100`. You don't need this to be sophisticated; you need it to be **explainable** — each number should trace back to something concrete you can point at on screen.

---

## 7. The API layer (what M5 and everyone else actually calls)

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class EstimateRequest(BaseModel):
    plot_id: str
    ndvi: float
    area_ha: float

class EstimateResponse(BaseModel):
    plot_id: str
    carbon_estimate: float
    standard_deviation: float
    creditable_carbon: float
    confidence_level: float = 0.90

@app.post("/api/ai/estimate", response_model=EstimateResponse)
def estimate(req: EstimateRequest):
    co2e, sigma = estimate_carbon(req.ndvi, req.area_ha)
    lower = creditable_carbon(co2e, sigma)
    return EstimateResponse(
        plot_id=req.plot_id, carbon_estimate=round(co2e, 1),
        standard_deviation=round(sigma, 1), creditable_carbon=lower
    )

class AnomalyRequest(BaseModel):
    plot_id: str
    current: dict
    previous: dict
    expected_range: dict

@app.post("/api/ai/detect-anomaly")
def detect_anomaly(req: AnomalyRequest):
    result = rule_based_anomaly(req.current, req.previous, req.expected_range)
    result['statistical_score'] = statistical_anomaly_score(req.current)
    return result

class ConfidenceRequest(BaseModel):
    iot_consistency: float
    satellite_evidence: float
    ai_confidence: float
    community_evidence: float
    historical_consistency: float

@app.post("/api/ai/mrv-confidence")
def mrv_confidence_endpoint(req: ConfidenceRequest):
    score = mrv_confidence(**req.dict())
    return {"mrv_confidence": score, "eligible": score >= 85}
```

Publish this contract to the team (paste it in your shared channel) **by end of Day 1** — M5's backend and M4's oracle both build against it, so if it changes on Day 2 it breaks two other people's work.

---

## 8. Testing & validation checklist

- [ ] Run `estimate_carbon` on your real plot's actual current NDVI — output is a plausible tonnage for the area.
- [ ] Run `rule_based_anomaly` with a hand-crafted "healthy" reading and a hand-crafted "degraded" reading — confirm it flags the right one and doesn't flag the healthy one.
- [ ] Confirm `IsolationForest` doesn't flag normal simulator output as anomalous (check false-positive rate isn't absurd — if it is, your `contamination` parameter or training data range is off).
- [ ] Confirm `creditable_carbon` is always less than `carbon_estimate` and never negative.
- [ ] Load-test nothing — this is a hackathon demo, not production; just make sure the three endpoints respond in well under a second so the live demo doesn't stall.

---

## 9. Integration checkpoints with the rest of the team

| When | With whom | What |
|---|---|---|
| End of Day 1 | M5 | Confirm final JSON schema for all three endpoints |
| End of Day 1 | M2 | Agree on the plot ID, coordinates, and NDVI source so Digital Twin and AI use identical numbers |
| Mid Day 2 | M3 | Confirm IoT payload field names match what `rule_based_anomaly` expects |
| Mid Day 2 | M5 | First end-to-end test: simulator → your anomaly endpoint → oracle |
| Day 3 morning | M4 + M5 | Rehearse the exact anomaly severity value that should trigger the freeze threshold in the smart contract, so Scene 4/5 of the demo fires reliably every rehearsal |

---

## 10. Hour-by-hour schedule (M1 specifically)

**Day 1**
- Hr 0–1: Env setup, GEE registration, lock plot ID/coordinates with M2
- Hr 1–3: Pull NDVI time series via GEE
- Hr 3–5: Download/sample NASA AGB raster, build paired NDVI–AGB dataset
- Hr 5–6: Fit calibration regression, save model + sigma
- Hr 6–7: Build IoT simulator (normal + anomaly mode), hand off to M3
- Hr 7–8: Publish API contract to the team

**Day 2**
- Hr 0–2: Build `/api/ai/estimate` endpoint, test against real values
- Hr 2–4: Build rule-based anomaly detector + endpoint
- Hr 4–5: Build Isolation Forest secondary signal
- Hr 5–6: Build MRV confidence fusion endpoint
- Hr 6–8: Integration test with M5's backend, fix schema mismatches

**Day 3**
- Hr 0–2: Tune anomaly thresholds so the demo scenario fires cleanly and repeatably
- Hr 2–4: Full run-through with M4/M5/M6, fix timing/threshold issues
- Hr 4–6: Prep the "how did you calibrate this" answer, write it down word for word
- Hr 6–8: Buffer for whatever broke; help other members if you're done early

---

## 11. Suggested `ai/` folder structure

```
ai/
├── data/
│   ├── ndvi_timeseries.csv
│   ├── ndvi_agb_samples.csv
│   └── mangrove_agb_tile.tif
├── models/
│   └── carbon_model.pkl
├── carbon_model.py       # fitting + estimate_carbon()
├── anomaly_model.py       # rule_based_anomaly() + IsolationForest
├── uncertainty.py         # creditable_carbon()
├── mrv_confidence.py      # fusion logic
├── simulator.py           # IoT reading generator
├── api.py                 # FastAPI app, all endpoints
└── requirements.txt
```

---

## 12. If something goes wrong (fallback plan)

- **GEE access never comes through:** manually download 2–3 Sentinel-2 scenes from Copernicus Data Space Browser, compute NDVI with rasterio, don't attempt a full time series.
- **NASA raster too fiddly to process in time:** use published NDVI–biomass coefficients from a mangrove biomass paper (cite it), skip the calibration fit, keep the same downstream API contract — nobody outside your module needs to know you skipped the fit, and you can honestly describe it as "literature-calibrated" to judges.
- **Isolation Forest not behaving:** drop it, ship rule-based only. It's the more explainable option anyway and is enough to carry the demo.
- **Running low on time overall:** prioritize in this order — API contract stability > rule-based anomaly detector > carbon estimator > uncertainty formula > statistical anomaly layer > community image validation. The first three are what the demo depends on; the last two are polish.
