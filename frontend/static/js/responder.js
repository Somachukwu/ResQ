/* Responder tactical cockpit brief — dynamic telemetry, stage control, navigation, multi-pane & mobile view */
import "./resq-theme.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Extract target incident uuid and assigned unit from URL query or defaults
const urlParams = new URLSearchParams(window.location.search);
let activeIncidentUuid = urlParams.get("incident") || urlParams.get("id");
let assignedUnitCode = urlParams.get("unit") || "AMB-01";

let incidentState = {
  id: activeIncidentUuid || "Awaiting Assignment",
  title: "Emergency Mission Standby",
  coords: { lat: 6.4480, lng: 7.5150 },
  place: "Enugu Urban Corridor",
  severity: "urgent",
  rsi: 3.5,
  tier: "P2",
  casualties: 1,
  hazards: [],
  trauma: [],
  completed_steps: [],
  hospital: {
    name: "ESUTH Parklane (Level-1 Trauma)",
    eta: "8 min from scene",
    tier: "Level 1 trauma",
    caps: ["Level 1 trauma", "ICU bed held", "Blood bank ready"]
  }
};

const el = {
  telemetry: $("#telemetry"),
  beat: $("#beat"),
  log: $("#statuslog"),
  navigate: $("#navigate"),
  call: $("#callCivilian"),
  mobileNavBtn: $("#mobileNavBtn"),
  mobileCallBtn: $("#mobileCallBtn"),
  arrivalCountdown: $("#arrivalCountdown"),
  mobileEta: $("#mobileEta"),
  ackBtn: $("#ackBriefBtn"),
  ackText: $("#ackBtnText"),
  lastRadioUpdate: $("#lastRadioUpdate"),
  fullscreenBtn: $("#fullscreenBtn"),
  workspace: $("#responderWorkspace"),
  incidentTitle: $(".mission__trauma"),
  incidentPlace: $(".mission__where span"),
  incidentBadge: $(".r-card--incident .badge"),
  briefTriageBadge: $("#briefTriageBadge"),
  mobileStripTitle: $(".m-strip__title"),
  mobileVictimCount: $(".m-strip__metrics .m-metric:nth-child(2) .m-metric__val"),
  victimCounterBadge: $(".victim-count-badge"),
  victimCounterStatus: $(".victim-counter-status"),
  victimCounterSub: $(".victim-counter-sub"),
  alertsGroup: $(".alerts-group"),
  doneList: $(".done-list"),
  hospitalName: $(".destination__name"),
  hospitalEta: $(".destination__eta"),
  hospitalCaps: $(".destination__caps"),
};

/* ---------------- arrival countdown ticker ---------------- */
let arrivalSeconds = 0;
function tickArrival() {
  if (arrivalSeconds > 0) {
    arrivalSeconds -= 1;
    const m = Math.floor(arrivalSeconds / 60);
    const s = arrivalSeconds % 60;
    const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = timeStr;
    if (el.mobileEta) el.mobileEta.textContent = timeStr;
  } else if (arrivalSeconds === 0 && incidentState.id !== "Awaiting Assignment") {
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = "00:00";
    if (el.mobileEta) el.mobileEta.textContent = "00:00";
  }
}
setInterval(tickArrival, 1000);

/* ---------------- radio sync ticker ---------------- */
let radioElapsed = 0;
function tickRadio() {
  radioElapsed += 1;
  if (el.lastRadioUpdate) {
    if (radioElapsed < 60) {
      el.lastRadioUpdate.textContent = `Updated ${radioElapsed}s ago`;
    } else {
      el.lastRadioUpdate.textContent = `Updated ${Math.floor(radioElapsed / 60)}m ago`;
    }
  }
}
setInterval(tickRadio, 1000);

