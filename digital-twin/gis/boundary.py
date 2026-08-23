"""
gis/boundary.py — Plot boundary utilities

Loads, validates, and provides geometric helpers for the Pichavaram
mangrove plot boundary stored in data/pichavaram_boundary.geojson.

This file is the single point of access for the boundary geometry — the
map renderer, the twin state, and the satellite clipping all import from here.
"""

import json
import os
from typing import Tuple

# Shapely is optional — falls back gracefully if not installed
try:
    from shapely.geometry import shape as _shape, mapping as _mapping
    _SHAPELY = True
except ImportError:
    _SHAPELY = False

_HERE = os.path.dirname(os.path.abspath(__file__))
_BOUNDARY_PATH = os.path.join(_HERE, "..", "data", "pichavaram_boundary.geojson")


def load_boundary() -> dict:
    """
    Return the full GeoJSON FeatureCollection for MNG-001.

    Returns
    -------
    dict
        Parsed GeoJSON dict with a single Feature whose geometry is
        the plot polygon.
    """
    with open(_BOUNDARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def boundary_feature() -> dict:
    """Return the first (and only) Feature from the boundary GeoJSON."""
    fc = load_boundary()
    return fc["features"][0]


def boundary_geometry() -> dict:
    """Return the raw GeoJSON geometry dict (type=Polygon, coordinates=[...])."""
    return boundary_feature()["geometry"]


def boundary_centroid() -> Tuple[float, float]:
    """
    Return (lat, lon) centroid of the plot boundary.

    Uses shapely if available; falls back to bbox midpoint.
    """
    if _SHAPELY:
        geom = _shape(boundary_geometry())
        c = geom.centroid
        return round(c.y, 6), round(c.x, 6)
    else:
        # Simple bbox midpoint fallback
        coords = boundary_geometry()["coordinates"][0]
        lons = [p[0] for p in coords]
        lats = [p[1] for p in coords]
        return round((min(lats) + max(lats)) / 2, 6), round((min(lons) + max(lons)) / 2, 6)


def boundary_area_ha() -> float:
    """
    Estimate plot area in hectares.

    Uses shapely with UTM-44N projection for accuracy; falls back to
    a planar degree-based approximation if shapely is unavailable.
    """
    if _SHAPELY:
        try:
            from shapely.geometry import shape
            from pyproj import Transformer
            geom = shape(boundary_geometry())
            # Reproject to UTM zone 44N (EPSG:32644) — correct CRS for Tamil Nadu
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
            projected = _transform_geom(geom, transformer)
            return round(projected.area / 10_000, 2)
        except Exception:
            pass  # fall through to approximation

    # Degree-to-metre approximation (1° lat ≈ 111_000 m, 1° lon ≈ 91_000 m at 11°N)
    coords = boundary_geometry()["coordinates"][0]
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    width_m  = (max(lons) - min(lons)) * 91_000
    height_m = (max(lats) - min(lats)) * 111_000
    return round((width_m * height_m) / 10_000, 2)


def _transform_geom(geom, transformer):
    """Apply a pyproj Transformer to a shapely geometry."""
    from shapely.geometry import Polygon, MultiPolygon
    if geom.geom_type == "Polygon":
        exterior = [transformer.transform(x, y) for x, y in geom.exterior.coords]
        interiors = [
            [transformer.transform(x, y) for x, y in ring.coords]
            for ring in geom.interiors
        ]
        return Polygon(exterior, interiors)
    raise NotImplementedError(f"Unsupported geometry type: {geom.geom_type}")


def boundary_bbox() -> dict:
    """Return {lon_min, lat_min, lon_max, lat_max} from the boundary geometry."""
    coords = boundary_geometry()["coordinates"][0]
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    return {
        "lon_min": min(lons),
        "lat_min": min(lats),
        "lon_max": max(lons),
        "lat_max": max(lats),
    }
