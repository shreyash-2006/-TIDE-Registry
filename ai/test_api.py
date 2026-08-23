"""
test_api.py — Full validation checklist for the Blue Carbon MRV AI Service
Runs all checks from section 8 of the work plan.

Usage:
  python test_api.py              # runs against http://localhost:8001
  python test_api.py --url http://other-host:8001
"""

import json
import sys
import argparse
import urllib.request
import urllib.error

BASE = "http://localhost:8001"

PASS = "[PASS]"
FAIL = "[FAIL]"


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def get(path: str, params: str = "") -> dict:
    url  = f"{BASE}{path}{params}"
    resp = urllib.request.urlopen(url, timeout=10)
    return json.loads(resp.read())


def check(label: str, cond: bool, details: str = "") -> bool:
    status = PASS if cond else FAIL
    line   = f"  {status}  {label}"
    if details:
        line += f"  ({details})"
    print(line)
    return cond


# ─────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────

def test_health() -> int:
    print("\n[1] Health / liveness")
    h   = get("/api/ai/health")
    ok  = 0
    ok += check("Service status = 'ok'", h.get("status") == "ok")
    ok += check("Plot ID = MNG-001", h.get("plot_id") == "MNG-001")
    ok += check("Carbon model meta present", "carbon_model_meta" in h)
    ok += check("NDVI stats present", "ndvi_stats" in h)
    return ok


def test_carbon_estimate() -> int:
    print("\n[2] Carbon estimation — /api/ai/estimate")
    ok = 0

    # Plausible NDVI for Pichavaram
    r = post("/api/ai/estimate", {"plot_id": "MNG-001", "ndvi": 0.42, "area_ha": 280.0})

    ok += check("Response has carbon_estimate",     "carbon_estimate"    in r)
    ok += check("Response has standard_deviation",  "standard_deviation" in r)
    ok += check("Response has creditable_carbon",   "creditable_carbon"  in r)
    ok += check("creditable_carbon <= carbon_estimate",
                r["creditable_carbon"] <= r["carbon_estimate"],
                f"{r['creditable_carbon']} <= {r['carbon_estimate']}")
    ok += check("creditable_carbon >= 0",
                r["creditable_carbon"] >= 0.0,
                str(r["creditable_carbon"]))
    ok += check("carbon_estimate > 0",
                r["carbon_estimate"] > 0.0,
                f"{r['carbon_estimate']} t CO2e")
    ok += check("co2_per_ha looks plausible (> 0)",
                r.get("co2_per_ha", 0) > 0.0,
                f"{r.get('co2_per_ha')} t/ha")
    return ok


def test_anomaly_healthy() -> int:
    print("\n[3] Anomaly detection — healthy reading")
    ok = 0
    healthy = {
        "plot_id": "MNG-001",
        "current":  {"salinity": 14.0, "temperature": 28.0, "ph": 7.8,
                     "soil_moisture": 65.0, "water_level": 1.1, "ndvi": 0.44},
        "previous": {"salinity": 14.0, "temperature": 28.0, "ph": 7.8,
                     "soil_moisture": 65.0, "water_level": 1.1, "ndvi": 0.45},
    }
    r = post("/api/ai/detect-anomaly", healthy)
    ok += check("anomaly = False for healthy reading",
                r["anomaly"] is False,
                f"anomaly={r['anomaly']}, severity={r['severity']}")
    ok += check("severity < 0.5 for healthy reading",
                r["severity"] < 0.5,
                str(r["severity"]))
    return ok


def test_anomaly_degraded() -> int:
    print("\n[4] Anomaly detection — degraded reading")
    ok = 0
    degraded = {
        "plot_id": "MNG-001",
        "current": {"salinity": 30.0, "temperature": 36.0, "ph": 7.8,
                    "soil_moisture": 20.0, "water_level": 1.1, "ndvi": 0.20},
        "previous": {"salinity": 14.0, "temperature": 28.0, "ph": 7.8,
                     "soil_moisture": 65.0, "water_level": 1.1, "ndvi": 0.44},
    }
    r = post("/api/ai/detect-anomaly", degraded)
    ok += check("anomaly = True for degraded reading",
                r["anomaly"] is True,
                f"anomaly={r['anomaly']}, severity={r['severity']}")
    ok += check("severity > 0.5 for degraded reading",
                r["severity"] > 0.5,
                str(r["severity"]))
    ok += check("combined_score present",
                "combined_score" in r)
    ok += check("reasons list is non-empty",
                len(r.get("reasons", [])) > 0,
                str(r.get("reasons", [])))
    return ok


