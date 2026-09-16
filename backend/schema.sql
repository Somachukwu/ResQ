-- ResQ Relational Database Schema
-- Compatible with MySQL 8.4 and SQLite 3
-- Target: Incident Management, Telemetry Tracking, and Audit Trails

CREATE TABLE IF NOT EXISTS hospitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    capability VARCHAR(100) NOT NULL DEFAULT 'general',
    emergency_ready BOOLEAN NOT NULL DEFAULT 1,
    lat DECIMAL(10, 7) NOT NULL,
    lng DECIMAL(10, 7) NOT NULL,
    bed_status VARCHAR(50) DEFAULT 'available',
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS responders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'ambulance',
    status VARCHAR(50) NOT NULL DEFAULT 'idle', -- idle, assigned, en_route, on_scene
    lat DECIMAL(10, 7),
    lng DECIMAL(10, 7),
    heading DECIMAL(5, 2) DEFAULT 0.0,
    speed_kmh DECIMAL(5, 2) DEFAULT 0.0,
    battery_level INTEGER DEFAULT 100,
    assigned_incident_id VARCHAR(64),
    last_beacon TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_uuid VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL DEFAULT 'road_traffic_accident', -- road_traffic_accident, urban_flood, fire, collapse, medical
    status VARCHAR(50) NOT NULL DEFAULT 'reported', -- reported, triaged, dispatched, en_route, on_scene, resolved
    severity_level VARCHAR(50) NOT NULL DEFAULT 'moderate', -- low, moderate, urgent, critical
    severity_score DECIMAL(3, 1) DEFAULT 2.5, -- 1.0 to 5.0 (ResQ Severity Index)
    escalation_status VARCHAR(50) DEFAULT 'steady', -- escalating, steady, de_escalating
    lat DECIMAL(10, 7) NOT NULL,
    lng DECIMAL(10, 7) NOT NULL,
    location_name VARCHAR(255),
    casualties_count INTEGER DEFAULT 1,
    trapped_count INTEGER DEFAULT 0,
    assigned_responder_id VARCHAR(50),
    recommended_hospital_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incident_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_uuid VARCHAR(64) NOT NULL,
    source VARCHAR(50) NOT NULL, -- civilian, dispatcher, responder, ai_system, cv_model
    update_type VARCHAR(50) NOT NULL DEFAULT 'chat', -- chat, triage, dispatch, hazard, telemetry
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scene_hazards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_uuid VARCHAR(64) NOT NULL,
    hazard_type VARCHAR(100) NOT NULL, -- flood_water, live_wire, fuel_leak, structural_collapse, aggressive_crowd
    severity VARCHAR(50) DEFAULT 'high',
    description TEXT,
    photo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

