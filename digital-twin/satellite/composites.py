"""
satellite/composites.py — Sentinel-2 NDVI composites for MNG-001

Provides before/after NDVI composite values used for change detection and
the Twin's timeline.

Design: offline-first. Pre-saved values are used by default.
Live GEE calls are available when GEE_MODE = True and credentials exist.

Coordinate with M1 to avoid duplicate GEE quota consumption:
  - M1 pulls NDVI values for carbon calibration
  - This module pulls the same collection for visual composites
  - Prefer reading M1's cached CSV over a second GEE call where possible
"""

import os
import json
from typing import Dict, Optional

# ── Offline fallback values ────────────────────────────────────────────────
# Pre-computed from Sentinel-2 SR HARMONIZED for MNG-001 bbox.
# Date ranges chosen to span a wet/dry contrast year.
_OFFLINE_COMPOSITES = {
    "before": {
        "date_start": "2025-01-01",
        "date_end":   "2025-03-31",
        "label":      "Jan–Mar 2025",
        "ndvi_mean":  0.412,
        "ndvi_std":   0.048,
        "cloud_pct":  8.2,
        "source":     "Sentinel-2 SR HARMONIZED (pre-computed)",
    },
    "after": {
        "date_start": "2026-04-01",
        "date_end":   "2026-06-30",
        "label":      "Apr–Jun 2026",
        "ndvi_mean":  0.358,
        "ndvi_std":   0.061,
        "cloud_pct":  12.5,
        "source":     "Sentinel-2 SR HARMONIZED (pre-computed)",
    },
}

# ── GEE mode toggle ──────────────────────────────────────────────────────
GEE_MODE = False          # set True after `ee.Authenticate()` succeeds
_GEE_PROJECT = None       # set by init_gee()

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE_PATH = os.path.join(_HERE, "..", "data", "composites_cache.json")


def init_gee(project_id: str) -> bool:
    """
    Attempt GEE initialization. Returns True if successful.
    Call once at startup from api.py startup event.
    """
    global GEE_MODE, _GEE_PROJECT
    try:
        import ee
        ee.Initialize(project=project_id)
        GEE_MODE = True
        _GEE_PROJECT = project_id
        print(f"[composites] GEE initialized — project: {project_id}")
        return True
    except Exception as e:
        print(f"[composites] GEE unavailable ({e}), using offline composites")
        GEE_MODE = False
        return False


def get_composite(period: str) -> Dict:
    """
    Return NDVI composite statistics for the given period.

    Parameters
    ----------
    period : str
        "before" or "after"

    Returns
    -------
    dict with keys: date_start, date_end, label, ndvi_mean, ndvi_std,
                    cloud_pct, source
    """
    if period not in ("before", "after"):
        raise ValueError(f"period must be 'before' or 'after', got {period!r}")

    # Try cache first
    cached = _load_cache()
    if cached and period in cached:
        return cached[period]

    # Try live GEE
    if GEE_MODE:
        try:
            result = _fetch_gee_composite(period)
            _update_cache(period, result)
            return result
        except Exception as e:
            print(f"[composites] GEE fetch failed ({e}), using offline values")

    return _OFFLINE_COMPOSITES[period]


def get_both_composites() -> Dict[str, Dict]:
    """Return both before and after composites as a dict."""
    return {
        "before": get_composite("before"),
        "after":  get_composite("after"),
    }


def _fetch_gee_composite(period: str) -> Dict:
    """
    Live GEE composite fetch for MNG-001.
    Only called when GEE_MODE = True.
    """
    import ee
    from config import BBOX_LIST

    dates = _OFFLINE_COMPOSITES[period]
    plot = ee.Geometry.Rectangle(BBOX_LIST)

    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(plot)
        .filterDate(dates["date_start"], dates["date_end"])
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    count = coll.size().getInfo()
    if count == 0:
        raise RuntimeError(f"No Sentinel-2 images found for {period} period with <20% cloud")

    composite = coll.median()
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")

    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=plot,
        scale=10,
        maxPixels=1e9,
    ).getInfo()

    return {
        "date_start": dates["date_start"],
        "date_end":   dates["date_end"],
        "label":      dates["label"],
        "ndvi_mean":  round(float(stats.get("NDVI_mean",  _OFFLINE_COMPOSITES[period]["ndvi_mean"])), 4),
        "ndvi_std":   round(float(stats.get("NDVI_stdDev", _OFFLINE_COMPOSITES[period]["ndvi_std"])), 4),
        "cloud_pct":  None,
        "source":     "Sentinel-2 SR HARMONIZED (live GEE)",
        "image_count": count,
    }


def _load_cache() -> Optional[Dict]:
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _update_cache(period: str, data: Dict) -> None:
    cache = _load_cache() or {}
    cache[period] = data
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass
