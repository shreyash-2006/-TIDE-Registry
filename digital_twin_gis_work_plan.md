# Digital Twin + GIS Work Plan — Blue Carbon MRV System
### For M2 (Digital Twin + GIS Lead) — TIDE / Blue Carbon Registry Hackathon

Same format as the AI/ML plan: exact setup, data sources, build logic, code skeletons, API contract, integration points, and an hour-by-hour schedule. This is your most visually impressive module — judges will remember whichever screen is on-stage the longest, and that's usually this one.

**Shared constants — lock these with M1 before you start:**
```
plot_id = "PCV-001"
site    = "Pichavaram Mangrove Forest, Tamil Nadu"
bbox    = [79.760, 11.400, 79.810, 11.450]   # [lon_min, lat_min, lon_max, lat_max]
```

---

## 0. What you're actually shipping

By end of Day 3, one running service (`/twin`) plus a map-based frontend view that together do three things:

| Capability | Input | Output |
|---|---|---|
| Digital Carbon Twin state | latest AI estimate, IoT summary, satellite change, community reports | a single structured "current state" object per plot, with full history |
| Satellite change detection | Sentinel-2 imagery over time | NDVI/EVI trend, % vegetation change between two dates, a "significant degradation" flag |
| Map visualization | plot boundary + twin state | an interactive map + timeline showing how the plot's health has evolved |

Everyone else's outputs *flow into* the Twin (that's the point of it — it's the fused living record). Your job is to define the Twin's data schema early, because M5's database and M6's frontend both build against it.

---

## 1. Environment setup

```bash
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pydantic numpy pandas geopandas rasterio shapely \
            earthengine-api geemap folium requests
```