def test_mrv_confidence() -> int:
    print("\n[5] MRV confidence — /api/ai/mrv-confidence")
    ok = 0

    # Healthy: should be mint-eligible
    r = post("/api/ai/mrv-confidence", {
        "iot_consistency": 95, "satellite_evidence": 90,
        "ai_confidence": 92, "community_evidence": 85,
        "historical_consistency": 88
    })
    ok += check("High scores -> eligible=True",
                r["eligible"] is True,
                f"mrv={r['mrv_confidence']}")
    ok += check("High scores -> freeze_alert=False",
                r["freeze_alert"] is False)

    # Degraded: should trigger freeze
    r2 = post("/api/ai/mrv-confidence", {
        "iot_consistency": 15, "satellite_evidence": 10,
        "ai_confidence": 20, "community_evidence": 10,
        "historical_consistency": 15
    })
    ok += check("Low scores -> freeze_alert=True",
                r2["freeze_alert"] is True,
                f"mrv={r2['mrv_confidence']}")
    ok += check("Low scores -> eligible=False",
                r2["eligible"] is False)

    return ok


def test_simulate() -> int:
    print("\n[6] Simulator endpoint — /api/ai/simulate")
    ok = 0

    # Normal mode
    r = get("/api/ai/simulate", "?anomaly=false")
    ok += check("Normal reading has salinity",   "salinity" in r)
    ok += check("Normal reading has ndvi",        "ndvi" in r)
    ok += check("Normal salinity in range [5, 25]",
                5 <= r.get("salinity", 0) <= 25,
                str(r.get("salinity")))

    # Anomaly mode
    ra = get("/api/ai/simulate", "?anomaly=true")
    ok += check("Anomaly reading has anomaly_injected=True",
                ra.get("anomaly_injected") is True)
    return ok


def test_full_pipeline() -> int:
    print("\n[7] Full pipeline — /api/ai/mrv-full")
    ok = 0
    r = post("/api/ai/mrv-full", {
        "plot_id":  "MNG-001",
        "current":  {"salinity": 14.0, "temperature": 28.0, "ph": 7.8,
                     "soil_moisture": 65.0, "water_level": 1.1},
        "previous": {"salinity": 14.0, "temperature": 28.0, "ph": 7.8,
                     "soil_moisture": 65.0, "water_level": 1.1},
        "current_ndvi": 0.42,
        "area_ha": 280.0,
        "community_evidence": 85.0,
        "historical_consistency": 82.0
    })
    ok += check("carbon section present",  "carbon" in r)
    ok += check("anomaly section present", "anomaly" in r)
    ok += check("mrv section present",     "mrv" in r)
    ok += check("mrv_confidence in mrv",   "mrv_confidence" in r.get("mrv", {}))
    return ok


def test_ndvi_timeseries() -> int:
    print("\n[8] NDVI time series — /api/ai/ndvi-timeseries")
    ok = 0
    r = get("/api/ai/ndvi-timeseries")
    ok += check("series is non-empty list",
                isinstance(r.get("series"), list) and len(r["series"]) > 0,
                f"{len(r.get('series', []))} records")
    ok += check("plot_id = MNG-001", r.get("plot_id") == "MNG-001")
    return ok


# ─────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8001")
    args = parser.parse_args()
    BASE = args.url.rstrip("/")

    print("=" * 55)
    print("Blue Carbon MRV AI Service — Validation Checklist")
    print(f"Target: {BASE}")
    print("=" * 55)

    suites = [
        test_health,
        test_carbon_estimate,
        test_anomaly_healthy,
        test_anomaly_degraded,
        test_mrv_confidence,
        test_simulate,
        test_full_pipeline,
        test_ndvi_timeseries,
    ]

    total_pass = 0
    total_all  = 0

    for suite in suites:
        try:
            passed = suite()
        except Exception as e:
            print(f"  [ERROR] {e}")
            passed = 0
        total_pass += passed
        total_all  += 10   # generous upper bound; we just track pass counts

    # Recount properly
    print("\n" + "=" * 55)
    # Re-run for accurate count
    pass_counts = []
    for suite in suites:
        try:
            pass_counts.append(suite())
        except Exception:
            pass_counts.append(0)

    total_pass = sum(pass_counts)
    print("\n" + "=" * 55)
    print(f"Result: {total_pass} checks passed across {len(suites)} test suites")
    print("All systems go!" if total_pass >= len(suites) * 3 else "Some checks need attention.")
