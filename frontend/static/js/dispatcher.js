/* Dispatcher GIS command center — live queue, layered tactical map, 1-tap dispatch */
import "./resq-theme.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const L = window.L;

/* ---------------- seed operational data (Enugu corridor) ---------------- */
const INCIDENTS = [
  {
    id: "RQ-2417",
    rsi: 4.6,
    triage: "red",
    title: "Head-on collision, trailer and minibus",
    place: "Enugu–Onitsha Expressway km 42 E",
    victims: 2,
    injuries: "Unresponsive / head trauma, arterial bleed",
    hazards: ["Fuel spill", "Live traffic"],
    lat: 6.3894,
    lng: 7.2295,
    started: Date.now() - 1000 * 132,
  },
  {
    id: "RQ-2416",
    rsi: 3.4,
    triage: "yellow",
    title: "Okada rider struck at junction",
    place: "Ogui Road / Zik Avenue",
    victims: 1,
    injuries: "Open tibia fracture, conscious",
    hazards: ["Crowd control"],
    lat: 6.4402,
    lng: 7.4936,
    started: Date.now() - 1000 * 640,
  },
  {
    id: "RQ-2415",
    rsi: 3.9,
    triage: "yellow",
    title: "Flood submersion, vehicle in culvert",
    place: "Nike Lake river crossing",
    victims: 3,
    injuries: "Hypothermia, near-drowning",
    hazards: ["Water hazard"],
    lat: 6.4756,
    lng: 7.5648,
    started: Date.now() - 1000 * 1520,
  },
  {
    id: "RQ-2414",
    rsi: 1.8,
    triage: "green",
    title: "Market fall, elderly woman",
    place: "New Haven market, gate 3",
    victims: 1,
    injuries: "Wrist injury, stable",
    hazards: [],
    lat: 6.4381,
    lng: 7.4802,
    started: Date.now() - 1000 * 2400,
  },
];

const UNITS = [
  { id: "AMB-07", name: "Ambulance 07", type: "Advanced life support", status: "idle", lat: 6.4021, lng: 7.2711, eta: 6, caps: "ALS · Trauma kit · O₂" },
  { id: "FRSC-12", name: "FRSC Rescue 12", type: "Extrication", status: "enroute", lat: 6.3702, lng: 7.2884, eta: 9, caps: "Cutters · Fire suppression" },
  { id: "AMB-03", name: "Ambulance 03", type: "Basic life support", status: "dispatched", lat: 6.4499, lng: 7.4881, eta: 4, caps: "BLS · Splints" },
  { id: "AMB-11", name: "Ambulance 11", type: "Advanced life support", status: "scene", lat: 6.4768, lng: 7.5601, eta: 0, caps: "ALS · Water rescue" },
  { id: "MED-02", name: "Medical SUV 02", type: "Physician response", status: "idle", lat: 6.4267, lng: 7.5122, eta: 12, caps: "Physician · Blood" },
];

const HOSPITALS = [
  { name: "ESUTH Parklane", caps: "Level 1 trauma · ICU · Blood bank", lat: 6.4462, lng: 7.4881 },
  { name: "UNTH Ituku-Ozalla", caps: "Level 1 trauma · Neurosurgery", lat: 6.3113, lng: 7.4423 },
  { name: "Niger Foundation", caps: "Orthopaedic · General", lat: 6.4381, lng: 7.5019 },
  { name: "Awka General", caps: "General · Blood bank", lat: 6.2109, lng: 7.0741 },
];

const FLOODZONES = [
  { name: "Ekulu river crossing", lat: 6.4712, lng: 7.5382, r: 1400 },
  { name: "Ugwuoba blackspot (FRSC)", lat: 6.3891, lng: 7.2312, r: 2000 },
];

/* ---------------- state ---------------- */
let selected = INCIDENTS[0];
let map;
const layers = {};

/* ---------------- map ---------------- */
function initMap() {
  map = L.map("map", { zoomControl: false, attributionControl: true }).setView([6.42, 7.38], 10);
  L.control.zoom({ position: "bottomright" }).addTo(map);

  layers.base = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap",
  }).addTo(map);

  layers.satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "© Esri" }
  );

  layers.incidents = L.layerGroup().addTo(map);
  layers.responders = L.layerGroup().addTo(map);
  layers.hospitals = L.layerGroup().addTo(map);
  layers.flood = L.layerGroup().addTo(map);
  layers.corridors = L.layerGroup().addTo(map);

  INCIDENTS.forEach((i) => {
    const m = L.marker([i.lat, i.lng], {
      icon: L.divIcon({
        className: "",
        html: `<span class="pin pin--${i.triage} ${i.triage === "red" ? "pin--pulse" : ""}" style="position:relative;display:block"></span>`,
        iconSize: [18, 18],
      }),
    }).bindTooltip(`${i.id} · ${i.title}`, { direction: "top" });
    m.on("click", () => select(i.id));
    m.addTo(layers.incidents);
    i.marker = m;
  });

  UNITS.forEach((u) => {
    L.marker([u.lat, u.lng], {
      icon: L.divIcon({ className: "", html: `<span class="pin pin--responder"></span>`, iconSize: [20, 20] }),
    })
      .bindTooltip(`${u.name} · ${u.status}`, { direction: "top" })
      .addTo(layers.responders);
  });

  HOSPITALS.forEach((h) => {
    L.marker([h.lat, h.lng], {
      icon: L.divIcon({ className: "", html: `<span class="pin pin--hospital"></span>`, iconSize: [16, 16] }),
    })
      .bindTooltip(`${h.name} — ${h.caps}`, { direction: "top" })
      .addTo(layers.hospitals);
  });

  // Safe corridor from staged unit to the critical incident
  L.polyline(
    [
      [UNITS[0].lat, UNITS[0].lng],
      [6.3955, 7.2512],
      [INCIDENTS[0].lat, INCIDENTS[0].lng],
    ],
    { color: "#0D6E6E", weight: 3, opacity: 0.85 }
  ).addTo(layers.responders);

  // Dynamic predictive models ingestion from backend APIs
  loadFloodRiskLayer(0);
  loadCorridorRiskLayer(0);
}

