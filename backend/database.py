"""MySQL production persistence; SQLite exists only for local tests/development."""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "resq.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USING_MYSQL = DATABASE_URL.startswith("mysql") or bool(os.getenv("MYSQL_HOST"))


class _MySQLCursor:
    def __init__(self, cursor): self._cursor = cursor
    def execute(self, query, params=None):
        self._cursor.execute(query.replace("?", "%s"), params or ())
        return self
    def executemany(self, query, params):
        self._cursor.executemany(query.replace("?", "%s"), params)
        return self
    def fetchone(self): return self._cursor.fetchone()
    def fetchall(self): return self._cursor.fetchall()
    @property
    def rowcount(self): return self._cursor.rowcount
    def close(self): self._cursor.close()


class _MySQLConnection:
    def __init__(self, conn): self._conn = conn
    def cursor(self): return _MySQLCursor(self._conn.cursor(dictionary=True))
    def commit(self): self._conn.commit()
    def rollback(self): self._conn.rollback()
    def close(self): self._conn.close()


def _mysql_config():
    if DATABASE_URL.startswith("mysql"):
        parsed = urlparse(DATABASE_URL)
        return {"host": parsed.hostname, "port": parsed.port or 3306,
                "user": unquote(parsed.username or ""), "password": unquote(parsed.password or ""),
                "database": parsed.path.lstrip("/")}
    return {"host": os.environ["MYSQL_HOST"], "port": int(os.getenv("MYSQL_PORT", "3306")),
            "user": os.environ["MYSQL_USER"], "password": os.environ["MYSQL_PASSWORD"],
            "database": os.environ["MYSQL_DATABASE"]}


def get_db_connection():
    if USING_MYSQL:
        import mysql.connector
        return _MySQLConnection(mysql.connector.connect(**_mysql_config(), connection_timeout=5))
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _dict(row): return dict(row) if row else None
def _count(row): return row["count"] if isinstance(row, dict) else row[0]


def init_db():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        schema = (Path(__file__).with_name("schema.mysql.sql") if USING_MYSQL else Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
        if USING_MYSQL:
            for statement in schema.split(";"):
                if statement.strip(): cursor.execute(statement)
        else:
            cursor.executescript(schema)
            try:
                cursor.execute("ALTER TABLE incidents ADD COLUMN route_geometry TEXT")
            except Exception:
                pass
        cursor.execute("SELECT COUNT(*) AS count FROM hospitals")
        if _count(cursor.fetchone()) == 0:
            cursor.executemany("INSERT INTO hospitals (name, capability, emergency_ready, lat, lng, bed_status, phone) VALUES (?, ?, ?, ?, ?, ?, ?)", [
                ("Enugu State University Teaching Hospital (ESUT Parklane)", "trauma", 1, 6.4541, 7.5248, "unverified", None),
                ("National Orthopaedic Hospital Enugu (NOHE)", "orthopaedic", 1, 6.4418, 7.4985, "unverified", None),
                ("University of Nigeria Teaching Hospital (UNTH Ituku-Ozalla)", "trauma", 1, 6.3125, 7.4764, "unverified", None),
                ("Park Lane General Hospital Emergency Wing", "general", 1, 6.4622, 7.5106, "unverified", None),
            ])
        cursor.execute("SELECT COUNT(*) AS count FROM responders")
        if _count(cursor.fetchone()) == 0:
            cursor.executemany("INSERT INTO responders (unit_code, name, type, status, lat, lng, heading, speed_kmh, battery_level, assigned_incident_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                ("AMB-01", "Ambulance Unit 01 (Enugu Urban)", "ambulance", "idle", 6.4480, 7.5150, 45.0, 0.0, 95, None),
                ("AMB-02", "Ambulance Unit 02 (9th Mile Rapid)", "ambulance", "idle", 6.4320, 7.4100, 180.0, 0.0, 88, None),
                ("RESCUE-01", "Emergency Rescue Crew 01", "rescue_truck", "idle", 6.4590, 7.5320, 90.0, 0.0, 100, None),
            ])
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cursor.close(); conn.close()


def _query_all(query, params=()):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute(query, params); return [_dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close(); conn.close()


def get_hospitals(capability=None):
    return _query_all("SELECT * FROM hospitals WHERE capability = ? ORDER BY id ASC", (capability,)) if capability else _query_all("SELECT * FROM hospitals ORDER BY id ASC")
def get_responders(): return _query_all("SELECT * FROM responders ORDER BY unit_code ASC")


def get_responder_by_code(unit_code):
    rows = _query_all("SELECT * FROM responders WHERE unit_code = ?", (unit_code,)); return rows[0] if rows else None
def get_incident_by_uuid(incident_uuid):
    rows = _query_all("SELECT * FROM incidents WHERE incident_uuid = ?", (incident_uuid,)); return rows[0] if rows else None
def get_incidents(status=None, limit=50):
    return _query_all("SELECT * FROM incidents WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)) if status else _query_all("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))


def update_responder_status(unit_code, status, incident_id=None):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("UPDATE responders SET status = ?, assigned_incident_id = ?, last_beacon = CURRENT_TIMESTAMP WHERE unit_code = ?", (status, incident_id, unit_code))
        conn.commit(); return cursor.rowcount == 1
    finally:
        cursor.close(); conn.close()


def update_responder_telemetry(unit_code, lat, lng, heading=0.0, speed_kmh=0.0):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("UPDATE responders SET lat = ?, lng = ?, heading = ?, speed_kmh = ?, last_beacon = CURRENT_TIMESTAMP WHERE unit_code = ?", (lat, lng, heading, speed_kmh, unit_code))
        conn.commit(); return cursor.rowcount == 1
    finally:
        cursor.close(); conn.close()


