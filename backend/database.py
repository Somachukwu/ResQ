import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resq.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    cursor.executescript(schema_sql)
    
    # Check if hospitals need initial seeding
    cursor.execute("SELECT COUNT(*) FROM hospitals")
    if cursor.fetchone()[0] == 0:
        seed_hospitals = [
            ("Enugu State University Teaching Hospital (ESUT Parklane)", "trauma", 1, 6.4541, 7.5248, "available", "+2348030000001"),
            ("National Orthopaedic Hospital Enugu (NOHE)", "orthopaedic", 1, 6.4418, 7.4985, "available", "+2348030000002"),
            ("University of Nigeria Teaching Hospital (UNTH Ituku-Ozalla)", "trauma", 1, 6.3125, 7.4764, "available", "+2348030000003"),
            ("Park Lane General Hospital Emergency Wing", "general", 1, 6.4622, 7.5106, "available", "+2348030000004"),
            ("Mother of Christ Specialist Hospital, Ogui", "general", 1, 6.4385, 7.4942, "available", "+2348030000005"),
            ("Annunciation Specialist Hospital, Emene", "general", 1, 6.4690, 7.5610, "available", "+2348030000006"),
            ("Lagos University Teaching Hospital (LUTH Idi-Araba)", "trauma", 1, 6.5240, 3.3560, "available", "+2348030000010"),
            ("Lagos State University Teaching Hospital (LASUTH Ikeja)", "trauma", 1, 6.5950, 3.3480, "available", "+2348030000011"),
            ("National Orthopaedic Hospital Igbobi, Lagos", "orthopaedic", 1, 6.5350, 3.3720, "available", "+2348030000012"),
            ("General Hospital Marina, Lagos Island", "general", 1, 6.4510, 3.3980, "available", "+2348030000013")
        ]
        cursor.executemany(
            "INSERT INTO hospitals (name, capability, emergency_ready, lat, lng, bed_status, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            seed_hospitals
        )
    
    # Check if responders need initial seeding
    cursor.execute("SELECT COUNT(*) FROM responders")
    if cursor.fetchone()[0] == 0:
        seed_responders = [
            ("AMB-01", "Ambulance Unit 01 (Enugu Urban)", "ambulance", "idle", 6.4480, 7.5150, 45.0, 0.0, 95, None),
            ("AMB-02", "Ambulance Unit 02 (9th Mile Rapid)", "ambulance", "idle", 6.4320, 7.4100, 180.0, 0.0, 88, None),
            ("RESCUE-01", "Emergency Rescue Crew 01", "rescue_truck", "idle", 6.4590, 7.5320, 90.0, 0.0, 100, None)
        ]
        cursor.executemany(
            "INSERT INTO responders (unit_code, name, type, status, lat, lng, heading, speed_kmh, battery_level, assigned_incident_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            seed_responders
        )
        
    conn.commit()
    conn.close()

# --- Repository Functions ---

def get_hospitals(capability=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if capability:
        cursor.execute("SELECT * FROM hospitals WHERE capability = ? ORDER BY id ASC", (capability,))
    else:
        cursor.execute("SELECT * FROM hospitals ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_responders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM responders ORDER BY unit_code ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_responder_by_code(unit_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM responders WHERE unit_code = ?", (unit_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_responder_status(unit_code, status, incident_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE responders SET status = ?, assigned_incident_id = ?, last_beacon = CURRENT_TIMESTAMP WHERE unit_code = ?",
        (status, incident_id, unit_code)
    )
    conn.commit()
    conn.close()

def update_responder_telemetry(unit_code, lat, lng, heading=0.0, speed_kmh=0.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE responders SET lat = ?, lng = ?, heading = ?, speed_kmh = ?, last_beacon = CURRENT_TIMESTAMP WHERE unit_code = ?",
        (lat, lng, heading, speed_kmh, unit_code)
    )
    conn.commit()
    conn.close()

def create_incident(data):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO incidents (
            incident_uuid, title, type, status, severity_level, severity_score, 
            escalation_status, lat, lng, location_name, casualties_count, trapped_count, 
            assigned_responder_id, recommended_hospital_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            data.get("incident_uuid"),
            data.get("title", "Emergency Incident"),
            data.get("type", "road_traffic_accident"),
            data.get("status", "reported"),
            data.get("severity_level", "moderate"),
            data.get("severity_score", 2.5),
            data.get("escalation_status", "steady"),
            data.get("lat"),
            data.get("lng"),
            data.get("location_name", "Enugu"),
            data.get("casualties_count", 1),
            data.get("trapped_count", 0),
            data.get("assigned_responder_id"),
            data.get("recommended_hospital_id")
        )
    )
    conn.commit()
    conn.close()
    return get_incident_by_uuid(data.get("incident_uuid"))

def get_incidents(status=None, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM incidents WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
    else:
        cursor.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_incident_by_uuid(incident_uuid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE incident_uuid = ?", (incident_uuid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_incident(incident_uuid, updates: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fields = []
    values = []
    for k, v in updates.items():
        if k in ("status", "severity_level", "severity_score", "escalation_status", 
                 "casualties_count", "trapped_count", "assigned_responder_id", 
                 "recommended_hospital_id", "location_name", "title"):
            fields.append(f"{k} = ?")
            values.append(v)
            
    if not fields:
        conn.close()
        return None
        
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(incident_uuid)
    query = f"UPDATE incidents SET {', '.join(fields)} WHERE incident_uuid = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return get_incident_by_uuid(incident_uuid)

def add_incident_update(incident_uuid, source, content, update_type="chat", metadata=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    meta_str = json.dumps(metadata) if metadata else None
    cursor.execute(
        "INSERT INTO incident_updates (incident_uuid, source, update_type, content, metadata_json) VALUES (?, ?, ?, ?, ?)",
        (incident_uuid, source, update_type, content, meta_str)
    )
    conn.commit()
    conn.close()

def get_incident_updates(incident_uuid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM incident_updates WHERE incident_uuid = ? ORDER BY id ASC",
        (incident_uuid,)
    )
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        if d.get("metadata_json"):
            try:
                d["metadata"] = json.loads(d["metadata_json"])
            except:
                d["metadata"] = None
        results.append(d)
    return results

def add_scene_hazard(incident_uuid, hazard_type, severity="high", description=None, photo_url=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scene_hazards (incident_uuid, hazard_type, severity, description, photo_url) VALUES (?, ?, ?, ?, ?)",
        (incident_uuid, hazard_type, severity, description, photo_url)
    )
    conn.commit()
    conn.close()

def get_scene_hazards(incident_uuid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM scene_hazards WHERE incident_uuid = ? ORDER BY id DESC",
        (incident_uuid,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

