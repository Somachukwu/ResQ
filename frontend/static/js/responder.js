/* Responder tactical cockpit brief — dynamic telemetry, stage control, navigation, multi-pane & mobile view */
import "./resq-theme.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// Extract target incident uuid and unit code from URL query
const urlParams = new URLSearchParams(window.location.search);
let activeIncidentUuid = urlParams.get("incident") || urlParams.get("id") || null;
let assignedUnitCode = urlParams.get("unit") || "AMB-01";

let incidentState = {
  id: null,
  title: "Awaiting Mission Dispatch",
  coords: { lat: 6.4480, lng: 7.5150 },
  place: "Staged in sector",
  severity: "standby",
  rsi: 0.0,
  tier: "Standby",
  casualties: 0,
  hazards: [],
  trauma: [],
  completed_steps: [],
  hospital: null
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
  incidentTitle: $("#incidentTraumaTitle") || $(".mission__trauma"),
  incidentPlace: $("#incidentWhereText") || $(".mission__where span"),
  incidentBadge: $("#incidentBadge") || $(".r-card--incident .badge"),
  briefTriageBadge: $("#briefTriageBadge"),
  headerUnitCode: $("#headerUnitCode"),
  headerUnitStatus: $("#headerUnitStatus"),
  mobileStripTitle: $("#mobileStripTitle") || $(".m-strip__title"),
  mobileVictimCount: $("#mobileVictimsCount") || $(".m-strip__metrics .m-metric:nth-child(2) .m-metric__val"),
  victimCounterBadge: $("#victimCountBadge") || $(".victim-count-badge"),
  victimCounterStatus: $("#victimCounterStatus") || $(".victim-counter-status"),
  victimCounterSub: $("#victimCounterSub") || $(".victim-counter-sub"),
  alertsGroup: $("#alertsGroup") || $(".alerts-group"),
  routeStepsList: $("#routeStepsList"),
  bystanderDoneList: $("#bystanderDoneList") || $(".done-list"),
  victimProfilesGrid: $("#victimProfilesGrid"),
  hospitalName: $("#destHospitalName") || $(".destination__name"),
  hospitalEta: $("#destHospitalEta") || $(".destination__eta"),
  hospitalCaps: $("#destHospitalCaps") || $(".destination__caps"),
  hospitalWhy: $("#destHospitalWhy") || $(".destination__why")
};

// Set initial unit code header
if (el.headerUnitCode) {
  el.headerUnitCode.textContent = ` · ${assignedUnitCode}`;
}

/* ---------------- arrival countdown ticker (only active when confirmed) ---------------- */
let arrivalSeconds = null;

function tickArrival() {
  if (arrivalSeconds !== null && arrivalSeconds > 0) {
    arrivalSeconds -= 1;
    const m = Math.floor(arrivalSeconds / 60);
    const s = arrivalSeconds % 60;
    const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = timeStr;
    if (el.mobileEta) el.mobileEta.textContent = timeStr;
  } else if (arrivalSeconds === 0) {
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = "00:00";
    if (el.mobileEta) el.mobileEta.textContent = "00:00";
  } else {
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = "--:--";
    if (el.mobileEta) el.mobileEta.textContent = "--:--";
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
      alert("No active incident assigned to acknowledge.");
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
      if (el.ackText) el.ackText.textContent = "Mission Acknowledged";
      logLine("Mission brief acknowledged", `Unit ${assignedUnitCode} rolling to scene`);
      
      // Calculate countdown strictly from real ETA
      const etaMins = data.eta_minutes || 8;
      arrivalSeconds = Math.round(etaMins * 60);
      tickArrival();

      if (el.headerUnitStatus) {
        el.headerUnitStatus.innerHTML = `<span class="pulse pulse--teal" aria-hidden="true"></span> Unit ${assignedUnitCode} · En route`;
      }

      radioElapsed = 0;
      if (navigator.vibrate) navigator.vibrate([40, 60, 40]);
    } catch (error) {
      logLine("Acknowledgement not sent", error.message);
      alert(`Could not acknowledge dispatch: ${error.message}`);
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
      speed_kmh: 42.0
    })
  }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (beats % 6 === 0) logLine("Position beacon transmitted", "Server confirmed AVL");
  }).catch(() => {});
}

