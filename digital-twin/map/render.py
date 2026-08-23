"""
map/render.py — Folium map builder for MNG-001 Digital Twin

Builds an interactive Leaflet map (via Folium) showing:
  - Plot boundary outline (color-coded green/yellow/red by health)
  - Health indicator circle marker with popup
  - NDVI-before and NDVI-after image overlays (toggleable via LayerControl)
  - Extent-history annotation in the popup
  - Satellite change stats in the popup

The map is served as an HTML string via the /api/twin/{plot_id}/map endpoint.

M6 integration note (from work plan §5):
  If M6 wants React/Leaflet instead of an iframe, give them:
    GET /api/twin/{plot_id}/current    → JSON snapshot
    GET /api/twin/boundary             → raw GeoJSON
  and let them render natively. Don't force-embed a Folium export into React.
"""

import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from temporal.snapshot import TwinSnapshot

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "..", "data")


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH → COLOUR MAPPING
# ─────────────────────────────────────────────────────────────────────────────

def _health_color(health_score: Optional[float]) -> str:
    """Return a CSS/Leaflet colour string based on health score."""
    if health_score is None:
        return "gray"
    if health_score >= 70:
        return "#2ecc71"   # green
    elif health_score >= 40:
        return "#f39c12"   # amber
    else:
        return "#e74c3c"   # red


def _health_label(health_score: Optional[float]) -> str:
    if health_score is None:
        return "Unknown"
    if health_score >= 70:
        return "Healthy"
    elif health_score >= 40:
        return "Stressed"
    else:
        return "Degraded"


# ─────────────────────────────────────────────────────────────────────────────
# MAP BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_map(
    snapshot: Optional["TwinSnapshot"] = None,
    include_ndvi_overlays: bool = True,
) -> "folium.Map":
    """
    Build and return a Folium Map for MNG-001.

    Parameters
    ----------
    snapshot : TwinSnapshot or None
        The current twin state. If None, map renders with no data popups.
    include_ndvi_overlays : bool
        If True, adds before/after NDVI image overlays. Disable if thumbnail
        files are not present (avoids Folium warnings).

    Returns
    -------
    folium.Map
    """
    import folium
    from folium.plugins import MeasureControl, Fullscreen

    from gis.boundary import load_boundary, boundary_centroid, boundary_area_ha

    centroid_lat, centroid_lon = boundary_centroid()
    color = _health_color(snapshot.health_score if snapshot else None)
    label = _health_label(snapshot.health_score if snapshot else None)

    # ── Base map ─────────────────────────────────────────────────────────────
    m = folium.Map(
        location=[centroid_lat, centroid_lon],
        zoom_start=14,
        tiles="OpenStreetMap",
    )

    # ── Satellite basemap tile option ─────────────────────────────────────────
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite (Esri)",
        overlay=False,
        control=True,
    ).add_to(m)

    # ── Plot boundary ─────────────────────────────────────────────────────────
    boundary_geojson = load_boundary()
    folium.GeoJson(
        boundary_geojson,
        name="Plot Boundary (MNG-001)",
        style_function=lambda x, c=color: {
            "color":       c,
            "weight":      3,
            "fillColor":   c,
            "fillOpacity": 0.12,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["plot_id", "site", "area_ha_approx", "ecosystem"],
            aliases=["Plot ID", "Site", "Area (ha, approx)", "Ecosystem"],
        ),
    ).add_to(m)

    # ── Health indicator marker ────────────────────────────────────────────────
    popup_html = _build_popup_html(snapshot, label, color)
    folium.CircleMarker(
        location=[centroid_lat, centroid_lon],
        radius=18,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=320),
        tooltip=f"MNG-001 — {label} ({snapshot.health_score:.0f}/100)" if snapshot and snapshot.health_score else "MNG-001",
    ).add_to(m)

    # ── NDVI image overlays ───────────────────────────────────────────────────
    bounds = [[11.400, 79.760], [11.450, 79.810]]   # [[lat_min, lon_min], [lat_max, lon_max]]

    if include_ndvi_overlays:
        before_thumb = os.path.join(_DATA_DIR, "ndvi_before_thumb.png")
        after_thumb  = os.path.join(_DATA_DIR, "ndvi_after_thumb.png")

        if os.path.exists(before_thumb):
            folium.raster_layers.ImageOverlay(
                image=before_thumb,
                bounds=bounds,
                opacity=0.55,
                name="NDVI — Before (Jan–Mar 2025)",
                show=False,
            ).add_to(m)

        if os.path.exists(after_thumb):
            folium.raster_layers.ImageOverlay(
                image=after_thumb,
                bounds=bounds,
                opacity=0.55,
                name="NDVI — After (Apr–Jun 2026)",
                show=False,
            ).add_to(m)

    # ── Controls ──────────────────────────────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)
    MeasureControl().add_to(m)
    Fullscreen().add_to(m)

    return m


def render_map_html(
    snapshot: Optional["TwinSnapshot"] = None,
    include_ndvi_overlays: bool = True,
) -> str:
    """Build the map and return its full HTML string."""
    m = build_map(snapshot, include_ndvi_overlays)
    return m._repr_html_()


def save_map(
    snapshot: Optional["TwinSnapshot"] = None,
    path: str = "twin_map.html",
    include_ndvi_overlays: bool = True,
) -> str:
    """Build the map, save to file, and return the path."""
    m = build_map(snapshot, include_ndvi_overlays)
    m.save(path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# POPUP HTML BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_popup_html(
    snapshot: Optional["TwinSnapshot"],
    label: str,
    color: str,
) -> str:
    """Build the HTML string shown in the plot marker popup."""
    if snapshot is None:
        return "<b>MNG-001 — Pichavaram</b><br/>No twin data loaded."

    ts_str = snapshot.timestamp.strftime("%Y-%m-%d %H:%M UTC") if snapshot.timestamp else "—"

    rows = [
        ("Plot ID",          snapshot.plot_id),
        ("Timestamp",        ts_str),
        ("Status",           f'<span style="color:{color};font-weight:bold">{label}</span>'),
        ("Health Score",     f"{snapshot.health_score:.1f} / 100" if snapshot.health_score is not None else "—"),
        ("Permanence Score", f"{snapshot.permanence_score:.1f} / 100" if snapshot.permanence_score is not None else "—"),
        ("NDVI",             f"{snapshot.ndvi:.4f}" if snapshot.ndvi is not None else "—"),
        ("Carbon Stock",     f"{snapshot.carbon_stock:,.0f} t CO₂e" if snapshot.carbon_stock else "—"),
        ("Area",             f"{snapshot.area_ha:.1f} ha"),
        ("Credit Status",    snapshot.credit_status or "—"),
        ("Event",            snapshot.source_event or "—"),
    ]

    table_rows = "".join(
        f"<tr><td style='color:#888;padding-right:8px'>{k}</td><td><b>{v}</b></td></tr>"
        for k, v in rows
    )

    return f"""
    <div style="font-family:sans-serif;font-size:13px;min-width:260px">
      <div style="background:{color};color:white;padding:6px 10px;border-radius:4px 4px 0 0;margin-bottom:8px">
        <b>MNG-001 — Pichavaram Mangrove</b>
      </div>
      <table style="border-collapse:collapse;width:100%">{table_rows}</table>
      {f'<p style="color:#555;font-size:11px;margin-top:6px">{snapshot.notes}</p>' if snapshot.notes else ''}
    </div>
    """
