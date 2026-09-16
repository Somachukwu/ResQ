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

  FLOODZONES.forEach((f) => {
    L.circle([f.lat, f.lng], {
      radius: f.r,
      color: "#993C1D",
      weight: 1,
      fillColor: "#993C1D",
      fillOpacity: 0.14,
    })
      .bindTooltip(f.name, { direction: "top" })
      .addTo(layers.flood);
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

function renderQueue() {
  const list = $("#queue");
  const sorted = [...INCIDENTS].sort((a, b) => b.rsi - a.rsi);
  list.innerHTML = sorted
    .map(
      (i) => `<button class="incident incident--${i.triage} ${i.id === selected.id ? "is-selected" : ""}" data-id="${i.id}">
        <div class="incident__top">
          <span class="incident__id">${i.id}</span>
          <span class="badge badge--${i.triage}">${i.triage === "red" ? "Critical" : i.triage === "yellow" ? "Urgent" : "Minor"}</span>
        </div>
        <h3 class="incident__title">${i.title}</h3>
        <div class="incident__meta">
          <span>${i.place}</span>
        </div>
        <div class="incident__meta">
          <span>${i.victims} victim${i.victims > 1 ? "s" : ""}</span>
          <span data-elapsed="${i.id}">${elapsed(i.started)} elapsed</span>
          <span class="rsi">${i.rsi.toFixed(1)} <small>RSI</small></span>
        </div>
        <p class="incident__meta"><span>${i.injuries}</span></p>
        ${i.hazards.length ? `<div class="incident__hazards">${i.hazards.map((h) => `<span class="hz">${h}</span>`).join("")}</div>` : ""}
      </button>`
    )
    .join("");

  $$(".incident", list).forEach((c) => c.addEventListener("click", () => select(c.dataset.id)));
  $("#kpiActive").textContent = INCIDENTS.length;
  $("#kpiCritical").textContent = INCIDENTS.filter((i) => i.triage === "red").length;
  $("#kpiUnits").textContent = UNITS.filter((u) => u.status === "idle").length;
}

function tickElapsed() {
  INCIDENTS.forEach((i) => {
    const node = document.querySelector(`[data-elapsed="${i.id}"]`);
    if (node) node.textContent = `${elapsed(i.started)} elapsed`;
  });
}

function select(id) {
  selected = INCIDENTS.find((i) => i.id === id) || selected;
  renderQueue();
  map.flyTo([selected.lat, selected.lng], 13, { duration: 0.6 });
  openDispatch();
}

/* ---------------- fleet ---------------- */
function renderFleet() {
  const labels = { idle: "Idle", dispatched: "Dispatched", enroute: "En route", scene: "On scene" };
  $("#fleet").innerHTML = UNITS.map(
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

/* ---------------- dispatch modal ---------------- */
function bestUnit() {
  const free = UNITS.filter((u) => u.status === "idle");
  return (free.length ? free : UNITS).slice().sort((a, b) => a.eta - b.eta)[0];
}

function nearestHospital(i) {
  return HOSPITALS.slice().sort(
    (a, b) => Math.hypot(a.lat - i.lat, a.lng - i.lng) - Math.hypot(b.lat - i.lat, b.lng - i.lng)
  )[0];
}

function openDispatch() {
  const unit = bestUnit();
  const hosp = selected.triage === "red" ? HOSPITALS[0] : nearestHospital(selected);
  $("#modalTitle").textContent = `${selected.id} — ${selected.title}`;
  $("#modalPlace").textContent = selected.place;
  $("#matchUnit").textContent = unit.name;
  $("#matchEta").textContent = `${unit.eta} min`;
  $("#matchCaps").textContent = unit.caps;
  $("#matchHospital").textContent = `${hosp.name} — ${hosp.caps}`;
  $("#matchAlt").innerHTML = UNITS.filter((u) => u.id !== unit.id)
    .slice(0, 3)
    .map((u) => `<div class="alt-unit"><span>${u.name} · ${u.type}</span><span>${u.eta || "—"} min</span></div>`)
    .join("");
  $("#dispatchBtn").dataset.unit = unit.id;
  $("#modal").classList.add("is-open");
}

$("#dispatchBtn").addEventListener("click", (e) => {
  const unit = UNITS.find((u) => u.id === e.currentTarget.dataset.unit);
  if (unit) unit.status = "dispatched";
  renderFleet();
  pushComms("dispatch", `Mission brief for ${selected.id} transmitted to ${unit ? unit.name : "unit"}.`);
  $("#modal").classList.remove("is-open");
});

$$("[data-close-modal]").forEach((b) => b.addEventListener("click", () => $("#modal").classList.remove("is-open")));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $("#modal").classList.remove("is-open");
});

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

$$(".comms__tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    $$(".comms__tab").forEach((t) => t.classList.remove("is-active"));
    tab.classList.add("is-active");
    channel = tab.dataset.channel;
    renderComms();
  })
);

$("#commsForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#commsInput");
  if (!input.value.trim()) return;
  COMMS[channel].push({ who: "Dispatch", text: input.value.trim(), me: true });
  input.value = "";
  renderComms();
});

/* ---------------- responsive panels ---------------- */
$("#queueHead").addEventListener("click", (e) => {
  if (window.innerWidth <= 860 && !e.target.closest("button:not(#queueHead)")) {
    $("#queuePanel").classList.toggle("is-open");
  }
});
$("#fleetToggle").addEventListener("click", () => $("#fleetPanel").classList.toggle("is-open"));
$("#fleetClose").addEventListener("click", () => $("#fleetPanel").classList.remove("is-open"));

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

/* ---------------- boot ---------------- */
initMap();
wireLayerToggles();
renderQueue();
renderFleet();
renderComms();
setInterval(tickElapsed, 1000);
setInterval(simulate, 15000);
