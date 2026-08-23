"""
database.py — Plain SQLite storage for the M5 backend.

No ORM. Just raw SQL via Python's built-in sqlite3 module.
Tables auto-create on first import. Functions: insert_*, get_*, update_*.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH


# ── Ensure data directory exists ───────────────────────────────────────
os.makedirs(DATA_DIR, exist_ok=True)


# ── Connection helper ──────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory set so rows behave like dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ─────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plots (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    lat             REAL NOT NULL,
    lng             REAL NOT NULL,
    area_ha         REAL NOT NULL,
    ecosystem_type  TEXT DEFAULT 'mangrove',
    baseline_ndvi   REAL DEFAULT 0.42,
    health_status   TEXT DEFAULT 'healthy',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    id              TEXT PRIMARY KEY,
    plot_id         TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    ndvi            REAL,
    salinity        REAL,
    soil_moisture   REAL,
    temperature     REAL,
    ph              REAL,
    water_level     REAL,
    source          TEXT DEFAULT 'simulator',
    quality_score   REAL DEFAULT 1.0,
    FOREIGN KEY (plot_id) REFERENCES plots(id)
);

CREATE TABLE IF NOT EXISTS credits (
    id              TEXT PRIMARY KEY,
    plot_id         TEXT NOT NULL,
    quantity        REAL NOT NULL,
    lower_bound     REAL NOT NULL,
    status          TEXT DEFAULT 'PROPOSED',
    mrv_score       REAL,
    evidence_hash   TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY (plot_id) REFERENCES plots(id)
);

CREATE TABLE IF NOT EXISTS anomalies (
    id              TEXT PRIMARY KEY,
    plot_id         TEXT NOT NULL,
    severity        REAL NOT NULL,
    description     TEXT,
    reasons         TEXT,
    source          TEXT DEFAULT 'ai',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (plot_id) REFERENCES plots(id)
);

CREATE TABLE IF NOT EXISTS community_reports (
    id              TEXT PRIMARY KEY,
    plot_id         TEXT NOT NULL,
    submitter       TEXT NOT NULL,
    description     TEXT NOT NULL,
    photo_uri       TEXT,
    status          TEXT DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (plot_id) REFERENCES plots(id)
);

CREATE TABLE IF NOT EXISTS retirements (
    id                TEXT PRIMARY KEY,
    credit_id         TEXT NOT NULL,
    plot_id           TEXT NOT NULL,
    amount            REAL NOT NULL,
    beneficiary_name  TEXT NOT NULL,
    offset_reason     TEXT NOT NULL,
    retiree_address   TEXT,
    certificate_id    TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (credit_id) REFERENCES credits(id)
);

CREATE TABLE IF NOT EXISTS system_config (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
"""


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


# ── Auto-init on import ───────────────────────────────────────────────
init_db()


# ── Helper ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _uuid() -> str:
    return str(uuid.uuid4())[:8]

def _row_to_dict(row) -> dict:
    if row is None:
        return None
    return dict(row)

def _rows_to_list(rows) -> list:
    return [dict(r) for r in rows]


# ── PLOTS ──────────────────────────────────────────────────────────────