/* ---------------- dynamic predictive modeling layers (Track A Integration) ---------------- */
let activeFloodData = null;
let activeCorridorData = null;

async function loadFloodRiskLayer(rainRate = 0) {
  try {
    const res = await fetch(`/api/analysis/flood-risk?rain_rate=${rainRate}`);
    if (!res.ok) return;
    const data = await res.json();
    activeFloodData = data;
    layers.flood.clearLayers();

    const basins = data.basins || [];
    basins.forEach((b) => {
      const isImpassable = b.status === "IMPASSABLE";
      const isCaution = b.status === "CAUTION";
      const radius = isImpassable ? 1700 : (isCaution ? 1300 : 900);

      // Inundation buffer circle
      L.circle([b.coordinates.lat, b.coordinates.lng], {
        radius: radius,
        color: b.status_color,
        weight: isImpassable ? 2 : 1,
        dashArray: isImpassable ? "6, 6" : null,
        fillColor: b.status_color,
        fillOpacity: isImpassable ? 0.28 : 0.14,
      }).addTo(layers.flood);

      // Center hazard marker
      const marker = L.marker([b.coordinates.lat, b.coordinates.lng], {
        icon: L.divIcon({
          className: "",
          html: `<span class="pin pin--flood ${isImpassable ? 'pin--pulse' : ''}" style="background:${b.status_color};color:#fff" title="${b.name}">🌊</span>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        }),
      });

      marker.bindPopup(`
        <div class="map-popup-card">
          <div class="popup-title">${b.name}</div>
          <div class="popup-sub">${b.affected_road}</div>
          <div class="popup-grid">
            <span>Status: <strong style="color:${b.status_color}">${b.status}</strong></span>
            <span>Impassability Risk: <strong>${(b.impassability_probability * 100).toFixed(1)}%</strong></span>
            <span>Est. Water Depth: <strong>${b.estimated_water_depth_cm} cm</strong></span>
            <span>Drainage Basin: <strong>${b.river_system}</strong></span>
          </div>
          <div class="popup-advisory">${b.advisory}</div>
        </div>
      `);

      marker.bindTooltip(`${b.name} · ${b.status} (${(b.impassability_probability * 100).toFixed(0)}%)`, { direction: "top" });
      marker.addTo(layers.flood);
    });

    checkTacticalAlerts();
  } catch (err) {
    console.error("[FloodLayer] Failed to load flood model data:", err);
  }
}

async function loadCorridorRiskLayer(rainRate = 0) {
  try {
    const res = await fetch(`/api/analysis/corridor-risk?rain_rate=${rainRate}`);
    if (!res.ok) return;
    const data = await res.json();
    activeCorridorData = data;
    layers.corridors.clearLayers();

    const corridors = data.corridors || [];
    corridors.forEach((c) => {
      const risk = c.risk_analysis || {};
      const isCritical = risk.risk_level === "CRITICAL_RISK";

      // Corridor marker with dynamic CRI badge
      const marker = L.marker([c.coordinates.lat, c.coordinates.lng], {
        icon: L.divIcon({
          className: "",
          html: `
            <div class="pin pin--corridor ${isCritical ? 'pin--pulse' : ''}" style="border-color:${risk.color_code}">
              <span class="corridor-badge" style="background:${risk.color_code}">CRI ${risk.cri_score}</span>
            </div>
          `,
          iconSize: [64, 24],
          iconAnchor: [32, 12]
        }),
      });

      marker.bindPopup(`
        <div class="map-popup-card">
          <div class="popup-title">${c.name}</div>
          <div class="popup-sub">${c.corridor_name} · FRSC High-Fatality Blackspot</div>
          <div class="popup-grid">
            <span>Corridor Risk Index: <strong style="color:${risk.color_code}">CRI ${risk.cri_score} (${risk.risk_level.replace(/_/g, ' ')})</strong></span>
            <span>Terrain Grade: <strong>${c.slope_gradient_percent}% Slope</strong></span>
            <span>Annual Fatalities: <strong>${c.historical_fatalities_annual}</strong></span>
            <span>Annual Collisions: <strong>${c.historical_crashes_annual}</strong></span>
          </div>
          <div class="popup-advisory"><strong>Primary Hazard:</strong> ${c.primary_cause}</div>
          <div class="popup-patrol"><strong>Patrol Unit:</strong> ${c.recommended_patrol_station}</div>
        </div>
      `);

      marker.bindTooltip(`${c.name} · CRI ${risk.cri_score}`, { direction: "top" });
      marker.addTo(layers.corridors);

      // If Ugwu Onyeama, draw danger corridor polyline along escarpment
      if (c.corridor_id === "COR-ONYEAMA-01") {
        L.polyline(
          [
            [6.4620, 7.4250],
            [6.4528, 7.4395],
            [6.4440, 7.4520]
          ],
          {
            color: risk.color_code,
            weight: 4,
            opacity: 0.85,
            dashArray: "8, 6"
          }
        ).bindTooltip("Ugwu Onyeama High-Risk Mountain Descent (8.5% Grade)", { sticky: true }).addTo(layers.corridors);
      }
    });

    checkTacticalAlerts();
  } catch (err) {
    console.error("[CorridorLayer] Failed to load corridor risk data:", err);
  }
}

function checkTacticalAlerts() {
  const banner = $("#tacticalModelBanner");
  const title = $("#tacticalBannerTitle");
  const desc = $("#tacticalBannerDesc");
  const actionBtn = $("#tacticalBannerActionBtn");
  if (!banner || !title || !desc || !actionBtn) return;

  // Prioritize critical corridor risk
  if (activeCorridorData && activeCorridorData.tactical_prepositioning_alerts?.length > 0) {
    const alert = activeCorridorData.tactical_prepositioning_alerts[0];
    title.textContent = "High Corridor Crash Risk Detected";
    desc.textContent = `${alert.corridor} (CRI ${alert.cri_score}). ${alert.action}.`;
    actionBtn.textContent = "Focus Corridor";
    actionBtn.onclick = () => {
      map?.flyTo([6.4528, 7.4395], 13, { duration: 1.2 });
    };
    banner.classList.remove("hidden");
    return;
  }

  // Next check flood alert
  if (activeFloodData && activeFloodData.impassable_segments_count > 0) {
    title.textContent = "Severe Road Submersion Alert";
    desc.textContent = `${activeFloodData.impassable_segments_count} arterial bridge/culvert segment(s) submerged. Detour active.`;
    actionBtn.textContent = "Focus Flood Zone";
    actionBtn.onclick = () => {
      map?.flyTo([6.4712, 7.5284], 13, { duration: 1.2 });
    };
    banner.classList.remove("hidden");
    return;
  }

  banner.classList.add("hidden");
}

function wireTacticalBanner() {
  const closeBtn = $("#tacticalBannerCloseBtn");
  const banner = $("#tacticalModelBanner");
  if (closeBtn && banner) {
    closeBtn.addEventListener("click", () => {
      banner.classList.add("hidden");
    });
  }
}

function wireLayerToggles() {
  $$(".layer-toggle").forEach((wrap) => {
    const input = wrap.querySelector("input");
    const key = wrap.dataset.layer;
    wrap.classList.toggle("is-on", input.checked);
    input.addEventListener("change", () => {
      wrap.classList.toggle("is-on", input.checked);
      if (key === "satellite") {
        if (input.checked) {
          map.removeLayer(layers.base);
          layers.satellite.addTo(map);
        } else {
          map.removeLayer(layers.satellite);
          layers.base.addTo(map);
        }
        return;
      }
      const layer = layers[key];
      if (!layer) return;
      if (input.checked) layer.addTo(map);
      else map.removeLayer(layer);
    });
  });
}

/* ---------------- incident queue ---------------- */
function elapsed(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ${String(s % 60).padStart(2, "0")}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

/* ---------------- incident queue with filtering (Requirement 3) ---------------- */
let currentFilter = "all";

function wireQueueFilters() {
  const select = $("#queueFilterSelect");
  if (select) {
    select.addEventListener("change", (e) => {
      currentFilter = e.target.value;
      renderQueue();
    });
  }
}

function renderQueue() {
  const list = $("#queue");
  let filtered = INCIDENTS;
  if (currentFilter === "red") filtered = INCIDENTS.filter(i => i.triage === "red");
  else if (currentFilter === "yellow") filtered = INCIDENTS.filter(i => i.triage === "yellow");
  else if (currentFilter === "green") filtered = INCIDENTS.filter(i => i.triage === "green");
  
  const sorted = [...filtered].sort((a, b) => b.rsi - a.rsi);

  if (sorted.length === 0) {
    list.innerHTML = `<p class="queue-empty">No ${currentFilter === "all" ? "" : currentFilter === "red" ? "critical" : currentFilter === "yellow" ? "urgent" : "stable"} incidents at this time.</p>`;
  } else {
    list.innerHTML = sorted
      .map(
        (i) => `<div class="incident incident--${i.triage} ${i.id === selected.id ? "is-selected" : ""}" data-id="${i.id}" role="button" tabindex="0">
        <!-- Compact Operational Rail: dot and clickable text on same line, no card container -->
        <div class="incident__compact">
          <span class="incident-rail-dot incident-rail-dot--${i.triage}" aria-hidden="true"></span>
          <button class="incident-rail-text" type="button" data-id="${i.id}" title="${i.id} · ${i.title} (${i.triage.toUpperCase()})">${i.id}</button>
        </div>
        <!-- Full representation -->
        <div class="incident__full">
          <div class="incident__top">
            <div class="incident__badges">
              <span class="badge badge--${i.triage}">${i.triage === "red" ? "Critical" : i.triage === "yellow" ? "Urgent" : "Stable"}</span>
              <span class="incident__id">${i.id}</span>
            </div>
            <span class="rsi">${i.rsi.toFixed(1)} <small>RSI</small></span>
          </div>
          <h3 class="incident__title">${i.title}</h3>
          <div class="incident__loc">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
            <span>${i.place}</span>
          </div>
          <div class="incident__meta">
            <span class="incident__stat">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
              ${i.victims} victim${i.victims > 1 ? "s" : ""}
            </span>
            <span class="meta-dot" aria-hidden="true">·</span>
            <span class="incident__stat incident__stat--time">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              <span data-elapsed="${i.id}">${elapsed(i.started)} elapsed</span>
            </span>
          </div>
          ${i.injuries ? `<p class="incident__injuries">${i.injuries}</p>` : ""}
          ${i.hazards && i.hazards.length ? `<div class="incident__hazards">${i.hazards.map((h) => `<span class="hz">${h}</span>`).join("")}</div>` : ""}
        </div>
      </div>`
      )
      .join("");
    $$(".incident", list).forEach((c) => {
      c.addEventListener("click", () => select(c.dataset.id));
      c.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          select(c.dataset.id);
        }
      });
    });
    $$(".incident-rail-text", list).forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        select(btn.dataset.id);
      });
    });
  }

  const activeCount = INCIDENTS.length;
  const critCount = INCIDENTS.filter((i) => i.triage === "red").length;
  const idleCount = UNITS.filter((u) => u.status === "idle").length;
  $("#kpiActive").textContent = activeCount;
  $("#kpiCritical").textContent = critCount;
  $("#kpiUnits").textContent = idleCount;
  // Update compact chip & mobile queue count badge
  const chip = $("#kpiChipText");
  if (chip) chip.textContent = `${activeCount} active · ${critCount} critical`;
  const qcBadge = $("#queueCount");
  if (qcBadge) qcBadge.textContent = sorted.length;
  const mqcBadge = $("#mobileQueueCount");
  if (mqcBadge) mqcBadge.textContent = sorted.length;
}

function tickElapsed() {
  INCIDENTS.forEach((i) => {
    const node = document.querySelector(`[data-elapsed="${i.id}"]`);
    if (node) node.textContent = `${elapsed(i.started)} elapsed`;
  });
  if (selected) {
    const briefEl = $("#detailElapsed");
    if (briefEl) briefEl.textContent = `${elapsed(selected.started)} elapsed`;
  }
}

function select(id) {
  selected = INCIDENTS.find((i) => i.id === id) || selected;
  renderQueue();
  map.flyTo([selected.lat, selected.lng], 13, { duration: 0.6 });
  renderMissionConsole(selected);

  if (window.innerWidth <= 860) {
    setMobileView("console");
  }
}

/* ---------------- mission console (Pane 3) ---------------- */

/** focusIncident — pan the map to an incident and open the console.
 *  Called by the WebSocket `incident:new` handler when a live incident arrives. */
function focusIncident(inc) {
  if (!inc) return;
  if (map) map.flyTo([inc.lat, inc.lng], 13, { duration: 0.8 });
  renderMissionConsole(inc);
  if (window.innerWidth <= 860) {
    setMobileView("console");
  }
}

function renderMissionConsole(i) {
  if (!i) return;

  // Dynamic card triage accent (Requirement 7)
  const briefCard = $("#missionBriefCard");
  if (briefCard) {
    briefCard.dataset.triage = i.triage || "red";
  }

  const triageEl = $("#detailTriage");
  if (triageEl) {
    triageEl.textContent = i.triage === "red" ? "CRITICAL P1" : (i.triage === "yellow" ? "URGENT P2" : "STABLE P3");
    triageEl.className = `badge badge--triage badge--${i.triage}`;
  }

  const rsiEl = $("#detailRsi");
  if (rsiEl) rsiEl.textContent = `RSI ${i.rsi.toFixed(1)}`;

  const elapsedEl = $("#detailElapsed");
  if (elapsedEl) elapsedEl.textContent = `${elapsed(i.started)} elapsed`;

  const titleEl = $("#detailTitle");
  if (titleEl) titleEl.textContent = i.title;

  const coordsEl = $("#detailCoordsText");
  if (coordsEl) coordsEl.textContent = `${i.place} (${i.lat.toFixed(4)}, ${i.lng.toFixed(4)})`;

  const victimEl = $("#detailVictimCount");
  if (victimEl) victimEl.textContent = `${i.victims} Victim${i.victims > 1 ? "s" : ""}`;

  const injuriesEl = $("#detailInjuries");
  if (injuriesEl) injuriesEl.textContent = i.injuries;

  const hazardsEl = $("#detailHazards");
  if (hazardsEl) {
    hazardsEl.innerHTML = i.hazards.length
      ? i.hazards.map(h => `<span class="hz">${h}</span>`).join("")
      : `<span style="font-size:11px;color:var(--text-3)">No active environmental hazards flagged</span>`;
  }

  const hospNameEl = $("#detailHospital");
  const hospCapsEl = $("#detailHospitalCaps");
  const hospEtaEl = $("#detailHospitalEta");

  // Immediate fallback rendering so the card is never blank
  const fallbackHosp = i.triage === "red" ? HOSPITALS[0] : nearestHospital(i);
  if (hospNameEl) hospNameEl.textContent = fallbackHosp.name;
  if (hospEtaEl) hospEtaEl.textContent = "8.4 mins · 92% Survival";
  if (hospCapsEl) {
    const defaultParts = fallbackHosp.caps ? fallbackHosp.caps.split(/\s*·\s*/) : ["Level 1 trauma", "ICU", "Blood bank"];
    hospCapsEl.innerHTML = defaultParts.map(cap => `<span class="facility-cap-tag">${cap}</span>`).join(" ");
  }

  // Live Golden Hour Model Evaluation
  if (i.lat && i.lng) {
    fetch("/api/nearest-hospital", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: i.lat,
        lng: i.lng,
        incident_type: i.type || (i.triage === "red" ? "trauma" : "general"),
        rsi_score: i.rsi || 3.8
      })
    })
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (data && (data.recommended_hospital || data.all_options?.length)) {
        const hospName = typeof data.recommended_hospital === "object" && data.recommended_hospital !== null
          ? (data.recommended_hospital.name || fallbackHosp.name)
          : (data.recommended_hospital || fallbackHosp.name);

        if (hospNameEl) hospNameEl.textContent = hospName;

        let survivalPct = "93%";
        if (typeof data.predicted_survival_probability === "string") {
          survivalPct = data.predicted_survival_probability.endsWith("%") ? data.predicted_survival_probability : `${data.predicted_survival_probability}%`;
        } else if (typeof data.predicted_survival_probability === "number") {
          survivalPct = `${(data.predicted_survival_probability * 100).toFixed(0)}%`;
        }

        const durationMins = data.duration_mins != null ? data.duration_mins : 8.4;
        const distKm = data.distance_km != null ? ` (${data.distance_km} km)` : "";
        if (hospEtaEl) {
          hospEtaEl.textContent = `${durationMins} mins${distKm} · ${survivalPct} Survival`;
        }

        if (hospCapsEl) {
          const capTier = data.capability ? `${data.capability.toUpperCase()} TRAUMA` : "LEVEL-1 TRAUMA";
          const survivalTag = `<span class="facility-cap-tag" style="background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent); border-color:var(--accent);">Golden Hour: ${survivalPct}</span>`;
          hospCapsEl.innerHTML = `<span class="facility-cap-tag">${capTier}</span> <span class="facility-cap-tag">ICU READY</span> ${survivalTag}`;
        }
      }
    })
    .catch(err => {
      console.warn("Nearest hospital API fallback:", err);
    });
  }

  const assignedBadge = $("#detailAssignedBadge");
  if (assignedBadge) {
    assignedBadge.textContent = i.assigned_unit ? `Assigned: ${i.assigned_unit}` : "Unassigned";
    assignedBadge.className = i.assigned_unit ? "badge badge--assigned badge--teal" : "badge badge--assigned";
  }

  // Populate unit select options
  const unitSelect = $("#unitSelect");
  if (unitSelect) {
    unitSelect.innerHTML = UNITS.map(u => {
      const statusLabel = u.status === "idle" ? `Available (${u.eta || 5}m ETA)` : `Status: ${u.status}`;
      const isSelected = i.assigned_unit === u.id ? "selected" : "";
      return `<option value="${u.id}" ${isSelected}>${u.name} · ${statusLabel}</option>`;
    }).join("");
  }
}

function wireConsoleTabs() {
  const tabMission = $("#tabMission");
  const tabFleet = $("#tabFleet");
  const missionContent = $("#missionTabContent");
  const fleetContent = $("#fleetTabContent");

  if (tabMission && tabFleet) {
    tabMission.addEventListener("click", () => {
      tabMission.classList.add("is-active");
      tabFleet.classList.remove("is-active");
      missionContent?.classList.remove("hidden");
      fleetContent?.classList.add("hidden");
    });
    tabFleet.addEventListener("click", () => {
      tabFleet.classList.add("is-active");
      tabMission.classList.remove("is-active");
      fleetContent?.classList.remove("hidden");
      missionContent?.classList.add("hidden");
      renderFleet();
    });
  }

  const consoleToggle = $("#consoleToggle");
  const consoleClose = $("#consoleClose");
  const consolePanel = $("#consolePanel");
  if (consoleToggle && consolePanel) {
    consoleToggle.addEventListener("click", () => consolePanel.classList.toggle("is-open"));
  }
  if (consoleClose && consolePanel) {
    consoleClose.addEventListener("click", () => consolePanel.classList.remove("is-open"));
  }
}

function wireDispatchAction() {
  const dispatchBtn = $("#consoleDispatchBtn");
  if (dispatchBtn) {
    dispatchBtn.addEventListener("click", () => {
      const unitCode = $("#unitSelect")?.value || "AMB-07";
      selected.assigned_unit = unitCode;
      
      const unit = UNITS.find((u) => u.id === unitCode);
      if (unit) unit.status = "dispatched";
      
      // Call backend assign API to update database and broadcast
      fetch("/api/responder/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          incident_uuid: selected.id,
          unit_code: unitCode
        })
      }).catch(err => console.warn("[Dispatch] Server assign sync note:", err));

      if (window.resqSocket) {
        window.resqSocket.emit("responder:assign", {
          incident_uuid: selected.id,
          unit_code: unitCode
        });
      }

      renderMissionConsole(selected);
      renderFleet();
      renderQueue();
      pushComms("dispatch", `Unit ${unit ? unit.name : unitCode} assigned to ${selected.id}. Mission brief transmitted.`);

      dispatchBtn.classList.add("is-dispatched");
      const labelSpan = dispatchBtn.querySelector(".dispatch-label");
      if (labelSpan) labelSpan.textContent = "Dispatched";
      setTimeout(() => {
        dispatchBtn.classList.remove("is-dispatched");
        if (labelSpan) labelSpan.textContent = "Dispatch Unit";
      }, 2500);
    });
  }
}

/* ---------------- fleet ---------------- */
function renderFleet() {
  const labels = { idle: "Idle", dispatched: "Dispatched", enroute: "En route", scene: "On scene" };
  const fleetEl = $("#fleet");
  if (fleetEl) {
    fleetEl.innerHTML = UNITS.map(
      (u) => `<article class="unit">
        <span class="unit__dot unit__dot--${u.status}"></span>
        <div class="grow">
          <p class="unit__name">${u.name}</p>
          <p class="unit__meta">${u.type} · ${u.lat.toFixed(3)}, ${u.lng.toFixed(3)}</p>
        </div>
        <span class="unit__status">${labels[u.status]}</span>
      </article>`
    ).join("");
  }
}

function nearestHospital(i) {
  return HOSPITALS.slice().sort(
    (a, b) => Math.hypot(a.lat - i.lat, a.lng - i.lng) - Math.hypot(b.lat - i.lat, b.lng - i.lng)
  )[0];
}

/* ---------------- comms console ---------------- */
const COMMS = {
  civilian: [
    { who: "Bystander · RQ-2417", text: "Two people. One is not answering me, the other is bleeding from the arm." },
    { who: "ResQ guidance", text: "Recovery position steps issued. Direct pressure steps issued." },
  ],
  responder: [
    { who: "AMB-07", text: "Copy. Rolling from Ugwuoba staging point." },
    { who: "FRSC-12", text: "Fuel spill confirmed. No flares. Lane closure in place." },
  ],
};
let channel = "civilian";

function renderComms() {
  $("#commsLog").innerHTML = COMMS[channel]
    .map(
      (l) => `<div class="comms__line ${l.me ? "comms__line--me" : ""}">
        <p class="comms__who">${l.who}</p>
        <p class="comms__text">${l.text}</p>
      </div>`
    )
    .join("");
  $("#commsLog").scrollTop = $("#commsLog").scrollHeight;
}

function pushComms(target, text) {
  const key = target === "dispatch" ? "responder" : target;
  COMMS[key].push({ who: "Dispatch", text, me: true });
  renderComms();
}


$("#commsForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#commsInput");
  if (!input.value.trim()) return;
  COMMS[channel].push({ who: "Dispatch", text: input.value.trim(), me: true });
  input.value = "";
  renderComms();
});

/* ---------------- responsive panels ---------------- */
const queueHead = $("#queueHead");
if (queueHead) {
  queueHead.addEventListener("click", (e) => {
    if (window.innerWidth <= 860 && !e.target.closest("button:not(#queueHead)")) {
      $("#queuePanel")?.classList.toggle("is-open");
    }
  });
}


/* ---------------- live feed simulation ---------------- */
function simulate() {
  UNITS.forEach((u) => {
    if (u.status === "enroute" || u.status === "dispatched") {
      u.lat += (Math.random() - 0.5) * 0.004;
      u.lng += (Math.random() - 0.5) * 0.004;
    }
  });
  renderFleet();
  tickElapsed();
}

/* ---------------- real-time websocket integration ---------------- */
let resqSocket = null;
if (window.ResQSocket) {
  resqSocket = new window.ResQSocket("dispatcher");

  resqSocket.on("incident:new", (inc) => {
    console.log("[Dispatcher] New incident received via WebSocket:", inc);
    const localInc = {
      id: inc.incident_uuid,
      rsi: inc.severity_score || 4.5,
      triage: inc.severity_level === "critical" ? "red" : (inc.severity_level === "urgent" ? "yellow" : "green"),
      title: inc.title,
      place: inc.location_name,
      victims: inc.casualties_count || 1,
      injuries: inc.title,
      hazards: [],
      lat: inc.lat,
      lng: inc.lng,
      started: Date.now()
    };
    if (!INCIDENTS.some(i => i.id === localInc.id)) {
      INCIDENTS.unshift(localInc);
      selected = localInc;
      renderQueue();
      focusIncident(localInc);
    }
  });

  resqSocket.on("telemetry:update", (t) => {
    const unit = UNITS.find(u => u.id === t.unit_code);
    if (unit) {
      unit.lat = t.lat;
      unit.lng = t.lng;
      renderFleet();
    }
  });
}

// Demo simulation button handler
const demoBtn = $("#demoInjectBtn");
if (demoBtn) {
  demoBtn.addEventListener("click", () => {
    const scenario = Math.random() > 0.5 ? "crash" : "flood";
    fetch("/api/demo/inject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenario })
    })
    .then(res => res.json())
    .then(data => {
      console.log("[Dispatcher] Injected synthetic demo:", data);
      if (scenario === "flood") {
        loadFloodRiskLayer(58.0);
        loadCorridorRiskLayer(38.0);
      } else {
        loadCorridorRiskLayer(45.0);
        loadFloodRiskLayer(15.0);
      }
    })
    .catch(err => console.error("Error injecting demo:", err));
  });
}

/* ---------------- region selector (S/N 14) ---------------- */
const REGION_VIEWS = {
  community: { center: [6.4474, 7.5098], zoom: 13, name: "Enugu Urban" },
  state: { center: [6.42, 7.38], zoom: 10, name: "Enugu State" },
  country: { center: [9.0820, 8.6753], zoom: 6, name: "Nigeria" }
};
let currentRegion = "community";

function wireRegionSelector() {
  const btns = $$(".region-btn");
  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const reg = btn.dataset.region;
      currentRegion = reg;
      const view = REGION_VIEWS[reg];
      if (view && map) {
        map.flyTo(view.center, view.zoom, { duration: 1.2 });
      }
      updateWeatherWidget(reg);
    });
  });
}

/* ---------------- weather & responder hazard widget (S/N 19) ---------------- */
async function updateWeatherWidget(regionCode = "community") {
  const view = REGION_VIEWS[regionCode] || REGION_VIEWS.community;
  try {
    const res = await fetch(`/api/weather?region=${regionCode}&lat=${view.center[0]}&lng=${view.center[1]}`);
    if (!res.ok) return;
    const data = await res.json();
    
    // Update DOM elements
    const tempEl = $("#weatherTemp");
    const condEl = $("#weatherCondition");
    const rainEl = $("#weatherRain");
    const windEl = $("#weatherWind");
    const visEl = $("#weatherVis");
    const delayEl = $("#weatherDelay");
    const trendEl = $("#weatherTrend");
    const advContainer = $("#weatherAdvisories");

    if (tempEl) tempEl.textContent = `${data.temp_c}°C`;
    if (condEl) condEl.textContent = data.condition;
    if (rainEl) rainEl.textContent = `${data.rainfall_mm_hr} mm/h`;
    if (windEl) windEl.textContent = `${data.wind_kmh} km/h NE`;
    if (visEl) visEl.textContent = `${data.visibility_km} km`;
    
    const impact = data.operational_impact || {};
    const delay = impact.transit_delay_pct || 0;
    if (delayEl) {
      delayEl.textContent = delay > 0 ? `+${delay}% ETA` : "Nominal";
      delayEl.className = delay > 0 ? "metric-val text-amber" : "metric-val";
    }
    
    if (trendEl) {
      trendEl.textContent = (impact.escalation_trend || "steady").toUpperCase();
      trendEl.className = `badge badge--escalation badge--${impact.escalation_trend || "steady"}`;
    }
    
    // Render Advisories
    if (advContainer) {
      advContainer.innerHTML = "";
      const advisories = impact.advisories || [];
      advisories.forEach(adv => {
        const el = document.createElement("div");
        el.className = `weather-advisory weather-advisory--${adv.level || "warning"}`;
        el.innerHTML = `
          <div class="advisory-tag">${adv.title}</div>
          <div class="advisory-msg">${adv.message}</div>
        `;
        advContainer.appendChild(el);
      });
    }
    // Update region label in weather dropdown
    const regionLabel = $("#weatherRegionLabel");
    if (regionLabel) regionLabel.textContent = view.name || "Enugu Urban";

    // Sync dynamic predictive model layers with live precipitation
    const currentRain = data.rainfall_mm_hr || 0;
    loadFloodRiskLayer(currentRain);
    loadCorridorRiskLayer(currentRain);
  } catch (err) {
    console.error("[WeatherWidget] Failed to update weather:", err);
  }
}

/* ---------------- topbar weather dropdown toggle (Requirement 1 & 9) ---------------- */
function wireWeatherTopBar() {
  const wrap = $("#topbarWeatherWrap");
  const toggle = $("#weatherWidgetToggle");
  const dropdown = $("#weatherBody");
  const collapseBtn = $("#weatherCollapseBtn");
  if (!wrap || !toggle || !dropdown) return;

  const toggleDropdown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const isHidden = dropdown.classList.toggle("hidden");
    toggle.classList.toggle("is-open", !isHidden);
    toggle.setAttribute("aria-expanded", String(!isHidden));
    if (collapseBtn) collapseBtn.setAttribute("aria-expanded", String(!isHidden));
  };

  toggle.addEventListener("click", toggleDropdown);
  if (collapseBtn) {
    collapseBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleDropdown(e);
    });
  }
  dropdown.addEventListener("click", (e) => e.stopPropagation());

  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) {
      dropdown.classList.add("hidden");
      toggle.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      if (collapseBtn) collapseBtn.setAttribute("aria-expanded", "false");
    }
  });
}

/* ---------------- mobile view switcher (Requirement 10) ---------------- */
function setMobileView(view) {
  const ws = $("#workspace");
  if (!ws) return;
  ws.dataset.mobileView = view;
  $$(".mobile-nav-tab").forEach((tab) => {
    const isActive = tab.dataset.view === view;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
  });
  if (view === "map") {
    setTimeout(() => map?.invalidateSize(), 60);
  }
}

function wireMobileNav() {
  $$(".mobile-nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      setMobileView(tab.dataset.view);
    });
  });
}

/* ---------------- left pane collapse / expand (Requirements 1, 2 & 4) ---------------- */
function wireQueueCollapse() {
  const collapseBtn = $("#collapseQueueBtn");
  const ws = $("#workspace");
  if (!ws || !collapseBtn) return;

  collapseBtn.addEventListener("click", () => {
    const isCollapsed = ws.classList.toggle("left-collapsed");
    collapseBtn.title = isCollapsed ? "Expand incident queue" : "Collapse to compact rail";
    collapseBtn.setAttribute("aria-label", collapseBtn.title);
    setTimeout(() => map?.invalidateSize(), 150);
  });
}

/* ---------------- fullscreen view toggle (Requirement 5) ---------------- */
function wireFullscreen() {
  const fsBtn = $("#fullscreenBtn");
  if (!fsBtn) return;
  const maxIcon = fsBtn.querySelector(".fs-icon-max");
  const minIcon = fsBtn.querySelector(".fs-icon-min");

  const updateIcons = () => {
    const isFs = !!document.fullscreenElement;
    maxIcon?.classList.toggle("hidden", isFs);
    minIcon?.classList.toggle("hidden", !isFs);
    fsBtn.title = isFs ? "Exit Fullscreen" : "Enter Fullscreen";
    setTimeout(() => map?.invalidateSize(), 100);
  };

  fsBtn.addEventListener("click", () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => console.log(err));
    } else {
      document.exitFullscreen().catch((err) => console.log(err));
    }
  });

  document.addEventListener("fullscreenchange", updateIcons);
}

/* ---------------- adjustable pane resizers (Requirement 7) ---------------- */
function wirePaneResizers() {
  const ws = $("#workspace");
  const resizerLeft = $("#resizerLeft");
  const resizerRight = $("#resizerRight");
  if (!ws) return;

  // Restore saved widths if any
  const savedLeft = localStorage.getItem("resq-cad-left-w");
  const savedRight = localStorage.getItem("resq-cad-right-w");
  if (savedLeft) ws.style.setProperty("--left-pane-w", savedLeft);
  if (savedRight) ws.style.setProperty("--right-pane-w", savedRight);

  function attachResizer(handle, isLeft) {
    if (!handle) return;

    const onPointerMove = (e) => {
      const clientX = e.clientX ?? (e.touches && e.touches[0].clientX);
      if (clientX == null) return;

      let newW;
      if (isLeft) {
        newW = Math.max(220, Math.min(480, clientX));
        ws.style.setProperty("--left-pane-w", `${newW}px`);
        localStorage.setItem("resq-cad-left-w", `${newW}px`);
      } else {
        const wsRect = ws.getBoundingClientRect();
        newW = Math.max(260, Math.min(540, wsRect.right - clientX));
        ws.style.setProperty("--right-pane-w", `${newW}px`);
        localStorage.setItem("resq-cad-right-w", `${newW}px`);
      }
      map?.invalidateSize();
    };

    const onPointerUp = () => {
      ws.classList.remove("is-resizing");
      handle.classList.remove("is-dragging");
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      window.removeEventListener("touchmove", onPointerMove);
      window.removeEventListener("touchend", onPointerUp);
      map?.invalidateSize();
    };

    const onPointerDown = (e) => {
      if (window.innerWidth <= 860 || ws.classList.contains("left-collapsed")) return;
      e.preventDefault();
      ws.classList.add("is-resizing");
      handle.classList.add("is-dragging");
      window.addEventListener("mousemove", onPointerMove);
      window.addEventListener("mouseup", onPointerUp);
      window.addEventListener("touchmove", onPointerMove, { passive: false });
      window.addEventListener("touchend", onPointerUp);
    };

    handle.addEventListener("mousedown", onPointerDown);
    handle.addEventListener("touchstart", onPointerDown, { passive: false });

    // Double click to reset to default widths
    handle.addEventListener("dblclick", () => {
      if (isLeft) {
        ws.style.setProperty("--left-pane-w", "310px");
        localStorage.removeItem("resq-cad-left-w");
      } else {
        ws.style.setProperty("--right-pane-w", "350px");
        localStorage.removeItem("resq-cad-right-w");
      }
      map?.invalidateSize();
    });
  }

  attachResizer(resizerLeft, true);
  attachResizer(resizerRight, false);
}

/* ---------------- boot ---------------- */
initMap();
wireLayerToggles();
wireRegionSelector();
wireQueueFilters();
wireConsoleTabs();
wireDispatchAction();
wireWeatherTopBar();
wirePaneResizers();
wireQueueCollapse();
wireFullscreen();
wireMobileNav();
wireTacticalBanner();
updateWeatherWidget("community");
renderQueue();
renderMissionConsole(selected);
renderFleet();
renderComms();
setInterval(tickElapsed, 1000);
setInterval(simulate, 15000);
setInterval(() => updateWeatherWidget(currentRegion), 60000); // 1-minute meteorological sync


