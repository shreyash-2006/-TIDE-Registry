"""
test_api.py — Integration tests for the M5 backend.

Tests the backend's own endpoints (database, plots, credits, observations).
Does NOT require AI or Twin services to be running — those tests are marked
and will gracefully skip if services are unavailable.

Run:
  cd backend/
  python test_api.py
"""

import sys
import json
import time
import requests

BASE = "http://localhost:8000"

PASS = 0
FAIL = 0
SKIP = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  -- {detail}")


def skip(name, reason=""):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {name}  ({reason})")


# ─────────────────────────────────────────────────────────────────────
# 1. Health / Liveness
# ─────────────────────────────────────────────────────────────────────
print("\n[1. Health / Liveness]")
try:
    r = requests.get(f"{BASE}/api/health", timeout=15)
    data = r.json()
    check("Status 200", r.status_code == 200)
    check("Status is ok", data.get("status") == "ok")
    check("Has db_stats", "db_stats" in data)
    check("Has upstream", "upstream" in data)
except Exception as e:
    check("Backend reachable", False, str(e))
    print("\n  Backend not running. Start it with: uvicorn api:app --port 8000")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────
# 2. Plots
# ─────────────────────────────────────────────────────────────────────
print("\n[2. Plot Operations]")

# List plots
r = requests.get(f"{BASE}/api/plots")
plots = r.json()
check("List plots returns array", isinstance(plots, list))
check("Demo plot exists", any(p["id"] == "MNG-001" for p in plots))

# Get specific plot
r = requests.get(f"{BASE}/api/plots/MNG-001")
plot = r.json()
check("Get MNG-001", plot.get("id") == "MNG-001")
check("Has area_ha", plot.get("area_ha") == 280.0)
check("Has health_status", "health_status" in plot)

# 404 for unknown plot
r = requests.get(f"{BASE}/api/plots/UNKNOWN-999")
check("404 for unknown plot", r.status_code == 404)


# ─────────────────────────────────────────────────────────────────────
# 3. Observations
# ─────────────────────────────────────────────────────────────────────
print("\n[3. Observations]")

# Record an observation
r = requests.post(f"{BASE}/api/observations", json={
    "plot_id": "MNG-001",
    "ndvi": 0.40,
    "salinity": 14.5,
    "temperature": 28.0,
    "ph": 7.7,
    "soil_moisture": 63.0,
    "source": "test",
})
obs_data = r.json()
check("Record observation", r.status_code == 200)
check("Has observation id", "observation" in obs_data)

# List observations
r = requests.get(f"{BASE}/api/plots/MNG-001/observations")
obs_list = r.json()
check("List observations", isinstance(obs_list, list))
check("Has test observation", any(o.get("source") == "test" for o in obs_list))


# ─────────────────────────────────────────────────────────────────────
# 4. Credits
# ─────────────────────────────────────────────────────────────────────
print("\n[4. Credit Lifecycle]")

# Mint a credit
r = requests.post(f"{BASE}/api/credits/mint", json={
    "plot_id": "MNG-001",
    "quantity": 50.0,
    "lower_bound": 38.5,
    "mrv_score": 91.2,
})
mint_data = r.json()
check("Mint credit", r.status_code == 200)
check("Status is minted", mint_data.get("status") == "minted")
credit_id = mint_data.get("credit", {}).get("id")
check("Has credit id", credit_id is not None)

# List credits
r = requests.get(f"{BASE}/api/credits")
creds = r.json()
check("List credits", isinstance(creds, list))
check("New credit in list", any(c["id"] == credit_id for c in creds))

# Freeze
if credit_id:
    r = requests.post(f"{BASE}/api/credits/{credit_id}/freeze")
    freeze_data = r.json()
    check("Freeze credit", freeze_data.get("credit", {}).get("status") == "FROZEN")

    # Reverify
    r = requests.post(f"{BASE}/api/credits/{credit_id}/reverify")
    rev_data = r.json()
    check("Reverify credit", rev_data.get("credit", {}).get("status") == "REVERIFIED")
else:
    skip("Freeze credit", "no credit_id")
    skip("Reverify credit", "no credit_id")


# ─────────────────────────────────────────────────────────────────────
# 5. Offset Retirements & On-Chain Transfers
# ─────────────────────────────────────────────────────────────────────
print("\n[5. Offset Retirements & Transfer Restrictions]")

# Test Transfer Active
r = requests.post(f"{BASE}/api/credits/{credit_id}/status", json={"status": "ACTIVE"})
check("Activate credit", r.status_code == 200)

r = requests.post(f"{BASE}/api/credits/{credit_id}/transfer", json={
    "recipient_address": "0xGreenFundIndia89a",
    "amount": 5.0
})
check("Transfer active credit", r.status_code == 200)

# Test Transfer Frozen (should block with 400)
requests.post(f"{BASE}/api/credits/{credit_id}/freeze")
r_block = requests.post(f"{BASE}/api/credits/{credit_id}/transfer", json={
    "recipient_address": "0xBlockedBuyer",
    "amount": 2.0
})
check("Block transfer when frozen", r_block.status_code == 400)

# Re-activate for retirement test
requests.post(f"{BASE}/api/credits/{credit_id}/status", json={"status": "ACTIVE"})

# Test Carbon Offset Retirement (Burn)
r_ret = requests.post(f"{BASE}/api/credits/{credit_id}/retire", json={
    "amount": 4.0,
    "beneficiary_name": "Tata Motors NetZero Scope 1",
    "offset_reason": "Neutralize fleet logistics emissions 2025"
})
ret_data = r_ret.json()
check("Retire carbon offset", r_ret.status_code == 200)
check("Has certificate ID", "certificate_id" in ret_data)