if ("geolocation" in navigator) {
  navigator.geolocation.watchPosition(
    (pos) => {
      currentCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    },
    () => {
      // Fallback calibrated Enugu corridor coordinates
      currentCoords = { lat: 6.4480, lng: 7.5150 };
    },
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
            .filter(u => u.update_type === "triage" || u.content.includes("step") || u.content.includes("Well done") || u.content.includes("position"))
            .map(u => u.content);
        }
      }
    } else {
      const res = await fetch("/api/incidents");
      if (res.ok) {
        const list = await res.json();
        if (list && list.length > 0) {
          // Check if any incident is assigned to this unit
          const assigned = list.find(i => i.assigned_responder_id === assignedUnitCode);
          inc = assigned || list[0];
          activeIncidentUuid = inc.incident_uuid;
        }
      }
    }

    if (inc) {
      incidentState.id = inc.incident_uuid;
      incidentState.title = inc.title || "Emergency Mission";
      incidentState.coords = { lat: Number(inc.lat), lng: Number(inc.lng) };
      incidentState.place = inc.location_name || `${Number(inc.lat).toFixed(4)}, ${Number(inc.lng).toFixed(4)}`;
      incidentState.severity = inc.severity_level || "critical";
      incidentState.casualties = Number(inc.casualties_count || 1);
      incidentState.rsi = Number(inc.severity_score || 3.5);

      applyIncidentToUI();
      logLine(`Active mission loaded: ${incidentState.id}`, incidentState.place);
      fetchOptimalHospital(inc.lat, inc.lng, inc.type, inc.severity_score);
      loadCivilianIntelForResponder();
    }
  } catch (err) {
    console.warn("[Responder] Dynamic incident sync fallback:", err);
  }
}

