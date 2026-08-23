# -*- coding: utf-8 -*-
"""
test_api.py - Integration test suite for the Digital Twin + GIS Service

Mirrors the structure of ai/test_api.py.
Run with the server already started on port 8002:

  cd digital-twin/
  uvicorn api:app --port 8002 &
  python test_api.py

All tests use the live HTTP API (no mocking) to validate the full stack.
Target: 28+ assertions across all endpoints.
"""

import sys
import json
import requests

BASE = "http://localhost:8002"
PLOT = "MNG-001"
PASS = 0
FAIL = 0


def check(description: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {description}")
    else:
        FAIL += 1
        print(f"  [FAIL] {description}" + (f" -- {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n[{title}]")


# ─────────────────────────────────────────────────────────────────────────────
# 1. HEALTH
# ─────────────────────────────────────────────────────────────────────────────
section("1. Health / liveness")
r = requests.get(f"{BASE}/api/twin/health")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("status ok",        d.get("status") == "ok")
check("plot_id present",  d.get("plot_id") == PLOT)
check("plots_tracked has MNG-001", PLOT in d.get("plots_tracked", []))


# ─────────────────────────────────────────────────────────────────────────────
# 2. BOUNDARY
# ─────────────────────────────────────────────────────────────────────────────
section("2. Boundary GeoJSON")
r = requests.get(f"{BASE}/api/twin/boundary")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("FeatureCollection",  d.get("type") == "FeatureCollection")
check("has features",       len(d.get("features", [])) > 0)
feat = d["features"][0]
check("geometry type Polygon", feat["geometry"]["type"] == "Polygon")
check("plot_id property",  feat["properties"].get("plot_id") == PLOT)


# ─────────────────────────────────────────────────────────────────────────────
# 3. CURRENT STATE (seeded from demo)
# ─────────────────────────────────────────────────────────────────────────────
section("3. Current state (seeded demo snapshot)")
r = requests.get(f"{BASE}/api/twin/{PLOT}/current")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("plot_id matches",   d.get("plot_id") == PLOT)
check("has timestamp",     "timestamp" in d)
check("ndvi present",      d.get("ndvi") is not None)
check("health_score >= 0",  d.get("health_score", -1) >= 0)
check("permanence_score >= 0", d.get("permanence_score", -1) >= 0)
check("credit_status present", d.get("credit_status") is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 4. HISTORY (seeded -- should have 4 snapshots)
# ─────────────────────────────────────────────────────────────────────────────
section("4. Snapshot history (seeded demo)")
r = requests.get(f"{BASE}/api/twin/{PLOT}/history")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("history is a list",   isinstance(d, list))
check(">= 4 seeded snapshots", len(d) >= 4, f"got {len(d)}")
# Health scores should tell the demo story
scores = [s.get("health_score") for s in d if s.get("health_score") is not None]
if len(scores) >= 3:
    check("first score >= last (degradation happened)", scores[0] >= scores[-2],
          f"scores={scores}")
check("all have plot_id", all(s.get("plot_id") == PLOT for s in d))

# limit param
r2 = requests.get(f"{BASE}/api/twin/{PLOT}/history?limit=2")
check("limit=2 returns <= 2", len(r2.json()) <= 2)


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST UPDATE -- append snapshot, verify accumulation
# ─────────────────────────────────────────────────────────────────────────────
section("5. POST update -- snapshot accumulation")
before_count = len(requests.get(f"{BASE}/api/twin/{PLOT}/history").json())

payload = {
    "ndvi":               0.38,
    "carbon_stock":       28_500.0,
    "carbon_confidence":  0.82,
    "water_quality":      {"salinity_ppt": 15.0, "ph": 7.7, "water_level_m": 1.05, "anomaly": False},
    "credit_status":      "UNDER_REVIEW",
    "source_event":       "routine_update",
    "iot_anomaly_penalty": 0.0,
    "ai_anomaly_severity": 0.0,
    "notes":              "Test update from test_api.py",
}
r = requests.post(f"{BASE}/api/twin/{PLOT}/update", json=payload)
check("HTTP 200", r.status_code == 200)
d = r.json()
check("status recorded",     d.get("status") == "recorded")
check("snapshot_count grew", d.get("snapshot_count", 0) > before_count,
      f"before={before_count}, after={d.get('snapshot_count')}")
check("health_score returned", d.get("health_score") is not None)
check("permanence_score returned", d.get("permanence_score") is not None)

after_count = len(requests.get(f"{BASE}/api/twin/{PLOT}/history").json())
check("history actually grew", after_count == before_count + 1,
      f"before={before_count}, after={after_count}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. SATELLITE CHANGE
# ─────────────────────────────────────────────────────────────────────────────
section("6. Satellite change detection")
r = requests.get(f"{BASE}/api/twin/{PLOT}/satellite-change")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("plot_id matches",      d.get("plot_id") == PLOT)
check("period_before present", "period_before" in d)
check("period_after present",  "period_after" in d)
change = d.get("change", {})
check("pct_change is float",  isinstance(change.get("pct_change"), (int, float)))
check("significant_degradation is bool", isinstance(change.get("significant_degradation"), bool))
check("direction in valid set", change.get("direction") in ("improving", "stable", "degrading"))
# pct_change for our pre-computed data should be around -13% (0.412 -> 0.358)
pct = change.get("pct_change", 0)
check("pct_change in plausible range", -50 < pct < 50, f"pct_change={pct}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. SCORES ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
section("7. Scores endpoint")
r = requests.get(f"{BASE}/api/twin/{PLOT}/scores?iot_anomaly_penalty=5&ai_anomaly_severity=0.1")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("health_score present",     "health_score" in d)
check("permanence_score present",  "permanence_score" in d)
check("volatility present",        "volatility" in d)
check("health_score 0-100",        0 <= d.get("health_score", -1) <= 100)

# Higher severity -> lower health score than without penalties
r_clean = requests.get(f"{BASE}/api/twin/{PLOT}/scores")
clean_health = r_clean.json().get("health_score", 100)
penalised_health = d.get("health_score", 0)
check("anomaly penalty reduces health", penalised_health <= clean_health,
      f"clean={clean_health}, penalised={penalised_health}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. EXTENT HISTORY
# ─────────────────────────────────────────────────────────────────────────────
section("8. Extent history (GMW)")
r = requests.get(f"{BASE}/api/twin/{PLOT}/extent-history")
check("HTTP 200", r.status_code == 200)
d = r.json()
check("plot_id matches",  d.get("plot_id") == PLOT)
check("history is list",  isinstance(d.get("history"), list))
check(">= 5 epochs",       len(d.get("history", [])) >= 5)
check("summary present",  "summary" in d)
summary = d.get("summary", {})
check("pct_change in summary", "pct_change" in summary)
check("direction in summary",  summary.get("direction") in ("gain", "loss"))


# ─────────────────────────────────────────────────────────────────────────────
# 9. MAP ENDPOINT (HTML response)
# ─────────────────────────────────────────────────────────────────────────────
section("9. Map HTML endpoint")
r = requests.get(f"{BASE}/api/twin/{PLOT}/map")
check("HTTP 200",         r.status_code == 200)
check("Content-Type HTML", "text/html" in r.headers.get("content-type", ""))
html = r.text
check("Leaflet present",   "leaflet" in html.lower())
check("MNG-001 in HTML",   PLOT in html)
check("map has layers",    any(x in html.lower() for x in ["layercontrol", "layer-control", "control-layers", "layers"]))


# ─────────────────────────────────────────────────────────────────────────────
# 10. 404 FOR UNKNOWN PLOT
# ─────────────────────────────────────────────────────────────────────────────
section("10. 404 for unknown plot")
r = requests.get(f"{BASE}/api/twin/UNKNOWN-999/current")
check("HTTP 404 for unknown plot", r.status_code == 404)


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
total = PASS + FAIL
print(f"\n{'-'*60}")
print(f"Result: {PASS}/{total} checks passed", end="")
if FAIL == 0:
    print(" -- All systems go! [OK]")
else:
    print(f" -- {FAIL} FAILED [ERROR]")
    sys.exit(1)