/* ---------------- acknowledge brief toggle ---------------- */
let isAcked = false;
if (el.ackBtn) {
  el.ackBtn.addEventListener("click", async () => {
    if (!activeIncidentUuid || activeIncidentUuid === "Awaiting Assignment") {
      logLine("No active mission", "Awaiting commander dispatch approval");
      return;
    }
    try {
      const response = await fetch(`/api/incidents/${activeIncidentUuid}/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ unit_code: assignedUnitCode })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      
      isAcked = true;
      el.ackBtn.classList.add("is-acked");
      if (el.ackText) el.ackText.textContent = "Brief Acknowledged · Rolling";
      logLine("Brief acknowledged by unit", "Live ETA & dispatch broadcast to civilian");
      radioElapsed = 0;
      if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
    } catch (error) {
      logLine("Acknowledgement error", error.message);
    }
  });
}

/* ---------------- telemetry heartbeat: broadcast GPS every 10 s ---------------- */
let beats = 0;
let currentCoords = { lat: 6.4480, lng: 7.5150 };

function broadcastTelemetry() {
  beats += 1;
  radioElapsed = 0;
  const t = new Date();
  if (el.beat) {
    el.beat.textContent = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}:${String(
      t.getSeconds()
    ).padStart(2, "0")}`;
  }
  if (el.telemetry) {
    el.telemetry.animate(
      [{ opacity: 1 }, { opacity: 0.45 }, { opacity: 1 }],
      { duration: 600, easing: "ease-out" }
    );
  }

  fetch("/api/responder-telemetry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      unit_code: assignedUnitCode,
      lat: currentCoords.lat,
      lng: currentCoords.lng,
      heading: 45.0,
      speed_kmh: 48.0
    })
  }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (beats % 4 === 0) logLine("Position beacon transmitted", "Server confirmed");
  }).catch(() => {});
}

if ("geolocation" in navigator) {
  navigator.geolocation.watchPosition(
    (pos) => {
      currentCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    },
    () => {},
    { enableHighAccuracy: true, maximumAge: 10000 }
  );
}
broadcastTelemetry();
setInterval(broadcastTelemetry, 10000);

/* ---------------- Leaflet map for responder route ---------------- */
let responderMap = null;
let responderMarker = null;
let incidentMarker = null;
let responderRouteLayer = null;