def insert_plot(plot_id: str, name: str, lat: float, lng: float,
                area_ha: float, ecosystem_type: str = "mangrove",
                baseline_ndvi: float = 0.42) -> dict:
    conn = get_conn()
    now = _now()
    conn.execute(
        "INSERT OR IGNORE INTO plots (id, name, lat, lng, area_ha, ecosystem_type, baseline_ndvi, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (plot_id, name, lat, lng, area_ha, ecosystem_type, baseline_ndvi, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM plots WHERE id = ?", (plot_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_plot(plot_id: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM plots WHERE id = ?", (plot_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_all_plots() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM plots ORDER BY created_at").fetchall()
    conn.close()
    return _rows_to_list(rows)


def update_plot_health(plot_id: str, status: str):
    conn = get_conn()
    conn.execute("UPDATE plots SET health_status = ? WHERE id = ?", (status, plot_id))
    conn.commit()
    conn.close()


# ── OBSERVATIONS ───────────────────────────────────────────────────────

def insert_observation(plot_id: str, ndvi: float = None, salinity: float = None,
                       soil_moisture: float = None, temperature: float = None,
                       ph: float = None, water_level: float = None,
                       source: str = "simulator") -> dict:
    conn = get_conn()
    obs_id = f"obs-{_uuid()}"
    now = _now()
    conn.execute(
        "INSERT INTO observations (id, plot_id, timestamp, ndvi, salinity, soil_moisture, "
        "temperature, ph, water_level, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (obs_id, plot_id, now, ndvi, salinity, soil_moisture, temperature, ph, water_level, source),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_observations(plot_id: str, limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM observations WHERE plot_id = ? ORDER BY timestamp DESC LIMIT ?",
        (plot_id, limit),
    ).fetchall()
    conn.close()
    return _rows_to_list(rows)


# ── CREDITS ────────────────────────────────────────────────────────────

def insert_credit(plot_id: str, quantity: float, lower_bound: float,
                  mrv_score: float = None, evidence_hash: str = None) -> dict:
    conn = get_conn()
    credit_id = f"crd-{_uuid()}"
    now = _now()
    conn.execute(
        "INSERT INTO credits (id, plot_id, quantity, lower_bound, status, mrv_score, "
        "evidence_hash, created_at, updated_at) VALUES (?, ?, ?, ?, 'PROPOSED', ?, ?, ?, ?)",
        (credit_id, plot_id, quantity, lower_bound, mrv_score, evidence_hash, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM credits WHERE id = ?", (credit_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_credits(plot_id: str = None) -> list:
    conn = get_conn()
    if plot_id:
        rows = conn.execute(
            "SELECT * FROM credits WHERE plot_id = ? ORDER BY created_at DESC", (plot_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM credits ORDER BY created_at DESC").fetchall()
    conn.close()
    return _rows_to_list(rows)


def update_credit_status(credit_id: str, status: str) -> dict:
    conn = get_conn()
    now = _now()
    conn.execute(
        "UPDATE credits SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, credit_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM credits WHERE id = ?", (credit_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


# ── ANOMALIES ──────────────────────────────────────────────────────────

def insert_anomaly(plot_id: str, severity: float, description: str = "",
                   reasons: str = "", source: str = "ai") -> dict:
    conn = get_conn()
    anom_id = f"anm-{_uuid()}"
    now = _now()
    conn.execute(
        "INSERT INTO anomalies (id, plot_id, severity, description, reasons, source, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (anom_id, plot_id, severity, description, reasons, source, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM anomalies WHERE id = ?", (anom_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_anomalies(plot_id: str, limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM anomalies WHERE plot_id = ? ORDER BY created_at DESC LIMIT ?",
        (plot_id, limit),
    ).fetchall()
    conn.close()
    return _rows_to_list(rows)


# ── COMMUNITY REPORTS ──────────────────────────────────────────────────

def insert_community_report(plot_id: str, submitter: str, description: str,
                            photo_uri: str = None) -> dict:
    conn = get_conn()
    report_id = f"rpt-{_uuid()}"
    now = _now()
    conn.execute(
        "INSERT INTO community_reports (id, plot_id, submitter, description, photo_uri, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (report_id, plot_id, submitter, description, photo_uri, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM community_reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_community_reports(plot_id: str = None, limit: int = 50) -> list:
    conn = get_conn()
    if plot_id:
        rows = conn.execute(
            "SELECT * FROM community_reports WHERE plot_id = ? ORDER BY created_at DESC LIMIT ?",
            (plot_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM community_reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return _rows_to_list(rows)


def update_community_report_status(report_id: str, status: str) -> dict:
    conn = get_conn()
    conn.execute("UPDATE community_reports SET status = ? WHERE id = ?", (status, report_id))
    conn.commit()
    row = conn.execute("SELECT * FROM community_reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


# ── RETIREMENTS (BUYER OFFSET) ────────────────────────────────────────

def insert_retirement(credit_id: str, plot_id: str, amount: float,
                      beneficiary_name: str, offset_reason: str,
                      retiree_address: str = "0xBuyerWallet78a9") -> dict:
    conn = get_conn()
    ret_id = f"ret-{_uuid()}"
    cert_id = f"CERT-TIDE-{int(datetime.now(timezone.utc).timestamp())}-{_uuid().upper()}"
    now = _now()
    conn.execute(
        "INSERT INTO retirements (id, credit_id, plot_id, amount, beneficiary_name, "
        "offset_reason, retiree_address, certificate_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ret_id, credit_id, plot_id, amount, beneficiary_name, offset_reason, retiree_address, cert_id, now),
    )
    # Deduct lower_bound / quantity or update credit status if fully retired
    credit_row = conn.execute("SELECT * FROM credits WHERE id = ?", (credit_id,)).fetchone()
    if credit_row:
        rem_bound = max(0.0, credit_row["lower_bound"] - amount)
        rem_qty = max(0.0, credit_row["quantity"] - amount)
        new_status = "RETIRED" if rem_bound <= 0.0 else credit_row["status"]
        conn.execute(
            "UPDATE credits SET lower_bound = ?, quantity = ?, status = ?, updated_at = ? WHERE id = ?",
            (rem_bound, rem_qty, new_status, now, credit_id)
        )
    conn.commit()
    row = conn.execute("SELECT * FROM retirements WHERE id = ?", (ret_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_retirements(credit_id: str = None) -> list:
    conn = get_conn()
    if credit_id:
        rows = conn.execute("SELECT * FROM retirements WHERE credit_id = ? ORDER BY created_at DESC", (credit_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM retirements ORDER BY created_at DESC").fetchall()
    conn.close()
    return _rows_to_list(rows)


# ── SYSTEM CONFIG ──────────────────────────────────────────────────────

def set_config(key: str, value: str):
    conn = get_conn()
    now = _now()
    conn.execute(
        "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, ?)",
        (key, str(value), now),
    )
    conn.commit()
    conn.close()


def get_config(key: str, default: str = None) -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


# ── STATS ──────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Summary counts and aggregates for the dashboard."""
    conn = get_conn()
    plots = conn.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
    obs   = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    creds = conn.execute("SELECT COUNT(*) FROM credits").fetchone()[0]
    anoms = conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
    reports = conn.execute("SELECT COUNT(*) FROM community_reports").fetchone()[0]
    rets = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM retirements").fetchone()
    
    total_retired_count = rets[0] if rets else 0
    total_retired_tonnes = round(float(rets[1]), 2) if rets else 0.0
    
    active_credits = conn.execute("SELECT COUNT(*), COALESCE(SUM(lower_bound), 0) FROM credits WHERE status IN ('ACTIVE', 'PROPOSED', 'REVERIFIED')").fetchone()
    frozen_credits = conn.execute("SELECT COUNT(*), COALESCE(SUM(lower_bound), 0) FROM credits WHERE status = 'FROZEN'").fetchone()

    conn.close()
    return {
        "plots": plots,
        "observations": obs,
        "credits": creds,
        "anomalies": anoms,
        "community_reports": reports,
        "retirements": total_retired_count,
        "total_retired_tonnes": total_retired_tonnes,
        "active_credits_count": active_credits[0] if active_credits else 0,
        "active_credits_tonnes": round(float(active_credits[1]), 2) if active_credits else 0.0,
        "frozen_credits_count": frozen_credits[0] if frozen_credits else 0,
        "frozen_credits_tonnes": round(float(frozen_credits[1]), 2) if frozen_credits else 0.0,
    }