def create_incident(data):
    incident_uuid = data.get("incident_uuid") or f"INC-{uuid.uuid4().hex[:12].upper()}"
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("""INSERT INTO incidents (incident_uuid, title, type, status, severity_level, severity_score, escalation_status, lat, lng, location_name, casualties_count, trapped_count, assigned_responder_id, recommended_hospital_id, route_geometry, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""", (
            incident_uuid, data.get("title", "Emergency Incident"), data.get("type", "road_traffic_accident"), data.get("status", "reported"), data.get("severity_level", "moderate"), data.get("severity_score", 2.5), data.get("escalation_status", "steady"), data.get("lat"), data.get("lng"), data.get("location_name", "Location pending"), data.get("casualties_count", 1), data.get("trapped_count", 0), data.get("assigned_responder_id"), data.get("recommended_hospital_id"), data.get("route_geometry")))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cursor.close(); conn.close()
    return get_incident_by_uuid(incident_uuid)


def update_incident(incident_uuid, updates):
    allowed = {"status", "severity_level", "severity_score", "escalation_status", "casualties_count", "trapped_count", "assigned_responder_id", "recommended_hospital_id", "location_name", "title", "lat", "lng", "route_geometry"}
    fields, values = [], []
    for key, value in updates.items():
        if key in allowed: fields.append(f"{key} = ?"); values.append(value)
    if not fields: return None
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        fields.append("updated_at = CURRENT_TIMESTAMP"); values.append(incident_uuid)
        cursor.execute(f"UPDATE incidents SET {', '.join(fields)} WHERE incident_uuid = ?", values)
        if cursor.rowcount != 1: conn.rollback(); return None
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cursor.close(); conn.close()
    return get_incident_by_uuid(incident_uuid)


def get_incident_conversation(incident_uuid):
    """Returns civilian chat messages, dispatcher direct messages, and AI responses for an incident in order."""
    rows = _query_all(
        "SELECT * FROM incident_updates WHERE incident_uuid = ? AND (source IN ('civilian', 'dispatcher', 'ai_system') OR update_type IN ('chat', 'triage', 'direct_message', 'route_change')) ORDER BY id ASC",
        (incident_uuid,)
    )
    for row in rows:
        try: row["metadata"] = json.loads(row["metadata_json"]) if row.get("metadata_json") else None
        except (TypeError, json.JSONDecodeError): row["metadata"] = None
    return rows


def assign_responder_to_incident(incident_uuid, unit_code):
    """Transactional, idempotent assignment with an availability re-check."""
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        if not USING_MYSQL: cursor.execute("BEGIN IMMEDIATE")
        lock = " FOR UPDATE" if USING_MYSQL else ""
        cursor.execute(f"SELECT * FROM incidents WHERE incident_uuid = ?{lock}", (incident_uuid,)); incident = _dict(cursor.fetchone())
        cursor.execute(f"SELECT * FROM responders WHERE unit_code = ?{lock}", (unit_code,)); responder = _dict(cursor.fetchone())
        if not incident or not responder: conn.rollback(); return None, None, "not_found"
        if incident["status"] in ("resolved", "cancelled"): conn.rollback(); return None, None, "incident_closed"
        if incident.get("assigned_responder_id") and incident["assigned_responder_id"] != unit_code: conn.rollback(); return None, None, "incident_already_assigned"
        if responder["status"] not in ("idle", "assigned") or (responder.get("assigned_incident_id") and responder["assigned_incident_id"] != incident_uuid): conn.rollback(); return None, None, "responder_unavailable"
        cursor.execute("UPDATE responders SET status = ?, assigned_incident_id = ?, last_beacon = CURRENT_TIMESTAMP WHERE unit_code = ?", ("assigned", incident_uuid, unit_code))
        cursor.execute("UPDATE incidents SET status = ?, assigned_responder_id = ?, updated_at = CURRENT_TIMESTAMP WHERE incident_uuid = ?", ("dispatched", unit_code, incident_uuid))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cursor.close(); conn.close()
    return get_incident_by_uuid(incident_uuid), get_responder_by_code(unit_code), None


def add_incident_update(incident_uuid, source, content, update_type="chat", metadata=None):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO incident_updates (incident_uuid, source, update_type, content, metadata_json) VALUES (?, ?, ?, ?, ?)", (incident_uuid, source, update_type, content, json.dumps(metadata) if metadata else None)); conn.commit()
    finally:
        cursor.close(); conn.close()


def get_incident_updates(incident_uuid):
    rows = _query_all("SELECT * FROM incident_updates WHERE incident_uuid = ? ORDER BY id ASC", (incident_uuid,))
    for row in rows:
        try: row["metadata"] = json.loads(row["metadata_json"]) if row.get("metadata_json") else None
        except (TypeError, json.JSONDecodeError): row["metadata"] = None
    return rows


def add_scene_hazard(incident_uuid, hazard_type, severity="high", description=None, photo_url=None):
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO scene_hazards (incident_uuid, hazard_type, severity, description, photo_url) VALUES (?, ?, ?, ?, ?)", (incident_uuid, hazard_type, severity, description, photo_url)); conn.commit()
    finally:
        cursor.close(); conn.close()


def get_scene_hazards(incident_uuid): return _query_all("SELECT * FROM scene_hazards WHERE incident_uuid = ? ORDER BY id DESC", (incident_uuid,))