function initResponderMap(centerLat, centerLng) {
  const mapDiv = document.getElementById("responderMap");
  if (!mapDiv || responderMap) return;
  responderMap = L.map("responderMap", { zoomControl: true, attributionControl: false })
    .setView([centerLat || 6.4480, centerLng || 7.5150], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(responderMap);
  
  responderMarker = L.marker([centerLat || 6.4480, centerLng || 7.5150], {
    icon: L.divIcon({ className: "", html: '<span class="pin pin--responder pin--pulse"></span>', iconSize: [22, 22] })
  }).bindTooltip(`${assignedUnitCode} (You)`, { direction: "top" }).addTo(responderMap);
}

function drawMissionRoute(geometry, incLat, incLng, hospitalName) {
  if (!responderMap && incLat && incLng) {
    initResponderMap(incLat, incLng);
  }
  if (!responderMap) return;

  if (responderRouteLayer) responderMap.removeLayer(responderRouteLayer);
  if (geometry && geometry.coordinates) {
    const coords = geometry.coordinates.map(([lng, lat]) => [lat, lng]);
    if (coords.length > 1) {
      responderRouteLayer = L.polyline(coords, { color: "#0D6E6E", weight: 5, opacity: 0.9, dashArray: "8 4" }).addTo(responderMap);
      responderMap.fitBounds(responderRouteLayer.getBounds(), { padding: [35, 35] });
    }
  }

  if (incLat && incLng) {
    if (incidentMarker) responderMap.removeLayer(incidentMarker);
    incidentMarker = L.marker([incLat, incLng], {
      icon: L.divIcon({ className: "", html: '<span class="pin pin--red pin--pulse"></span>', iconSize: [20, 20] })
    }).bindTooltip(`Scene: ${incidentState.title}${hospitalName ? " → " + hospitalName : ""}`, { direction: "top" }).addTo(responderMap);
  }
}

/* ---------------- dynamic incident data synchronization ---------------- */
async function loadDynamicIncident() {
  try {
    let inc = null;
    if (activeIncidentUuid && activeIncidentUuid !== "Awaiting Assignment") {
      const res = await fetch(`/api/incidents/${activeIncidentUuid}`);
      if (res.ok) {
        const d = await res.json();
        inc = d.incident;
        if (d.hazards && d.hazards.length) {
          incidentState.hazards = d.hazards.map(h => `${h.hazard_type.replace(/_/g, " ").toUpperCase()}: ${h.description}`);
        }
        if (d.updates && d.updates.length) {
          incidentState.completed_steps = d.updates
            .filter(u => u.update_type === "triage" || u.content.includes("step") || u.content.includes("Well done"))
            .map(u => u.content);
        }
      }
    } else {
      const res = await fetch("/api/incidents");
      if (res.ok) {
        const list = await res.json();
        if (list && list.length > 0) {
          inc = list[0];
          activeIncidentUuid = inc.incident_uuid;
        }
      }
    }

    if (inc) {
      incidentState.id = inc.incident_uuid;
      incidentState.title = inc.title || "Emergency Mission";
      incidentState.coords = { lat: inc.lat, lng: inc.lng };
      incidentState.place = inc.location_name || `${inc.lat.toFixed(4)}, ${inc.lng.toFixed(4)}`;
      incidentState.severity = inc.severity_level || "critical";
      incidentState.casualties = inc.casualties_count || 1;
      incidentState.rsi = inc.severity_score || 4.2;
      
      applyIncidentToUI();
      logLine(`Active mission loaded: ${incidentState.id}`, incidentState.place);
      fetchOptimalHospital(inc.lat, inc.lng, inc.type, inc.severity_score);
      loadCivilianIntelForResponder();

      if (inc.route_geometry) {
        try {
          const geom = typeof inc.route_geometry === "string" ? JSON.parse(inc.route_geometry) : inc.route_geometry;
          drawMissionRoute(geom, inc.lat, inc.lng, null);
        } catch (_) {}
      }
    }
  } catch (err) {
    console.warn("[Responder] Dynamic incident sync fallback:", err);
  }
}

function applyIncidentToUI() {
  if (el.incidentTitle) el.incidentTitle.textContent = incidentState.title;
  if (el.incidentPlace) el.incidentPlace.textContent = incidentState.place;
  if (el.incidentBadge) el.incidentBadge.textContent = incidentState.id;
  if (el.mobileStripTitle) el.mobileStripTitle.innerHTML = `<span class="cond-dot cond-dot--red"></span> ${incidentState.title}`;
  if (el.mobileVictimCount) el.mobileVictimCount.textContent = String(incidentState.casualties).padStart(2, "0");
  if (el.victimCounterBadge) el.victimCounterBadge.textContent = String(incidentState.casualties).padStart(2, "0");
  
  if (el.victimCounterStatus) {
    el.victimCounterStatus.innerHTML = `<span class="cond-dot cond-dot--red"></span> Triage Level: ${incidentState.severity.toUpperCase()} (RSI ${incidentState.rsi})`;
  }

  if (el.alertsGroup && incidentState.hazards.length > 0) {
    el.alertsGroup.innerHTML = incidentState.hazards.map(h => `
      <article class="alert">
        <svg class="crit-icon crit-icon--red" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
        <div>
          <p class="alert__label">Tactical Scene Hazard</p>
          <p class="alert__text">${h}</p>
        </div>
      </article>
    `).join("");
  }

  if (el.doneList && incidentState.completed_steps.length > 0) {
    el.doneList.innerHTML = incidentState.completed_steps.map(s => `
      <li>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
        <span>${s}</span>
      </li>
    `).join("");
  }
}

async function fetchOptimalHospital(lat, lng, incidentType, rsi) {
  try {
    const res = await fetch("/api/nearest-hospital", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lng, incident_type: incidentType || "trauma", rsi_score: rsi || 4.0 })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.recommended_hospital) {
        if (el.hospitalName) el.hospitalName.textContent = data.recommended_hospital.name;
        if (el.hospitalEta) el.hospitalEta.textContent = `${data.duration_mins} min (${data.distance_km} km)`;
        if (el.hospitalCaps) {
          const capTag = data.capability ? data.capability.toUpperCase() : "LEVEL 1 TRAUMA";
          el.hospitalCaps.innerHTML = `
            <span class="facility-cap-tag">${capTag}</span>
            <span class="facility-cap-tag" style="background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent);">Survival: ${(data.predicted_survival_probability * 100).toFixed(0)}%</span>
          `;
        }
      }
    }
  } catch (err) {
    console.warn("[Responder] Hospital routing fallback:", err);
  }
}

