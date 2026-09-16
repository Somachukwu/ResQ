from flask import request
from flask_socketio import emit, join_room, leave_room
from .database import (
    create_incident,
    update_incident,
    add_incident_update,
    get_incident_by_uuid,
    get_incident_updates,
    get_scene_hazards,
    update_responder_status,
    update_responder_telemetry,
    get_responder_by_code
)
from .synthetic_injector import inject_expressway_crash, inject_urban_flood

def register_socket_events(socketio):
    
    @socketio.on("connect")
    def handle_connect():
        print(f"[WebSocket] Client connected: {request.sid}")
        emit("connection:acknowledged", {"status": "connected", "sid": request.sid})

    @socketio.on("disconnect")
    def handle_disconnect():
        print(f"[WebSocket] Client disconnected: {request.sid}")

    @socketio.on("join")
    def handle_join(data):
        room = data.get("room")
        if room:
            join_room(room)
            print(f"[WebSocket] Client {request.sid} joined room: {room}")
            emit("room:joined", {"room": room}, to=request.sid)

    @socketio.on("leave")
    def handle_leave(data):
        room = data.get("room")
        if room:
            leave_room(room)
            print(f"[WebSocket] Client {request.sid} left room: {room}")

    @socketio.on("incident:create")
    def handle_incident_create(data):
        """Civilian creates a new emergency incident"""
        import uuid
        incident_uuid = data.get("incident_uuid") or f"INC-{uuid.uuid4().hex[:8].upper()}"
        data["incident_uuid"] = incident_uuid
        incident = create_incident(data)
        
        # Broadcast to dispatchers room and incident room
        emit("incident:new", incident, room="dispatchers")
        emit("incident:created", incident, to=request.sid)
        print(f"[WebSocket] Incident created: {incident_uuid}")

    @socketio.on("incident:msg")
    def handle_incident_message(data):
        """Civilian or AI sends a chat update to the incident timeline"""
        incident_uuid = data.get("incident_uuid")
        source = data.get("source", "civilian")
        content = data.get("content", "")
        update_type = data.get("update_type", "chat")
        metadata = data.get("metadata")

        if incident_uuid and content:
            add_incident_update(incident_uuid, source, content, update_type, metadata)
            update_payload = {
                "incident_uuid": incident_uuid,
                "source": source,
                "content": content,
                "update_type": update_type,
                "metadata": metadata
            }
            # Broadcast to everyone viewing this incident and dispatchers
            emit("incident:update_received", update_payload, room=f"incident_{incident_uuid}")
            emit("incident:timeline_update", update_payload, room="dispatchers")

    @socketio.on("responder:assign")
    def handle_responder_assign(data):
        """Dispatcher assigns a responder to an incident"""
        incident_uuid = data.get("incident_uuid")
        unit_code = data.get("unit_code")

        if incident_uuid and unit_code:
            update_incident(incident_uuid, {"assigned_responder_id": unit_code, "status": "dispatched"})
            update_responder_status(unit_code, "assigned", incident_uuid)
            
            payload = {
                "incident_uuid": incident_uuid,
                "unit_code": unit_code,
                "status": "dispatched"
            }
            emit("responder:assigned", payload, room="dispatchers")
            emit("responder:assigned", payload, room=f"incident_{incident_uuid}")
            emit("responder:mission_alert", payload, room=f"responder_{unit_code}")
            print(f"[WebSocket] Assigned {unit_code} to {incident_uuid}")

    @socketio.on("responder:telemetry")
    def handle_responder_telemetry(data):
        """Responder broadcasts 15-second GPS position and telemetry"""
        unit_code = data.get("unit_code")
        lat = data.get("lat")
        lng = data.get("lng")
        heading = data.get("heading", 0.0)
        speed_kmh = data.get("speed_kmh", 0.0)

        if unit_code and lat is not None and lng is not None:
            update_responder_telemetry(unit_code, lat, lng, heading, speed_kmh)
            payload = {
                "unit_code": unit_code,
                "lat": lat,
                "lng": lng,
                "heading": heading,
                "speed_kmh": speed_kmh
            }
            emit("telemetry:update", payload, room="dispatchers")

    @socketio.on("demo:inject")
    def handle_demo_inject(data):
        """Synthetic incident injection trigger"""
        scenario = data.get("scenario", "crash")
        if scenario == "flood":
            incident = inject_urban_flood()
        else:
            incident = inject_expressway_crash()
            
        emit("incident:new", incident, room="dispatchers")
        emit("demo:injected", incident, to=request.sid)
        print(f"[WebSocket] Synthetic demo injected: {incident['incident_uuid']}")

