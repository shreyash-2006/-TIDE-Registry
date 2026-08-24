"""
thingspeak_service.py — Dedicated Service for ThingSpeak IoT Channel Data Extraction.

Extracts, cleans, and formats real-time IoT sensor feeds from ThingSpeak Channel 3465169.
API Endpoint: https://api.thingspeak.com/channels/3465169/feeds.json?api_key=1B0QXQ9AX389NOVW
"""

import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

# ThingSpeak Channel Config
THINGSPEAK_CHANNEL_ID = "3465169"
THINGSPEAK_API_KEY = "1B0QXQ9AX389NOVW"
THINGSPEAK_FEEDS_URL = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json?api_key={THINGSPEAK_API_KEY}"

TIMEOUT = 8.0  # seconds


def fetch_raw_thingspeak_data(results_count: Optional[int] = 50) -> Dict[str, Any]:
    """
    Fetch raw payload directly from ThingSpeak API.
    """
    url = THINGSPEAK_FEEDS_URL
    if results_count and results_count > 0:
        url += f"&results={results_count}"
        
    try:
        response = httpx.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching ThingSpeak data: {e}")
        return {
            "error": True,
            "message": str(e),
            "channel": {},
            "feeds": []
        }


def _safe_float(val: Any) -> Optional[float]:
    """Parse string/number to float cleanly or return None if empty/invalid."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_feed_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cleanly parse and format a single feed entry from ThingSpeak fields.
    
    ThingSpeak Field Mapping:
      - field1: Temperature (°C)
      - field2: Humidity (%)
      - field3: Soil Moisture (raw ADC converted via 100*field/4045)
      - field4: Offline Temp (°C)
      - field5: Offline Humidity (%)
      - field6: Offline Moisture (raw ADC converted via 100*field/4045)
      - field7: Custom Time
    """
    temp = _safe_float(entry.get("field1"))
    hum = _safe_float(entry.get("field2"))
    moist = _safe_float(entry.get("field3"))
    
    off_temp = _safe_float(entry.get("field4"))
    off_hum = _safe_float(entry.get("field5"))
    off_moist = _safe_float(entry.get("field6"))
    
    # Calculate soil moisture percentage using (100 * field / 4045) formula
    moist_pct = None
    if moist is not None:
        moist_pct = round((100.0 * moist) / 4045.0, 1)

    off_moist_pct = None
    if off_moist is not None:
        off_moist_pct = round((100.0 * off_moist) / 4045.0, 1)
            
    return {
        "entry_id": entry.get("entry_id"),
        "created_at": entry.get("created_at"),
        "temperature": temp,
        "humidity": hum,
        "moisture_raw": moist,
        "moisture_pct": moist_pct,
        "offline_temperature": off_temp,
        "offline_humidity": off_hum,
        "offline_moisture": off_moist,
        "offline_moisture_pct": off_moist_pct,
        "custom_time": entry.get("field7"),
    }


def get_thingspeak_telemetry(results_count: int = 50) -> Dict[str, Any]:
    """
    Extract, clean, and structure ThingSpeak channel feeds into a ready-to-render payload.
    """
    raw_data = fetch_raw_thingspeak_data(results_count=results_count)
    
    if raw_data.get("error"):
        return {
            "status": "error",
            "message": raw_data.get("message", "Failed to contact ThingSpeak API"),
            "channel": {},
            "latest": None,
            "feeds": [],
            "summary": {}
        }
        
    channel_info = raw_data.get("channel", {})
    raw_feeds = raw_data.get("feeds", [])
    
    parsed_feeds = [parse_feed_entry(f) for f in raw_feeds]
    
    # Filter out empty/null entries for latest status calculation
    valid_feeds = [f for f in parsed_feeds if f["temperature"] is not None or f["offline_temperature"] is not None]
    
    latest_entry = parsed_feeds[-1] if parsed_feeds else None
    
    # Calculate summary metrics if feeds exist
    temps = [f["temperature"] for f in valid_feeds if f["temperature"] is not None]
    hums = [f["humidity"] for f in valid_feeds if f["humidity"] is not None]
    moists = [f["moisture_pct"] for f in valid_feeds if f["moisture_pct"] is not None]
    
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    avg_hum = round(sum(hums) / len(hums), 1) if hums else None
    avg_moist = round(sum(moists) / len(moists), 1) if moists else None
    
    return {
        "status": "ok",
        "channel": {
            "id": channel_info.get("id"),
            "name": channel_info.get("name", "Blue Carbon Sensor"),
            "latitude": channel_info.get("latitude"),
            "longitude": channel_info.get("longitude"),
            "last_entry_id": channel_info.get("last_entry_id"),
            "updated_at": channel_info.get("updated_at"),
            "field_labels": {
                "field1": channel_info.get("field1", "Temperature"),
                "field2": channel_info.get("field2", "Humidity"),
                "field3": channel_info.get("field3", "Moisture"),
                "field4": channel_info.get("field4", "Offline Temp"),
                "field5": channel_info.get("field5", "Offline Humidity"),
                "field6": channel_info.get("field6", "Offline Moisture"),
                "field7": channel_info.get("field7", "Time"),
            }
        },
        "latest": latest_entry,
        "summary": {
            "total_entries": len(parsed_feeds),
            "avg_temperature": avg_temp,
            "avg_humidity": avg_hum,
            "avg_moisture_pct": avg_moist,
            "min_temp": min(temps) if temps else None,
            "max_temp": max(temps) if temps else None,
        },
        "feeds": parsed_feeds
    }


if __name__ == "__main__":
    # Test runner for standalone verification
    data = get_thingspeak_telemetry(results_count=10)
    print(f"Channel Name: {data['channel'].get('name')}")
    print(f"Total Feeds Extracted: {len(data['feeds'])}")
    print(f"Latest Telemetry: {data['latest']}")