async function loadCivilianIntelForResponder() {
  if (!activeIncidentUuid || activeIncidentUuid === "Awaiting Assignment") return;
  const panel = document.getElementById("responderCivilianIntel");
  if (!panel) return;
  try {
    const res = await fetch(`/api/incidents/${activeIncidentUuid}/conversation`);
    if (!res.ok) return;
    const turns = await res.json();
    panel.innerHTML = turns.map(t => {
      const who = t.source === "civilian" ? "Bystander" : (t.source === "dispatcher" ? "Commander" : "ResQ AI");
      const cls = t.source === "civilian" ? "intel-line--civilian" : (t.source === "dispatcher" ? "intel-line--commander" : "intel-line--ai");
      const safe = String(t.content || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      return `<div class="intel-line ${cls}"><span class="intel-who">${who}</span><p class="intel-text">${safe}</p></div>`;
    }).join("") || "<p style='opacity:.5;padding:8px 0'>No AI conversation recorded yet</p>";
    panel.scrollTop = panel.scrollHeight;
  } catch (err) {
    console.warn("[Responder] Civilian intel load failed:", err);
  }
}

initResponderMap(6.4480, 7.5150);
loadDynamicIncident();

/* ---------------- socket event listener ---------------- */
if (typeof io !== "undefined") {
  const serverUrl = window.RESQ_CONFIG?.backendUrl || undefined;
  const socket = io(serverUrl, { transports: ["websocket", "polling"], reconnection: true });

  socket.on("connect", () => {
    socket.emit("join", { room: "responders" });
    if (assignedUnitCode) socket.emit("join", { room: `responder_${assignedUnitCode}` });
    logLine("Tactical data-link connected", "SocketIO bus active");
  });

  socket.on("responder:mission_alert", (data) => {
    if (data.unit_code && data.unit_code !== assignedUnitCode) return;
    
    activeIncidentUuid = data.incident_uuid;
    loadDynamicIncident();
    logLine(`🚨 Mission Alert: ${data.incident_uuid}`, "Commander approved dispatch. Acknowledge brief.");

    const inc = data.incident;
    if (inc) {
      if (!responderMap) initResponderMap(inc.lat, inc.lng);
      const hospName = data.recommended_hospital?.name;
      drawMissionRoute(data.route_geometry, inc.lat, inc.lng, hospName);
      
      if (data.recommended_hospital) {
        if (el.hospitalName) el.hospitalName.textContent = data.recommended_hospital.name;
        if (el.hospitalEta) el.hospitalEta.textContent = `${data.hospital_duration_mins} min (${data.hospital_distance_km} km)`;
      }
      if (data.route_duration_mins) {
        arrivalSeconds = Math.round(data.route_duration_mins * 60);
      }
    }
    
    // Pulse acknowledge button
    if (el.ackBtn) {
      el.ackBtn.classList.remove("is-acked");
      if (el.ackText) el.ackText.textContent = "Acknowledge Brief & Roll";
    }
    if (navigator.vibrate) navigator.vibrate([150, 80, 150, 80, 200]);
  });

  socket.on("incident:chat_turn", (data) => {
    if (data.incident_uuid === activeIncidentUuid) {
      loadCivilianIntelForResponder();
      logLine("Civilian update", data.civilian_message || "New first-aid step");
    }
  });

  socket.on("responder:beacon", (data) => {
    if (data.unit_code === assignedUnitCode && responderMap && responderMarker) {
      responderMarker.setLatLng([data.lat, data.lng]);
      if (data.eta_seconds !== undefined) {
        arrivalSeconds = data.eta_seconds;
      }
    }
  });

  socket.on("responder:on_scene", (data) => {
    if (data.unit_code === assignedUnitCode || data.incident_uuid === activeIncidentUuid) {
      arrivalSeconds = 0;
      $$(".stage-btn").forEach(b => b.classList.remove("is-active"));
      $('[data-stage="onscene"]')?.classList.add("is-active");
      logLine("ARRIVED ON SCENE", "Unit confirmed at casualty coordinates");
      if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
    }
  });

  socket.on("responder:route_change", (data) => {
    if (data.unit_code && data.unit_code !== assignedUnitCode) return;
    logLine("COMMANDER: Route Change", data.note || "Follow detour");
    
    const toast = document.createElement("div");
    toast.style.cssText = "position:fixed;top:64px;left:50%;transform:translateX(-50%);background:#0D6E6E;color:#fff;padding:16px 24px;border-radius:14px;z-index:99999;font-weight:600;max-width:92vw;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.5);border:2px solid #2dd4bf;";
    toast.innerHTML = `<span style="font-size:1.1rem;display:block;margin-bottom:4px;">⚠️ Route Change from Commander</span>${data.note}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 9000);
    if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
    if (data.route_geometry) drawMissionRoute(data.route_geometry, incidentState.coords?.lat, incidentState.coords?.lng, null);
  });

  socket.on("call_bridge:event", (data) => {
    if (data.active) {
      showResponderVoiceModal("Encrypted Voice Link Active: Connected with Commander & Bystander.");
    } else {
      document.getElementById("responderVoiceModal")?.remove();
    }
  });
}

function showResponderVoiceModal(msg) {
  let modal = document.getElementById("responderVoiceModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "responderVoiceModal";
    modal.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);width:92%;max-width:440px;background:var(--surface-2);border:2px solid var(--accent);border-radius:18px;padding:16px 20px;z-index:99999;box-shadow:0 12px 40px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:space-between;gap:14px;";
    document.body.appendChild(modal);
  }
  modal.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;">
      <span class="pulse pulse--teal" style="width:14px;height:14px;"></span>
      <div>
        <strong style="font-size:0.9rem;color:var(--text);display:block;">📞 Voice Bridge Active</strong>
        <span style="font-size:0.75rem;color:var(--text-2);">${msg}</span>
      </div>
    </div>
    <button id="endResponderVoiceBtn" type="button" style="background:#dc2626;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-size:0.8rem;font-weight:600;cursor:pointer;">End</button>
  `;
  document.getElementById("endResponderVoiceBtn")?.addEventListener("click", () => {
    modal.remove();
    if (activeIncidentUuid) {
      fetch(`/api/incidents/${activeIncidentUuid}/call-bridge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "end" })
      }).catch(() => {});
    }
  });
}

/* ---------------- stage control ---------------- */
$$(".stage-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".stage-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    logLine(`Status transitioned: ${btn.dataset.stage.toUpperCase()}`, "Dispatch notified");
    radioElapsed = 0;
    if (navigator.vibrate) navigator.vibrate(20);
  });
});

/* ---------------- actions: navigate & call ---------------- */
function openNavigation() {
  const { lat, lng } = incidentState.coords;
  logLine("Turn-by-turn navigation launched", `${lat.toFixed(4)}, ${lng.toFixed(4)}`);
  window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, "_blank", "noopener");
}

function openCallScene() {
  logLine("Voice radio bridge initiated", "Connecting to scene bystander & command");
  if (activeIncidentUuid && activeIncidentUuid !== "Awaiting Assignment") {
    fetch(`/api/incidents/${activeIncidentUuid}/call-bridge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start", type: "command_to_responder" })
    }).catch(() => {});
  }
  showResponderVoiceModal("Direct encrypted voice link open to scene bystander.");
}

el.navigate?.addEventListener("click", openNavigation);
el.mobileNavBtn?.addEventListener("click", openNavigation);
el.call?.addEventListener("click", openCallScene);
el.mobileCallBtn?.addEventListener("click", openCallScene);

/* ---------------- status log ---------------- */
function logLine(label, detail) {
  if (!el.log) return;
  const row = document.createElement("p");
  row.className = "statuslog__row";
  const t = new Date();
  row.innerHTML = `<span>${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}</span><b>${label}</b><span>${detail}</span>`;
  el.log.prepend(row);
  while (el.log.children.length > 8) el.log.lastElementChild.remove();
}

/* ---------------- fullscreen view toggle ---------------- */
function wireFullscreen() {
  const btn = el.fullscreenBtn;
  if (!btn) return;
  const maxIcon = btn.querySelector(".fs-icon-max");
  const minIcon = btn.querySelector(".fs-icon-min");

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  };

  btn.addEventListener("click", toggleFullscreen);

  document.addEventListener("fullscreenchange", () => {
    const isFs = !!document.fullscreenElement;
    if (maxIcon) maxIcon.classList.toggle("hidden", isFs);
    if (minIcon) minIcon.classList.toggle("hidden", !isFs);
    btn.title = isFs ? "Exit Fullscreen" : "Toggle Fullscreen Mode";
  });
}
wireFullscreen();

/* ---------------- mobile segmented switcher ---------------- */
function wireMobileNav() {
  const tabs = $$(".m-nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        const isActive = t === tab;
        t.classList.toggle("is-active", isActive);
        t.setAttribute("aria-selected", String(isActive));
      });
      if (el.workspace) {
        el.workspace.dataset.activeTab = tab.dataset.tab;
      }
      setTimeout(() => responderMap?.invalidateSize(), 100);
    });
  });
}
wireMobileNav();
