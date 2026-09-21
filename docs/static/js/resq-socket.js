/**
 * ResQ Real-Time WebSocket Client Helper
 * Establishes persistent connection and dispatches custom events
 */

class ResQSocket {
    constructor(role = "civilian", metadata = {}) {
        this.role = role;
        this.metadata = metadata;
        this.socket = null;
        this.connected = false;
        this.eventListeners = new Map();
        
        this.init();
    }

    init() {
        if (typeof io === "undefined") {
            console.warn("[ResQSocket] socket.io client library not loaded. Falling back to HTTP polling.");
            return;
        }

        const serverUrl = window.RESQ_CONFIG?.backendUrl || undefined;
        this.socket = io(serverUrl, {
            transports: ["websocket", "polling"],
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 1000
        });

        this.socket.on("connect", () => {
            this.connected = true;
            console.log(`[ResQSocket] Connected to real-time bus as ${this.role}`);
            
            // Join role-based room
            if (this.role === "dispatcher") {
                this.socket.emit("join", { room: "dispatchers" });
            } else if (this.role === "responder" && this.metadata.unitCode) {
                this.socket.emit("join", { room: `responder_${this.metadata.unitCode}` });
            } else if (this.role === "civilian" && this.metadata.incidentUuid) {
                this.socket.emit("join", { room: `incident_${this.metadata.incidentUuid}` });
            }

            this.trigger("connected", { sid: this.socket.id });
        });

        this.socket.on("disconnect", () => {
            this.connected = false;
            console.log("[ResQSocket] Disconnected from bus");
            this.trigger("disconnected", {});
        });

        // Forward server events to local listeners
        const standardEvents = [
            "incident:new", 
            "incident:created", 
            "incident:update_received", 
            "incident:timeline_update", 
            "responder:assigned", 
            "responder:mission_alert", 
            "telemetry:update", 
            "demo:injected"
        ];

        standardEvents.forEach(evtName => {
            this.socket.on(evtName, (payload) => {
                console.log(`[ResQSocket] Event received [${evtName}]:`, payload);
                this.trigger(evtName, payload);
            });
        });
    }

    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }

    trigger(event, data) {
        if (this.eventListeners.has(event)) {
            this.eventListeners.get(event).forEach(cb => cb(data));
        }
    }

    emit(event, data) {
        if (this.socket && this.connected) {
            this.socket.emit(event, data);
        } else {
            console.warn(`[ResQSocket] Cannot emit [${event}], socket not connected.`);
        }
    }

    joinIncidentRoom(incidentUuid) {
        if (this.socket) {
            this.socket.emit("join", { room: `incident_${incidentUuid}` });
        }
    }

    broadcastTelemetry(unitCode, lat, lng, heading = 0, speedKmh = 0) {
        this.emit("responder:telemetry", {
            unit_code: unitCode,
            lat: lat,
            lng: lng,
            heading: heading,
            speed_kmh: speedKmh
        });
    }

    injectDemo(scenario = "crash") {
        this.emit("demo:inject", { scenario });
    }
}

// Global accessor
window.ResQSocket = ResQSocket;