r_list_ret = requests.get(f"{BASE}/api/retirements")
check("List retirements", len(r_list_ret.json()) > 0)


# ─────────────────────────────────────────────────────────────────────
# 6. Community Reports & Verification
# ─────────────────────────────────────────────────────────────────────
print("\n[6. Community Reports & Verification]")

r = requests.post(f"{BASE}/api/community-reports", json={
    "plot_id": "MNG-001",
    "submitter": "test_user",
    "description": "Test report -- healthy mangroves observed",
})
report_data = r.json()
check("Submit report", r.status_code == 200)
check("Has report id", "report" in report_data)
rep_id = report_data.get("report", {}).get("id")

r = requests.get(f"{BASE}/api/plots/MNG-001/community-reports")
reports = r.json()
check("List reports", isinstance(reports, list))

if rep_id:
    r_stat = requests.post(f"{BASE}/api/community-reports/{rep_id}/status", json={"status": "verified"})
    check("Update report verification status", r_stat.status_code == 200)


# ─────────────────────────────────────────────────────────────────────
# 7. Regulatory Thresholds Configuration
# ─────────────────────────────────────────────────────────────────────
print("\n[7. Regulatory Thresholds Configuration]")

r_thr = requests.post(f"{BASE}/api/config/thresholds", json={
    "mint_threshold": 87.0,
    "freeze_threshold": 62.0
})
check("Update policy thresholds", r_thr.status_code == 200)


# ─────────────────────────────────────────────────────────────────────
# 8. Dashboard Data & Multi-Role UI
# ─────────────────────────────────────────────────────────────────────
print("\n[8. Dashboard Data & Multi-Role UI]")

r = requests.get(f"{BASE}/api/dashboard-data")
dash = r.json()
check("Dashboard endpoint", r.status_code == 200)
check("Has stats", "stats" in dash)
check("Has demo_plot", "demo_plot" in dash)
check("Has services", "services" in dash)
check("Has config", "config" in dash)
check("Has retirements in dash", "retirements" in dash)

r_ui = requests.get(f"{BASE}/")
check("UI serves HTML", r_ui.status_code == 200)
check("Contains TIDE Registry", "TIDE Registry" in r_ui.text)
check("Contains Admin Portal", "Government / Admin" in r_ui.text)
check("Contains Developer Portal", "Project Developer" in r_ui.text)
check("Contains Marketplace", "Buyer & Marketplace" in r_ui.text)
check("Contains Community Portal", "Community Reporter" in r_ui.text)


# ─────────────────────────────────────────────────────────────────────
# 9. MRV Pipeline (Live with AI 8001 & Twin 8002)
# ─────────────────────────────────────────────────────────────────────
print("\n[9. Full Continuous MRV Pipeline (Live)]")

try:
    ai_health = requests.get("http://localhost:8001/api/ai/health", timeout=3)
    ai_ok = ai_health.status_code == 200
except Exception:
    ai_ok = False

if ai_ok:
    r = requests.post(f"{BASE}/api/plots/MNG-001/analyze?ndvi=0.38&anomaly_mode=false")
    if r.status_code == 200:
        result = r.json()
        check("Healthy analysis", "carbon" in result)
        check("Has anomaly result", "anomaly" in result)
        check("Has MRV result", "mrv" in result)
        check("Carbon estimate > 0", result.get("carbon", {}).get("carbon_estimate", 0) > 0)
        check("Creditable carbon lower bound > 0", result.get("carbon", {}).get("creditable_carbon", 0) > 0)
    else:
        check("Healthy analysis", False, f"Status {r.status_code}")

    r = requests.post(f"{BASE}/api/plots/MNG-001/analyze?ndvi=0.15&anomaly_mode=true")
    if r.status_code == 200:
        result = r.json()
        check("Anomaly analysis", result.get("anomaly", {}).get("anomaly", False) is True)
    else:
        check("Anomaly analysis", False, f"Status {r.status_code}")
else:
    skip("Healthy analysis", "AI service not running")
    skip("Has anomaly result", "AI service not running")
    skip("Has MRV result", "AI service not running")
    skip("Carbon estimate > 0", "AI service not running")
    skip("Creditable carbon lower bound > 0", "AI service not running")
# ─────────────────────────────────────────────────────────────────────
# 9. ThingSpeak IoT Extraction
# ─────────────────────────────────────────────────────────────────────
print("\n[9. ThingSpeak IoT Extraction]")
try:
    r = requests.get(f"{BASE}/api/thingspeak?results=5", timeout=10)
    data = r.json()
    check("Status 200", r.status_code == 200)
    check("Status ok", data.get("status") == "ok")
    check("Channel ID 3465169", str(data.get("channel", {}).get("id")) == "3465169")
    check("Has latest telemetry", "latest" in data)
    check("Has extracted feeds", isinstance(data.get("feeds"), list))
except Exception as e:
    check("ThingSpeak API extraction", False, str(e))


# ─────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────
total = PASS + FAIL + SKIP
print(f"\n{'='*50}")
print(f"Result: {PASS} passed, {FAIL} failed, {SKIP} skipped -- {total} total checks")
if FAIL == 0:
    print("All systems go! [OK]")
else:
    print(f"{FAIL} check(s) failed -- review output above")
    sys.exit(1)