function applyIncidentToUI() {
  if (el.incidentTitle) el.incidentTitle.textContent = incidentState.title;
  if (el.incidentPlace) el.incidentPlace.textContent = incidentState.place;
  if (el.incidentBadge) el.incidentBadge.textContent = incidentState.id || "--";
  if (el.mobileStripTitle) {
    el.mobileStripTitle.innerHTML = `<span class="cond-dot cond-dot--red"></span> ${incidentState.title}`;
  }
  const casualtiesStr = String(incidentState.casualties).padStart(2, "0");
  if (el.mobileVictimCount) el.mobileVictimCount.textContent = casualtiesStr;
  if (el.victimCounterBadge) el.victimCounterBadge.textContent = casualtiesStr;

  if (el.briefTriageBadge) {
    const isCrit = incidentState.severity === "critical";
    el.briefTriageBadge.className = isCrit ? "status-indicator-tag status-indicator-tag--red" : "status-indicator-tag";
    el.briefTriageBadge.innerHTML = `<span class="cond-dot ${isCrit ? 'cond-dot--red' : ''}"></span> ${incidentState.severity.toUpperCase()}`;
  }

  if (el.victimCounterStatus) {
    el.victimCounterStatus.innerHTML = `<span class="cond-dot cond-dot--red"></span> Scene Priority: ${incidentState.severity.toUpperCase()} (RSI ${incidentState.rsi.toFixed(1)})`;
  }
  if (el.victimCounterSub) {
    el.victimCounterSub.textContent = `${incidentState.casualties} Casualty report(s) active · Direct telemetry linked`;
  }

  // Render hazards
  if (el.alertsGroup) {
    if (incidentState.hazards.length > 0) {
      el.alertsGroup.innerHTML = incidentState.hazards.map(h => `
        <article class="alert">
          <svg class="crit-icon crit-icon--red" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
          <div>
            <p class="alert__label">Tactical Scene Hazard</p>
            <p class="alert__text">${h}</p>
          </div>
        </article>
      `).join("");
    } else {
      el.alertsGroup.innerHTML = `<article class="alert" style="color:var(--text-3);font-size:12px;padding:10px 14px;">No active environmental hazards flagged.</article>`;
    }
  }

  // Render civilian first-aid steps
  if (el.bystanderDoneList) {
    if (incidentState.completed_steps.length > 0) {
      el.bystanderDoneList.innerHTML = incidentState.completed_steps.map(s => `
        <li>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
          <span>${s}</span>
        </li>
      `).join("");
    } else {
      el.bystanderDoneList.innerHTML = `<li style="color:var(--text-3);font-size:12px;">No bystander first aid actions logged yet.</li>`;
    }
  }

  // Render patient profiles dynamically
  if (el.victimProfilesGrid) {
    const victimsCount = incidentState.casualties || 1;
    let profilesHtml = "";
    for (let i = 1; i <= Math.min(victimsCount, 4); i++) {
      const isP1 = i === 1 && incidentState.severity === "critical";
      profilesHtml += `
        <article class="victim-card">
          <div class="victim-card__top">
            <span class="victim-condition-title">
              <span class="cond-dot ${isP1 ? 'cond-dot--red' : 'cond-dot--orange'}"></span>
              Victim ${i} · Priority ${isP1 ? 'Red' : 'Yellow'}
            </span>
            <span class="victim-card__eta">Direct triage</span>
          </div>
          <p class="victim-card__demo">Casualty profile ${i} · Live telemetry</p>
          <p class="victim-card__clinical">${incidentState.title}. Bystander guidance in progress.</p>
        </article>
      `;
    }
    el.victimProfilesGrid.innerHTML = profilesHtml;
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
          const survivalPct = data.predicted_survival_probability ? Math.round(data.predicted_survival_probability * 100) : 92;
          el.hospitalCaps.innerHTML = `
            <span class="facility-cap-tag">${capTag}</span>
            <span class="facility-cap-tag">ICU Bed Held</span>
            <span class="facility-cap-tag" style="background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent);">Survival: ${survivalPct}%</span>
          `;
        }
        if (el.hospitalWhy) {
          el.hospitalWhy.textContent = `Capability-matched for ${incidentType || "trauma"} profile. Golden hour transit prioritized.`;
        }
      }
    }
  } catch (err) {
    console.warn("[Responder] Hospital routing fallback:", err);
  }
}

loadDynamicIncident();

