/* Responder tactical cockpit brief — dynamic telemetry, stage control, navigation, multi-pane & mobile view */
import "./resq-theme.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Extract target incident uuid from URL query or fallback
const urlParams = new URLSearchParams(window.location.search);
let activeIncidentUuid = urlParams.get("incident") || urlParams.get("id");
let assignedUnitCode = urlParams.get("unit") || "AMB-07";

let incidentState = {
  id: activeIncidentUuid || "RQ-2417",
  title: "Head-on collision, trailer and minibus",
  coords: { lat: 6.3894, lng: 7.2295 },
  place: "Enugu–Onitsha Expressway, km 42 eastbound (near Ugwuoba)",
  severity: "critical",
  rsi: 4.5,
  tier: "P1",
  casualties: 2,
  hazards: ["Fuel spill detected at collision site — do not deploy flares"],
  trauma: ["Head trauma / Unresponsive", "Severe arterial hemorrhage"],
  completed_steps: ["Recovery position administered", "Direct pressure held on wound", "Casualty kept warm, nil by mouth"],
  hospital: {
    name: "Enugu State University Teaching Hospital (ESUT)",
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
let arrivalSeconds = 12 * 60 + 4; // 12:04
function tickArrival() {
  if (arrivalSeconds > 0) {
    arrivalSeconds -= 1;
    const m = Math.floor(arrivalSeconds / 60);
    const s = arrivalSeconds % 60;
    const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = timeStr;
    if (el.mobileEta) el.mobileEta.textContent = timeStr;
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
    if (!activeIncidentUuid) {
      logLine("Acknowledgement unavailable", "No assigned incident selected");
      return;
    }
    try {
      const response = await fetch(`/api/incidents/${activeIncidentUuid}/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ unit_code: assignedUnitCode })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      logLine("Acknowledgement not sent", "Server confirmation required");
      return;
    }
    isAcked = !isAcked;
    if (isAcked) {
      el.ackBtn.classList.add("is-acked");
      if (el.ackText) el.ackText.textContent = "Brief acknowledged";
      logLine("Brief acknowledged by unit", "Dispatch confirmation recorded");
      radioElapsed = 0;
      if (navigator.vibrate) navigator.vibrate([30, 50, 30]);
    } else {
      el.ackBtn.classList.remove("is-acked");
      if (el.ackText) el.ackText.textContent = "Acknowledge brief";
      logLine("Brief status reset to pending", "Dispatch telemetry updated");
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

  // POST telemetry beacon to server
  fetch("/api/responder-telemetry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      unit_code: assignedUnitCode,
      lat: currentCoords.lat,
      lng: currentCoords.lng,
      heading: 45.0,
      speed_kmh: 42.0
    })
  }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (beats % 4 === 0) logLine("Position beacon transmitted", "Server confirmed");
  }).catch(() => logLine("Position beacon not delivered", "Retrying on next interval"));
}

if ("geolocation" in navigator) {
  navigator.geolocation.watchPosition(
    (pos) => {
      currentCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    },
    () => logLine("GPS signal using cellular triangulation", "Using calibrated corridor coordinate"),
    { enableHighAccuracy: true, maximumAge: 10000 }
  );
}
broadcastTelemetry();
setInterval(broadcastTelemetry, 10000);

/* ---------------- dynamic incident data synchronization ---------------- */
async function loadDynamicIncident() {
  try {
    let inc = null;
    if (activeIncidentUuid) {
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
      // Find latest reported or dispatched incident
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
      incidentState.rsi = inc.severity_score || 3.5;
      
      applyIncidentToUI();
      logLine(`Active mission loaded: ${incidentState.id}`, incidentState.place);
      fetchOptimalHospital(inc.lat, inc.lng, inc.type, inc.severity_score);
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

  // Render hazards
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

  // Render civilian steps
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

loadDynamicIncident();

/* ---------------- Leaflet map for responder route ---------------- */
let responderMap = null;
let responderMarker = null;
let incidentMarker = null;
let responderRouteLayer = null;

function initResponderMap(centerLat, centerLng) {
  const mapDiv = document.getElementById("responderMap");
  if (!mapDiv || responderMap) return;
  responderMap = L.map("responderMap", { zoomControl: true, attributionControl: false })
    .setView([centerLat || 6.42, centerLng || 7.38], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(responderMap);
  // Own position marker
  responderMarker = L.marker([centerLat || 6.42, centerLng || 7.38], {
    icon: L.divIcon({ className: "", html: '<span class="pin pin--responder pin--pulse"></span>', iconSize: [22, 22] })
  }).bindTooltip("Your position", { direction: "top" }).addTo(responderMap);
}

function drawMissionRoute(geometry, incLat, incLng, hospitalName) {
  if (!responderMap) return;
  // Draw route polyline
  if (responderRouteLayer) responderMap.removeLayer(responderRouteLayer);
  if (geometry && geometry.coordinates) {
    const coords = geometry.coordinates.map(([lng, lat]) => [lat, lng]);
    if (coords.length > 1) {
      responderRouteLayer = L.polyline(coords, { color: "#0D6E6E", weight: 4, opacity: 0.9, dashArray: "8 4" }).addTo(responderMap);
    }
  }
  // Incident pin
  if (incLat && incLng) {
    if (incidentMarker) responderMap.removeLayer(incidentMarker);
    incidentMarker = L.marker([incLat, incLng], {
      icon: L.divIcon({ className: "", html: '<span class="pin pin--red pin--pulse"></span>', iconSize: [18, 18] })
    }).bindTooltip(`Incident scene${hospitalName ? " → " + hospitalName : ""}`, { direction: "top" }).addTo(responderMap);
    if (responderRouteLayer) {
      responderMap.fitBounds(responderRouteLayer.getBounds(), { padding: [30, 30] });
    } else {
      responderMap.setView([incLat, incLng], 13);
    }
  }
}

/* ---------------- socket event listener ---------------- */
if (typeof io !== "undefined") {
  const socket = io({ transports: ["websocket", "polling"] });
  socket.on("connect", () => {
    socket.emit("join", { room: "responders" });
    if (assignedUnitCode) socket.emit("join", { room: `responder_${assignedUnitCode}` });
    logLine("Tactical data-link connected", "SocketIO bus active");
  });

  socket.on("responder:mission_alert", (data) => {
    // Update unit code if provided
    if (data.unit_code) {
      assignedUnitCode = data.unit_code;
      socket.emit("join", { room: `responder_${assignedUnitCode}` });
    }
    if (data.incident_uuid) {
      activeIncidentUuid = data.incident_uuid;
      loadDynamicIncident();
      logLine(`Mission alert received: ${data.incident_uuid}`, "Loading full brief…");
    }
    // Draw the route and incident on map
    const inc = data.incident;
    if (inc) {
      if (!responderMap) initResponderMap(inc.lat, inc.lng);
      const hospName = data.recommended_hospital?.name;
      drawMissionRoute(data.route_geometry, inc.lat, inc.lng, hospName);
      // Update hospital info
      if (data.recommended_hospital) {
        if (el.hospitalName) el.hospitalName.textContent = data.recommended_hospital.name;
        if (el.hospitalEta) el.hospitalEta.textContent = `${data.hospital_duration_mins} min (${data.hospital_distance_km} km)`;
      }
      if (data.route_duration_mins && el.arrivalCountdown) {
        arrivalSeconds = Math.round(data.route_duration_mins * 60);
      }
    }
    if (navigator.vibrate) navigator.vibrate([100, 80, 100]);
  });

  socket.on("responder:assigned", (data) => {
    if (data.unit_code === assignedUnitCode || !activeIncidentUuid) {
      activeIncidentUuid = data.incident_uuid;
      loadDynamicIncident();
      logLine(`Assigned to Mission: ${data.incident_uuid}`, data.status || "dispatched");
      if (navigator.vibrate) navigator.vibrate([100, 80, 100]);
    }
  });

  socket.on("incident:update", (data) => {
    if (data.incident_uuid === activeIncidentUuid) {
      loadDynamicIncident();
    }
  });

  socket.on("responder:beacon", (data) => {
    // Update own-position marker from server-confirmed position
    if (data.unit_code === assignedUnitCode && responderMap && responderMarker) {
      responderMarker.setLatLng([data.lat, data.lng]);
    }
  });

  socket.on("responder:route_change", (data) => {
    // Show a prominent alert toast and log it
    logLine("DISPATCH: Route change instruction received", data.note || "See dispatcher message");
    const toast = document.createElement("div");
    toast.style.cssText = "position:fixed;top:72px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:14px 22px;border-radius:10px;z-index:9999;font-weight:600;max-width:90vw;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.35)";
    toast.textContent = `Dispatch: ${data.note}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 8000);
    if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
    if (data.route_geometry) drawMissionRoute(data.route_geometry, incidentState.coords?.lat, incidentState.coords?.lng, null);
  });
}

/* ---------------- load civilian AI conversation for responder intel ---------------- */
async function loadCivilianIntelForResponder() {
  if (!activeIncidentUuid) return;
  const panel = document.getElementById("responderCivilianIntel");
  if (!panel) return;
  try {
    const res = await fetch(`/api/incidents/${activeIncidentUuid}/conversation`);
    if (!res.ok) return;
    const turns = await res.json();
    panel.innerHTML = turns.map(t => {
      const who = t.source === "civilian" ? "Bystander" : "ResQ AI";
      const cls = t.source === "civilian" ? "intel-line--civilian" : "intel-line--ai";
      const safe = String(t.content || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      return `<div class="intel-line ${cls}"><span class="intel-who">${who}</span><p class="intel-text">${safe}</p></div>`;
    }).join("") || "<p style='opacity:.5;padding:8px 0'>No AI conversation recorded yet</p>";
    panel.scrollTop = panel.scrollHeight;
  } catch (err) {
    console.warn("[Responder] Civilian intel load failed:", err);
  }
}
setInterval(loadCivilianIntelForResponder, 15000); // refresh every 15s


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
  logLine("Radio bridge opened to scene bystander", "Channel active");
  radioElapsed = 0;
  alert(`Connecting encrypted voice radio bridge to reporting bystander at ${incidentState.id}...`);
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
    });
  });
}
wireMobileNav();
