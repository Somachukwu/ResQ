import os
from flask import request
from flask_socketio import emit, join_room, leave_room
from .database import (
    create_incident,
    update_incident,
    add_incident_update,
    get_incident_by_uuid,
    get_incident_updates,
    get_scene_hazards,
    update_responder_telemetry,
    assign_responder_to_incident,
    update_responder_status
)
from .synthetic_injector import inject_expressway_crash, inject_urban_flood
from .security import AUTH_REQUIRED, role_from_socket_auth

def register_socket_events(socketio):
    connection_roles = {}
    
    @socketio.on("connect")
    def handle_connect(auth=None):
        role = role_from_socket_auth(auth)
        if role is None:
            return False
        connection_roles[request.sid] = role
        print(f"[WebSocket] Client connected: {request.sid}")
        emit("connection:acknowledged", {"status": "connected", "sid": request.sid})

    @socketio.on("disconnect")
    def handle_disconnect():
        connection_roles.pop(request.sid, None)
        print(f"[WebSocket] Client disconnected: {request.sid}")

    @socketio.on("join")
    def handle_join(data):
        room = data.get("room")
        role = connection_roles.get(request.sid, "civilian")
        allowed = (
            (room == "dispatchers" and role in ("dispatcher", "development")) or
            (room == "responders" and role in ("responder", "development")) or
            (room == "civilians") or
            (room and room.startswith("responder_") and role in ("responder", "development")) or
            (room and room.startswith("incident_"))
        )
        if room and allowed:
            join_room(room)
            print(f"[WebSocket] Client {request.sid} ({role}) joined room: {room}")
            emit("room:joined", {"room": room}, to=request.sid)
        elif room:
            emit("error", {"error": "Room access denied"}, to=request.sid)

    @socketio.on("leave")
    def handle_leave(data):
        room = data.get("room")
        if room:
            leave_room(room)
            print(f"[WebSocket] Client {request.sid} left room: {room}")

    @socketio.on("incident:create")
    def handle_incident_create(data):
        """Civilian creates a new emergency incident"""
        if AUTH_REQUIRED:
            emit("error", {"error": "Use the protected HTTP SOS endpoint"}, to=request.sid)
            return
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
        if AUTH_REQUIRED:
            emit("error", {"error": "Use the protected HTTP SOS endpoint"}, to=request.sid)
            return
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
        if connection_roles.get(request.sid) not in ("dispatcher", "development"):
            emit("error", {"error": "Dispatcher role required"}, to=request.sid)
            return
        incident_uuid = data.get("incident_uuid")
        unit_code = data.get("unit_code")

        if incident_uuid and unit_code:
            incident, responder, assignment_error = assign_responder_to_incident(incident_uuid, unit_code)
            if assignment_error:
                emit("error", {"error": assignment_error}, to=request.sid)
                return
            
            payload = {
                "incident_uuid": incident_uuid,
                "unit_code": unit_code,
                "status": "dispatched",
                "eta_minutes": 8,
                "eta_seconds": 480
            }
            emit("responder:assigned", payload, room="dispatchers")
            emit("responder:assigned", payload, room=f"incident_{incident_uuid}")
            emit("civilian:dispatch_confirmed", payload, room=f"incident_{incident_uuid}")
            emit("responder:mission_alert", payload, room=f"responder_{unit_code}")
            print(f"[WebSocket] Assigned {unit_code} to {incident_uuid}")

    @socketio.on("responder:status")
    def handle_responder_status(data):
        """Responder transitions stage (e.g. enroute, on_scene, transport, complete)"""
        if connection_roles.get(request.sid) not in ("responder", "development"):
            emit("error", {"error": "Responder role required"}, to=request.sid)
            return
        unit_code = data.get("unit_code")
        status = (data.get("status") or data.get("stage") or "").strip().lower()
        incident_uuid = data.get("incident_uuid")
        if unit_code and status:
            update_responder_status(unit_code, status, incident_uuid)
            payload = {
                "unit_code": unit_code,
                "status": status,
                "incident_uuid": incident_uuid
            }
            emit("responder:status_update", payload, room="dispatchers")
            emit("responder:status_update", payload, room="responders")
            if status in ("scene", "on_scene"):
                emit("responder:on_scene", payload, room="dispatchers")
                if incident_uuid:
                    emit("responder:on_scene", payload, room=f"incident_{incident_uuid}")
                emit("responder:on_scene", payload, room="civilians")

    @socketio.on("responder:telemetry")
    def handle_responder_telemetry(data):
        """Responder broadcasts 15-second GPS position and telemetry"""
        if connection_roles.get(request.sid) not in ("responder", "development"):
            emit("error", {"error": "Responder role required"}, to=request.sid)
            return
        unit_code = data.get("unit_code")
        lat = data.get("lat")
        lng = data.get("lng")
        heading = data.get("heading", 0.0)
        speed_kmh = data.get("speed_kmh", 0.0)

        if unit_code and lat is not None and lng is not None:
            if not update_responder_telemetry(unit_code, lat, lng, heading, speed_kmh):
                emit("error", {"error": "Responder not found"}, to=request.sid)
                return
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
        if connection_roles.get(request.sid) not in ("dispatcher", "development"):
            emit("error", {"error": "Dispatcher role required"}, to=request.sid)
            return
        if AUTH_REQUIRED and os.getenv("RESQ_ENABLE_DEMO", "0").lower() not in ("1", "true", "yes"):
            emit("error", {"error": "Synthetic scenarios are disabled"}, to=request.sid)
            return
        scenario = data.get("scenario", "crash")
        if scenario == "flood":
            incident = inject_urban_flood()
        else:
            incident = inject_expressway_crash()
            
        emit("incident:new", incident, room="dispatchers")
        emit("demo:injected", incident, to=request.sid)
        print(f"[WebSocket] Synthetic demo injected: {incident['incident_uuid']}")

    @socketio.on("webrtc:signal")
    def handle_webrtc_signal(data):
        incident_uuid = data.get("incident_uuid") or "default"
        emit("webrtc:signal", data, broadcast=True, include_self=False)
        print(f"[WebSocket] WebRTC signal relayed: {data.get('type')} from {data.get('from')} for {incident_uuid}")

    @socketio.on("call_bridge:event")
    def handle_call_bridge_event(data):
        incident_uuid = data.get("incident_uuid") or "default"
        emit("call_bridge:event", data, broadcast=True, include_self=False)
        print(f"[WebSocket] Call bridge event relayed: {data.get('action')} from {data.get('caller')} for {incident_uuid}")

    @socketio.on("responder:message")
    def handle_responder_message(data):
        incident_uuid = data.get("incident_uuid")
        unit_code = data.get("unit_code", "AMB-01")
        message = data.get("message", "")
        payload = {
            "incident_uuid": incident_uuid,
            "unit_code": unit_code,
            "sender": f"Unit {unit_code}",
            "message": message,
            "timestamp": time.time()
        }
        emit("responder:message", payload, room="dispatchers")
        emit("responder:message", payload, room="responders")
        if incident_uuid:
            emit("responder:message", payload, room=f"incident_{incident_uuid}")