- You'll share GEE access with M1 — no need to register separately, just get added to the same GEE project, or register your own account against the same project ID so quota is shared cleanly.
- Get the **plot boundary as an actual polygon**, not just a bounding box. Options, in order of preference:
  1. Trace it yourself in [geojson.io](http://geojson.io) using recent satellite basemap imagery — 15 minutes, gives you a real polygon instead of a rectangle, and rectangles look sloppy on a map next to a real coastline.
  2. Pull a mangrove extent polygon for your bbox from **Global Mangrove Watch (GMW v4.1)** and clip it to your area of interest.
  3. Fallback: use the rectangle from the AI plan if you're short on time — functionally fine, just less polished visually.
- Save the polygon as `data/pichavaram_boundary.geojson`. This is the single most-reused file in your module — the map, the twin state, and the satellite clipping all reference it.

---

## 2. Data sources

### 2a. Plot boundary + historical extent (real data)

**Global Mangrove Watch (GMW v4.1)** gives real mangrove extent polygons for multiple years (1996 → 2020, roughly every 3–5 years, plus continuing updates). Download the tiles covering Pichavaram.

```python
import geopandas as gpd

gmw_2000 = gpd.read_file('data/gmw_v3_2000_vec.shp')
gmw_2020 = gpd.read_file('data/gmw_v3_2020_vec.shp')

pichavaram_bbox = gpd.GeoSeries.from_wkt(
    ['POLYGON((79.760 11.400, 79.810 11.400, 79.810 11.450, 79.760 11.450, 79.760 11.400))']
)
extent_2000 = gpd.clip(gmw_2000, pichavaram_bbox)
extent_2020 = gpd.clip(gmw_2020, pichavaram_bbox)

area_2000_ha = extent_2000.to_crs(epsg=32644).area.sum() / 10_000  # UTM zone 44N for TN
area_2020_ha = extent_2020.to_crs(epsg=32644).area.sum() / 10_000
```

This gives you a **real extent-loss/gain number over two decades** — a genuinely strong number to put on the Twin's history panel, independent of anything M1 computes from NDVI.

### 2b. Current + historical satellite imagery (real data — shared source with M1, different use)

M1 pulls NDVI *values* for calibration and current estimation. You pull imagery for **visual change detection and the Twin's timeline** — same Sentinel-2 collection, different purpose, so coordinate to avoid duplicate GEE calls hitting quota.

```python
import ee
ee.Initialize(project='your-gee-project')

plot = ee.Geometry.Rectangle([79.760, 11.400, 79.810, 11.450])

def get_composite(start, end):
    coll = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(plot)
            .filterDate(start, end)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .median())
    ndvi = coll.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return coll.addBands(ndvi)

before = get_composite('2025-06-01', '2025-08-31')
after  = get_composite('2026-06-01', '2026-08-31')
```

Export both composites as PNG thumbnails (true-color + NDVI-colored) for the Twin's before/after view:

```python
url = before.getThumbURL({
    'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000,
    'region': plot, 'dimensions': 800
})
```

Save these thumbnails locally — they're what actually renders on the map/dashboard, and you don't want to be live-fetching from GEE during the demo (latency + quota risk).

### 2c. Change detection number

```python
ndvi_before = before.select('NDVI').reduceRegion(
    reducer=ee.Reducer.mean(), geometry=plot, scale=10).get('NDVI').getInfo()
ndvi_after = after.select('NDVI').reduceRegion(
    reducer=ee.Reducer.mean(), geometry=plot, scale=10).get('NDVI').getInfo()

pct_change = (ndvi_after - ndvi_before) / ndvi_before * 100
significant = abs(pct_change) > 15  # tune threshold with M1
```

This `pct_change` and `significant` flag is what you hand to M5's oracle to trigger the freeze — coordinate the threshold value with M1's anomaly detector so both modules agree on what counts as "significant" (you don't want the AI service and the Twin disagreeing on-stage about whether an event is an anomaly).

---

## 3. The Digital Twin data model

This is the core deliverable. One JSON object per plot, versioned over time — think of it as a time series of snapshots, not just a single current state.

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TwinSnapshot(BaseModel):
    plot_id: str
    timestamp: datetime
    location: dict          # {"lat": 11.42, "lon": 79.78}
    area_ha: float
    mangrove_density: Optional[float] = None    # from GMW / NDVI proxy
    carbon_stock: Optional[float] = None        # pulled from M1's /api/ai/estimate
    biomass: Optional[float] = None
    health_score: Optional[float] = None        # 0-100, composite (see §4)
    biodiversity_index: Optional[float] = None  # stub/simplified for hackathon
    water_quality: Optional[dict] = None        # from IoT summary (M3)
    soil_conditions: Optional[dict] = None       # from IoT summary (M3)
    restoration_age_years: Optional[float] = None
    carbon_confidence: Optional[float] = None   # from M1's confidence_level
    permanence_score: Optional[float] = None    # see §4
    ndvi: Optional[float] = None
    credit_status: Optional[str] = None         # from M4 (ACTIVE/AT-RISK/FROZEN/etc.)
    source_event: Optional[str] = None          # "routine_update" | "satellite_alert" | "community_report" | "reverification"
```

Every time something changes — a new satellite pass, a new IoT batch, a community report, a blockchain state change — you append a **new snapshot**, you don't overwrite the old one. The full list of snapshots *is* the Twin's history, and that history is what makes the "Day 1 → after cyclone → after restoration" narrative work on screen.

```python
twin_history: dict[str, list[TwinSnapshot]] = {}  # plot_id -> list of snapshots, in-memory for hackathon

def add_snapshot(snapshot: TwinSnapshot):
    twin_history.setdefault(snapshot.plot_id, []).append(snapshot)
```

(For the hackathon, an in-memory list per plot is genuinely fine — don't over-engineer this into a full time-series database. If M5 wants it persisted, hand them the same schema for a Postgres table and let them own storage; you own the logic that produces snapshots.)

---

## 4. Composite scores — health and permanence

These two numbers are what make the Twin feel intelligent rather than just a data dump. Keep them simple and explainable.

**Health score** — blend of vegetation condition, sensor normalcy, and absence of anomalies:

```python
def health_score(ndvi_current, ndvi_baseline, iot_anomaly_penalty, ai_anomaly_severity):
    ndvi_ratio = min(1.0, ndvi_current / ndvi_baseline)
    base = ndvi_ratio * 100
    penalty = iot_anomaly_penalty + (ai_anomaly_severity * 30)
    return max(0, round(base - penalty, 1))
```

**Permanence score** — how likely the current carbon stock is to persist, informed by recent volatility and credit status:

```python
def permanence_score(health_score, recent_volatility, credit_status):
    base = health_score
    penalty = recent_volatility * 20
    if credit_status in ('FROZEN', 'UNDER_REVIEW'):
        penalty += 15
    return max(0, round(base - penalty, 1))
```

`recent_volatility` can be as simple as the standard deviation of the last 3–5 health scores in the plot's history — a plot bouncing around a lot is less "permanent" than one holding steady, even at a lower absolute score. This is a good talking point for judges: "permanence isn't just current health, it's stability of that health over time."

---

## 5. Map visualization

Use **Folium** (Python, wraps Leaflet, easiest to get running fast) for a server-rendered map, or hand M6 raw GeoJSON + Leaflet.js if they want it embedded directly in the React frontend. Either works — decide with M6 on Day 1 based on their frontend stack.

```python
import folium

m = folium.Map(location=[11.42, 79.78], zoom_start=13, tiles='OpenStreetMap')

folium.GeoJson(
    'data/pichavaram_boundary.geojson',
    name='Plot Boundary',
    style_function=lambda x: {'color': 'green', 'weight': 2, 'fillOpacity': 0.1}
).add_to(m)

folium.raster_layers.ImageOverlay(
    image='data/ndvi_before_thumb.png',
    bounds=[[11.400, 79.760], [11.450, 79.810]],
    opacity=0.6,
    name='NDVI - Before'
).add_to(m)

folium.LayerControl().add_to(m)
m.save('twin_map.html')
```

**What the demo needs on this map, minimum:**
- Plot boundary outline
- A color-coded health indicator (green/yellow/red) that changes when you trigger the demo scenario
- A before/after NDVI toggle for Scene 4 of the demo script
- Popups showing current snapshot values when you click the plot

**If M6 wants this embedded in React instead of a standalone Folium page:** hand them the GeoJSON boundary file + the thumbnail PNGs + the snapshot JSON, and let them render it with Leaflet.js directly — don't try to force a Folium HTML export into a React app, it's a worse integration path than just sharing the underlying data.

---

## 6. The API layer

```python
from fastapi import FastAPI
from typing import List

app = FastAPI()

@app.get("/api/twin/{plot_id}/current")
def get_current_state(plot_id: str) -> TwinSnapshot:
    history = twin_history.get(plot_id, [])
    if not history:
        raise HTTPException(404, "No twin data for this plot")
    return history[-1]

@app.get("/api/twin/{plot_id}/history")
def get_history(plot_id: str) -> List[TwinSnapshot]:
    return twin_history.get(plot_id, [])

@app.post("/api/twin/{plot_id}/update")
def push_update(plot_id: str, snapshot: TwinSnapshot):
    add_snapshot(snapshot)
    return {"status": "recorded", "plot_id": plot_id, "snapshot_count": len(twin_history[plot_id])}

@app.get("/api/twin/{plot_id}/satellite-change")
def satellite_change(plot_id: str):
    return {
        "plot_id": plot_id,
        "ndvi_before": ndvi_before,
        "ndvi_after": ndvi_after,
        "pct_change": round(pct_change, 1),
        "significant_degradation": significant
    }
```

Publish this contract to the team by **end of Day 1**, same as M1. M5's backend calls `/update` every time it has fresh data (from IoT, AI, community, or blockchain), and calls `/current` + `/history` to feed the frontend and the oracle's freeze decision.

---

## 7. Testing & validation checklist

- [ ] Boundary polygon renders correctly on the map and roughly matches the real coastline (sanity-check visually against satellite basemap)
- [ ] `pct_change` calculation gives a sane, explainable number when you manually feed it a known before/after NDVI pair
- [ ] `health_score` degrades sensibly when you feed it a lower NDVI ratio and higher anomaly severity — test with 3–4 hand-crafted scenarios (healthy, mild stress, severe degradation, post-restoration)
- [ ] Snapshot history actually accumulates (doesn't overwrite) when you call `/update` multiple times
- [ ] Map before/after toggle visually shows a difference for your demo date range — if it doesn't, your date ranges are too close together or hit heavy cloud cover; adjust

---

## 8. Integration checkpoints with the rest of the team

| When | With whom | What |
|---|---|---|
| Day 1, hour 1 | M1 | Lock plot_id, bbox/boundary, and share GEE project access |
| End of Day 1 | M5 | Confirm Twin snapshot schema and the four endpoints above |
| End of Day 1 | M6 | Decide: Folium-rendered map vs. raw GeoJSON handoff to React/Leaflet |
| Mid Day 2 | M1 | Agree on the exact `pct_change` / anomaly severity threshold that counts as "significant" — both modules must trigger together |
| Mid Day 2 | M3 | Confirm what IoT summary fields feed into `water_quality`/`soil_conditions` in the snapshot |
| Day 3 morning | M4 + M5 | Rehearse the full satellite-alert → freeze → dashboard-update chain, timed against the demo script |

---

## 9. Hour-by-hour schedule (M2 specifically)

**Day 1**
- Hr 0–1: Lock plot ID/bbox with M1, get GEE access, trace or pull the real boundary polygon
- Hr 1–3: Pull before/after Sentinel-2 composites, export thumbnails, compute NDVI change number
- Hr 3–4: Pull GMW historical extent (2000 vs. most recent), compute area change over time
- Hr 4–6: Build the `TwinSnapshot` schema, in-memory history store, `add_snapshot`/`get_current`/`get_history`
- Hr 6–7: Get a basic Folium map rendering with the boundary + one NDVI overlay
- Hr 7–8: Publish API contract to the team

**Day 2**
- Hr 0–2: Implement health score + permanence score functions, test against hand-crafted scenarios
- Hr 2–4: Wire the `/satellite-change` endpoint, agree on the significance threshold with M1
- Hr 4–6: Integration test with M5 — confirm snapshots flow in correctly from AI/IoT/blockchain updates
- Hr 6–8: Build the before/after toggle + color-coded health indicator on the map; hand off GeoJSON/thumbnails to M6 if they're rendering in React instead

**Day 3**
- Hr 0–2: Full run-through of the demo scenario — confirm the map visibly reflects each scene (healthy → degraded → frozen → restored)
- Hr 2–4: Polish the timeline/history view — this is likely to be on-screen the longest, make it look intentional
- Hr 4–6: Rehearse with M1/M4/M5, fix any timing mismatches between satellite alert and freeze trigger
- Hr 6–8: Buffer; prep your one-line answer for "how is this different from just NDVI on a map" (answer: it's a fused, time-versioned state combining IoT + satellite + community + credit status, not a single data layer)

---

## 10. Suggested `digital-twin/` folder structure

```
digital-twin/
├── data/
│   ├── pichavaram_boundary.geojson
│   ├── gmw_2000_extent.shp
│   ├── gmw_2020_extent.shp
│   ├── ndvi_before_thumb.png
│   └── ndvi_after_thumb.png
├── gis/
│   ├── boundary.py         # polygon loading/clipping utilities
│   └── extent_history.py   # GMW area-over-time calculation
├── satellite/
│   ├── composites.py       # GEE before/after pulls
│   └── change_detection.py # pct_change + significance logic
├── temporal/
│   ├── snapshot.py         # TwinSnapshot model + history store
│   └── scoring.py          # health_score(), permanence_score()
├── map/
│   └── render.py           # Folium map builder
├── api.py                  # FastAPI app, all endpoints
└── requirements.txt
```

---

## 11. If something goes wrong (fallback plan)

- **GMW download/processing too slow:** skip the extent-over-time calculation, rely entirely on Sentinel-2 NDVI before/after for the change story — still demonstrable, just one fewer independent data point.
- **Cloud cover ruins your before/after composite:** widen the date windows (whole season instead of 2–3 months), or shift your "after" date to align with a known clear-sky period; Sentinel-2 revisits every 5 days so you have options.
- **Folium map feels clunky to integrate with M6's React frontend:** stop trying to embed it — export the boundary as GeoJSON and the thumbnails as static images, let M6 render them natively in Leaflet.js. Don't burn hours fighting an iframe.
- **Running low on time overall:** prioritize in this order — Twin snapshot schema + API > satellite change detection number > map with boundary + before/after toggle > health/permanence scoring > GMW historical extent > polish. The first three carry the demo; the rest is depth you add if time allows.