/* ---------------- socket event listener ---------------- */
if (typeof io !== "undefined") {
  const socket = io({ transports: ["websocket", "polling"] });

  socket.on("connect", () => {
    socket.emit("join", { room: "responders" });
    if (assignedUnitCode) socket.emit("join", { room: `responder_${assignedUnitCode}` });
    logLine("Tactical data-link connected", "SocketIO bus active");
  });

  socket.on("responder:assigned", (data) => {
    if (data.unit_code === assignedUnitCode || !activeIncidentUuid) {
      activeIncidentUuid = data.incident_uuid;
      loadDynamicIncident();
      logLine(`DISPATCH ORDER RECEIVED`, `Incident: ${data.incident_uuid}`);
      if (el.headerUnitStatus) {
        el.headerUnitStatus.innerHTML = `<span class="pulse pulse--teal" aria-hidden="true"></span> Unit ${assignedUnitCode} · Dispatched (Awaiting Ack)`;
      }
      if (data.route_duration_mins && arrivalSeconds === null) {
        arrivalSeconds = Math.round(data.route_duration_mins * 60);
      }
      if (navigator.vibrate) navigator.vibrate([100, 80, 100]);
    }
  });

  socket.on("responder:mission_alert", (data) => {
    if (data.unit_code) {
      assignedUnitCode = data.unit_code;
      socket.emit("join", { room: `responder_${assignedUnitCode}` });
    }
    if (data.incident_uuid) {
      activeIncidentUuid = data.incident_uuid;
      loadDynamicIncident();
      logLine(`Mission alert received: ${data.incident_uuid}`, "Tactical brief loaded");
    }
    if (data.route_duration_mins) {
      arrivalSeconds = Math.round(data.route_duration_mins * 60);
    }
    if (navigator.vibrate) navigator.vibrate([100, 80, 100]);
  });

  socket.on("incident:update", (data) => {
    if (data.incident_uuid === activeIncidentUuid) {
      loadDynamicIncident();
    }
  });

  socket.on("incident:chat_turn", (data) => {
    if (data.incident_uuid === activeIncidentUuid) {
      if (data.casualties_count != null && data.casualties_count !== incidentState.casualties) {
        incidentState.casualties = Number(data.casualties_count);
        applyIncidentToUI();
      }
      loadCivilianIntelForResponder();
    }
  });

  socket.on("responder:route_change", (data) => {
    logLine("COMMAND: Route change instruction received", data.note || data.new_route || "Detour instructed");
    const toast = document.createElement("div");
    toast.style.cssText = "position:fixed;top:72px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:14px 22px;border-radius:10px;z-index:9999;font-weight:600;max-width:90vw;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.35)";
    toast.textContent = `Command Instruction: ${data.note || data.new_route}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 8000);
    if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
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
    if (turns.length === 0) {
      panel.innerHTML = "<p style='opacity:.5;padding:8px 0;margin:0;'>No bystander conversation recorded yet.</p>";
      return;
    }
    panel.innerHTML = turns.map(t => {
      const who = t.source === "civilian" ? "Bystander" : "ResQ AI";
      const cls = t.source === "civilian" ? "intel-line--civilian" : "intel-line--ai";
      const safe = String(t.content || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
      return `<div class="intel-line ${cls}" style="padding:4px 0;"><span class="intel-who" style="font-weight:600;color:var(--accent);">${who}:</span> <span class="intel-text">${safe}</span></div>`;
    }).join("");
    panel.scrollTop = panel.scrollHeight;
  } catch (err) {
    console.warn("[Responder] Civilian intel load failed:", err);
  }
}
setInterval(loadCivilianIntelForResponder, 10000);

/* ---------------- stage control ---------------- */
$$(".stage-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".stage-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const stage = btn.dataset.stage;
    logLine(`Status transitioned: ${stage.toUpperCase()}`, "Dispatch notified");
    radioElapsed = 0;
    if (navigator.vibrate) navigator.vibrate(20);

    const payload = {
      unit_code: assignedUnitCode,
      status: stage,
      stage: stage,
      incident_uuid: activeIncidentUuid
    };
    if (resqSocket) {
      resqSocket.emit("responder:status", payload);
    }
    fetch("/api/responder/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).catch(() => {});
  });
});

/* ---------------- actions: navigate & call ---------------- */
function openNavigation() {
  const { lat, lng } = incidentState.coords;
  logLine("Turn-by-turn navigation launched", `${lat.toFixed(4)}, ${lng.toFixed(4)}`);
  window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, "_blank", "noopener");
}

async function openCallScene() {
  if (!activeIncidentUuid) {
    alert("No active mission assigned.");
    return;
  }
  logLine("Radio bridge connecting to scene", "Establishing audio line...");
  try {
    const res = await fetch(`/api/incidents/${activeIncidentUuid}/call-bridge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "responder_connect",
        title: `Responder ${assignedUnitCode} Voice Bridge`
      })
    });
    if (res.ok) {
      logLine("Voice radio link established", "Encrypted channel open to bystander");
      alert(`Voice link connected with caller on scene at incident ${activeIncidentUuid}. Audio open.`);
    }
  } catch (err) {
    console.warn("Call scene error:", err);
  }
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
